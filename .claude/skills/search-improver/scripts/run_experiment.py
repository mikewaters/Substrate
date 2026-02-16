# /// script
# dependencies = [
#   "idx",
# ]
# ///
"""Run end-to-end retrieval experiments across multiple search modes.

Ingests a corpus (Obsidian vault or pre-built corpus.jsonl), then runs
retrieval evaluation across FTS, vector, hybrid, and hybrid+rerank modes.
Writes structured artifacts: run.json, results.jsonl, metrics.json, trace.jsonl.

Usage:
    uv run python run_experiment.py \
        --corpus-dir /path/to/corpus \
        --output-dir /path/to/output \
        --slug my-experiment
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentlayer.logging import configure_logging, get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class ModeSpec:
    """Specification for a single retrieval mode to evaluate.

    Attributes:
        label: Human-readable label used in output artifacts.
        mode: SearchCriteria mode value (fts, vector, hybrid).
        rerank: Whether to enable LLM-as-judge reranking.
    """

    label: str
    mode: str  # "fts" | "vector" | "hybrid"
    rerank: bool


ALL_MODES: list[ModeSpec] = [
    ModeSpec(label="fts", mode="fts", rerank=False),
    ModeSpec(label="vector", mode="vector", rerank=False),
    ModeSpec(label="hybrid", mode="hybrid", rerank=False),
    ModeSpec(label="hybrid_rerank", mode="hybrid", rerank=True),
]


@dataclass
class QueryDef:
    """A query loaded from queries.json or golden_queries.json.

    Attributes:
        query: The search query text.
        expected_docs: List of expected document paths/IDs.
        difficulty: Difficulty tier (easy/medium/hard/fusion).
    """

    query: str
    expected_docs: list[str]
    difficulty: str


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Run end-to-end retrieval experiments across multiple search modes.",
    )
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        required=True,
        help="Directory containing corpus. Either an Obsidian vault or a dir with corpus.jsonl/queries.json.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory where experiment artifacts are written.",
    )
    parser.add_argument(
        "--slug",
        type=str,
        required=True,
        help="Experiment slug for identification.",
    )
    parser.add_argument(
        "--dataset-name",
        type=str,
        default="eval-vault",
        help="Dataset name for ingestion (default: eval-vault).",
    )
    parser.add_argument(
        "--embedding-model",
        type=str,
        default="mlx-community/all-MiniLM-L6-v2-bf16",
        help="Embedding model identifier.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root for git metadata (default: auto-detect).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Max results per query (default: 10).",
    )
    parser.add_argument(
        "--queries-file",
        type=Path,
        default=None,
        help="Explicit path to queries JSON. Auto-detected from corpus-dir if omitted.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Log level (default: INFO).",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Environment & isolation
# ---------------------------------------------------------------------------

EVAL_TMP = Path("/tmp/catalog-eval-experiment")


def setup_isolated_env(embedding_model: str) -> None:
    """Configure environment variables for isolated eval databases.

    Sets SUBSTRATE_* env vars so that the catalog stack uses ephemeral paths
    under /tmp/catalog-eval-experiment/ instead of the user's real data.

    Args:
        embedding_model: Embedding model identifier to inject.
    """
    catalog_db = EVAL_TMP / "catalog.db"
    content_db = EVAL_TMP / "content.db"
    vector_dir = EVAL_TMP / "vectors"

    EVAL_TMP.mkdir(parents=True, exist_ok=True)
    vector_dir.mkdir(parents=True, exist_ok=True)

    # Remove stale databases so each experiment starts fresh
    for db_path in (catalog_db, content_db):
        if db_path.exists():
            db_path.unlink()
    # Remove stale vector store contents
    for child in vector_dir.iterdir():
        if child.is_file():
            child.unlink()

    os.environ["SUBSTRATE_DATABASES__CATALOG_PATH"] = str(catalog_db)
    os.environ["SUBSTRATE_DATABASES__CONTENT_PATH"] = str(content_db)
    os.environ["SUBSTRATE_VECTOR_STORE_PATH"] = str(vector_dir)
    os.environ["SUBSTRATE_EMBEDDING_MODEL"] = embedding_model

    logger.info(f"Isolated eval env: catalog={catalog_db}, content={content_db}, vectors={vector_dir}")


# ---------------------------------------------------------------------------
# Corpus & query loading
# ---------------------------------------------------------------------------

def detect_queries_file(corpus_dir: Path) -> Path:
    """Auto-detect a queries file within the corpus directory.

    Checks for queries.json and golden_queries.json in order.

    Args:
        corpus_dir: Directory to scan.

    Returns:
        Path to the detected queries file.

    Raises:
        FileNotFoundError: If no queries file is found.
    """
    candidates = ["queries.json", "golden_queries.json"]
    for name in candidates:
        path = corpus_dir / name
        if path.exists():
            logger.info(f"Detected queries file: {path}")
            return path
    raise FileNotFoundError(
        f"No queries file found in {corpus_dir}. "
        f"Looked for: {', '.join(candidates)}. "
        f"Use --queries-file to specify one explicitly."
    )


def load_queries(queries_path: Path) -> list[QueryDef]:
    """Load query definitions from a JSON file.

    Supports two formats:
    1. Wrapped format: {"queries": [...]} (from build_corpus.py)
    2. Array format: [...] (golden_queries.json)

    Each query object must have at minimum: query, expected_docs.

    Args:
        queries_path: Path to the JSON file.

    Returns:
        List of QueryDef instances.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file format is unrecognized.
    """
    if not queries_path.exists():
        raise FileNotFoundError(f"Queries file not found: {queries_path}")

    raw = json.loads(queries_path.read_text(encoding="utf-8"))

    # Unwrap if needed
    if isinstance(raw, dict) and "queries" in raw:
        items = raw["queries"]
    elif isinstance(raw, list):
        items = raw
    else:
        raise ValueError(
            f"Unrecognized queries format in {queries_path}. "
            f"Expected a JSON array or an object with a 'queries' key."
        )

    queries: list[QueryDef] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"Query item {i} is not an object.")
        if "query" not in item or "expected_docs" not in item:
            raise ValueError(f"Query item {i} missing required fields (query, expected_docs).")
        queries.append(QueryDef(
            query=item["query"],
            expected_docs=item["expected_docs"],
            difficulty=item.get("difficulty", "medium"),
        ))

    logger.info(f"Loaded {len(queries)} queries from {queries_path}")
    return queries


def is_obsidian_vault(corpus_dir: Path) -> bool:
    """Check whether a directory is an Obsidian vault.

    Args:
        corpus_dir: Directory to check.

    Returns:
        True if the directory contains a .obsidian/ subdirectory.
    """
    return (corpus_dir / ".obsidian").is_dir()


def compute_corpus_hash(corpus_dir: Path) -> str:
    """Compute a sha256 hash for a corpus directory.

    Includes relative file paths and file bytes, sorted for determinism.

    Args:
        corpus_dir: Root directory of the corpus.

    Returns:
        Hash string prefixed with 'sha256:'.
    """
    files = sorted(p for p in corpus_dir.rglob("*") if p.is_file())
    digest = hashlib.sha256()
    for file_path in files:
        relative = file_path.relative_to(corpus_dir).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


# ---------------------------------------------------------------------------
# Git metadata
# ---------------------------------------------------------------------------

def collect_git_metadata(repo_root: Path) -> dict[str, Any]:
    """Collect git commit, branch, and dirty state.

    Args:
        repo_root: Repository root directory.

    Returns:
        Dict with keys: commit, branch, dirty.
    """
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root, capture_output=True, text=True, check=True,
        ).stdout.strip()
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root, capture_output=True, text=True, check=True,
        ).stdout.strip()
        dirty_rc = subprocess.run(
            ["git", "diff", "--quiet"],
            cwd=repo_root, capture_output=True, check=False,
        ).returncode
        return {"commit": commit, "branch": branch, "dirty": dirty_rc != 0}
    except Exception as exc:
        logger.warning(f"Failed to collect git metadata: {exc}")
        return {"commit": "unknown", "branch": "unknown", "dirty": False}


def detect_repo_root() -> Path:
    """Detect the repository root by walking up from this script's location.

    Returns:
        Path to the detected repo root, or cwd if detection fails.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return Path(result.stdout.strip())
    except Exception:
        return Path.cwd()


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

def ingest_vault(vault_path: Path, dataset_name: str) -> None:
    """Ingest an Obsidian vault using the DatasetIngestPipeline.

    Args:
        vault_path: Path to the Obsidian vault directory.
        dataset_name: Name for the ingested dataset.
    """
    from catalog.ingest.pipelines import DatasetIngestPipeline
    from catalog.integrations.obsidian.source import SourceObsidianConfig

    logger.info(f"Ingesting Obsidian vault: {vault_path} as dataset '{dataset_name}'")
    pipeline = DatasetIngestPipeline()
    config = SourceObsidianConfig(
        source_path=vault_path,
        dataset_name=dataset_name,
        force=True,
    )
    result = pipeline.ingest_dataset(config)
    logger.info(
        f"Ingestion complete: read={result.documents_read} "
        f"created={result.documents_created} updated={result.documents_updated} "
        f"skipped={result.documents_skipped} failed={result.documents_failed}"
    )
    if result.errors:
        for err in result.errors:
            logger.warning(f"Ingestion error: {err}")


def ingest_corpus_jsonl(corpus_dir: Path, dataset_name: str) -> None:
    """Ingest documents from a corpus.jsonl file.

    Reads line-delimited JSON, writes each document to a temporary directory
    as a markdown file, then ingests that directory via the directory source.

    Args:
        corpus_dir: Directory containing corpus.jsonl.
        dataset_name: Name for the ingested dataset.
    """
    from catalog.ingest import DatasetIngestPipeline
    from catalog.ingest.directory import SourceDirectoryConfig

    corpus_file = corpus_dir / "corpus.jsonl"
    if not corpus_file.exists():
        raise FileNotFoundError(f"corpus.jsonl not found in {corpus_dir}")

    # Write documents to a temp directory as markdown files for ingestion
    staging_dir = EVAL_TMP / "corpus_staging"
    if staging_dir.exists():
        import shutil
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)

    doc_count = 0
    with corpus_file.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            doc = json.loads(line)
            doc_id = doc.get("doc_id", f"doc_{doc_count}")
            body = doc.get("body", doc.get("text", doc.get("content", "")))
            title = doc.get("title", doc_id)
            frontmatter = doc.get("frontmatter", {})

            # Build markdown with frontmatter
            parts = ["---"]
            parts.append(f"title: {title}")
            for k, v in frontmatter.items():
                if k != "title":
                    parts.append(f"{k}: {v}")
            parts.append("---")
            parts.append("")
            parts.append(body)
            content = "\n".join(parts)

            # Use doc_id as filename, sanitizing for filesystem
            safe_name = doc_id.replace("/", "_").replace("\\", "_")
            if not safe_name.endswith(".md"):
                safe_name += ".md"
            (staging_dir / safe_name).write_text(content, encoding="utf-8")
            doc_count += 1

    logger.info(f"Staged {doc_count} documents from corpus.jsonl to {staging_dir}")

    # Ingest the staging directory via the directory source type
    config = SourceDirectoryConfig(
        source_path=staging_dir,
        dataset_name=dataset_name,
        force=True,
    )
    pipeline = DatasetIngestPipeline()
    result = pipeline.ingest_dataset(config)
    logger.info(
        f"Corpus ingestion complete: read={result.documents_read} "
        f"created={result.documents_created} updated={result.documents_updated} "
        f"failed={result.documents_failed}"
    )
    if result.errors:
        for err in result.errors:
            logger.warning(f"Ingestion error: {err}")


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

@dataclass
class QueryResult:
    """Results from running a single query in a single mode.

    Attributes:
        query: The query text.
        mode_label: Mode label (e.g. 'fts', 'hybrid_rerank').
        expected_docs: Ground-truth document list.
        difficulty: Difficulty tier.
        results: Ranked list of retrieved result dicts.
    """

    query: str
    mode_label: str
    expected_docs: list[str]
    difficulty: str
    results: list[dict[str, Any]]


def run_retrieval(
    queries: list[QueryDef],
    modes: list[ModeSpec],
    dataset_name: str,
    limit: int,
) -> list[QueryResult]:
    """Run retrieval for all queries across all modes.

    Creates a SearchService within a database session, then evaluates
    each (query, mode) combination.

    Args:
        queries: List of query definitions with expected docs.
        modes: List of mode specifications to evaluate.
        dataset_name: Dataset name to filter search results.
        limit: Maximum number of results per query.

    Returns:
        List of QueryResult objects, one per (query, mode) pair.
    """
    from catalog.search.models import SearchCriteria
    from catalog.search.service import SearchService
    from catalog.store.database import get_session
    from catalog.store.session_context import use_session

    all_results: list[QueryResult] = []

    with get_session() as session:
        with use_session(session):
            service = SearchService(session)

            for mode_spec in modes:
                logger.info(f"Running mode: {mode_spec.label}")
                errors = 0
                for qdef in queries:
                    criteria = SearchCriteria(
                        query=qdef.query,
                        mode=mode_spec.mode,
                        dataset_name=dataset_name,
                        limit=limit,
                        rerank=mode_spec.rerank,
                    )

                    result_dicts = []
                    try:
                        search_results = service.search(criteria)
                        for rank, sr in enumerate(search_results.results, start=1):
                            result_dicts.append({
                                "rank": rank,
                                "doc_id": sr.path,
                                "score": sr.score,
                                "scores": sr.scores,
                            })
                    except Exception as exc:
                        # Record the failure but continue the experiment.
                        # FTS5 in particular can reject certain query syntax.
                        logger.warning(
                            f"Query failed [{mode_spec.label}] "
                            f"'{qdef.query[:60]}': {type(exc).__name__}: {exc}"
                        )
                        errors += 1

                    all_results.append(QueryResult(
                        query=qdef.query,
                        mode_label=mode_spec.label,
                        expected_docs=qdef.expected_docs,
                        difficulty=qdef.difficulty,
                        results=result_dicts,
                    ))
                logger.info(
                    f"Completed mode {mode_spec.label}: "
                    f"{len(queries)} queries evaluated, {errors} errors"
                )

    return all_results


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _normalize_doc_id(doc_id: str) -> str:
    """Strip .md suffix from a doc_id for consistent matching.

    The staging step adds .md to filenames, but corpus queries reference
    bare doc_ids. This normalizes both sides for comparison.

    Args:
        doc_id: Raw document identifier.

    Returns:
        Normalized doc_id without .md suffix.
    """
    if doc_id.endswith(".md"):
        return doc_id[:-3]
    return doc_id


def compute_mrr(expected_docs: list[str], ranked_results: list[dict[str, Any]], k: int) -> float:
    """Compute Mean Reciprocal Rank at k for a single query.

    Finds the rank of the first expected document within the top-k results
    and returns 1/rank. Returns 0.0 if no expected doc is found.

    Args:
        expected_docs: List of expected document identifiers.
        ranked_results: Ranked list of result dicts with 'doc_id' keys.
        k: Cutoff rank.

    Returns:
        Reciprocal rank (1/rank) or 0.0 if no hit in top k.
    """
    expected_set = {_normalize_doc_id(d) for d in expected_docs}
    for result in ranked_results[:k]:
        if _normalize_doc_id(result["doc_id"]) in expected_set:
            return 1.0 / result["rank"]
    return 0.0


def compute_hit_at_k(expected_docs: list[str], ranked_results: list[dict[str, Any]], k: int) -> bool:
    """Check whether any expected doc appears in the top-k results.

    Args:
        expected_docs: List of expected document identifiers.
        ranked_results: Ranked list of result dicts with 'doc_id' keys.
        k: Cutoff rank.

    Returns:
        True if at least one expected doc appears in top k.
    """
    expected_set = {_normalize_doc_id(d) for d in expected_docs}
    top_k_ids = {_normalize_doc_id(r["doc_id"]) for r in ranked_results[:k]}
    return bool(expected_set & top_k_ids)


def aggregate_metrics(query_results: list[QueryResult], limit: int) -> dict[str, Any]:
    """Aggregate per-query results into metrics grouped by mode and difficulty.

    Computes hit@1, hit@3, hit@k (at limit), and MRR@k (at limit)
    for each (mode, difficulty) bucket.

    Args:
        query_results: All query results from retrieval.
        limit: The k value used for hit@k and MRR@k.

    Returns:
        Nested dict: by_mode -> mode_label -> difficulty -> metric_name -> value.
    """
    k_values = [1, 3, limit]
    # De-duplicate k_values while preserving order
    seen: set[int] = set()
    unique_k: list[int] = []
    for k in k_values:
        if k not in seen:
            unique_k.append(k)
            seen.add(k)

    # Group by (mode_label, difficulty)
    groups: dict[tuple[str, str], list[QueryResult]] = {}
    for qr in query_results:
        key = (qr.mode_label, qr.difficulty)
        groups.setdefault(key, []).append(qr)

    by_mode: dict[str, dict[str, dict[str, float]]] = {}

    for (mode_label, difficulty), group in groups.items():
        count = len(group)
        metrics: dict[str, float] = {"count": float(count)}

        for k in unique_k:
            hit_count = sum(
                1 for qr in group
                if compute_hit_at_k(qr.expected_docs, qr.results, k)
            )
            metrics[f"hit_at_{k}"] = hit_count / count if count > 0 else 0.0

        mrr_sum = sum(
            compute_mrr(qr.expected_docs, qr.results, limit)
            for qr in group
        )
        metrics[f"mrr_at_{limit}"] = mrr_sum / count if count > 0 else 0.0

        by_mode.setdefault(mode_label, {})[difficulty] = metrics

    return {"by_mode": by_mode}


# ---------------------------------------------------------------------------
# Artifact writers
# ---------------------------------------------------------------------------

def write_run_json(
    output_dir: Path,
    slug: str,
    timestamp: str,
    git_meta: dict[str, Any],
    corpus_dir: Path,
    corpus_hash: str,
    queries_path: Path,
    query_count: int,
    embedding_model: str,
    dataset_name: str,
    limit: int,
) -> None:
    """Write run.json execution metadata artifact.

    Args:
        output_dir: Output directory.
        slug: Experiment slug.
        timestamp: ISO 8601 timestamp.
        git_meta: Git metadata dict.
        corpus_dir: Path to the corpus directory.
        corpus_hash: SHA256 hash of the corpus.
        queries_path: Path to the queries file.
        query_count: Number of queries.
        embedding_model: Embedding model identifier.
        dataset_name: Dataset name used for ingestion.
        limit: Max results per query.
    """
    payload = {
        "slug": slug,
        "timestamp": timestamp,
        "git": git_meta,
        "corpus": {
            "path": str(corpus_dir.resolve()),
            "hash": corpus_hash,
        },
        "queries": {
            "path": str(queries_path.resolve()),
            "count": query_count,
        },
        "settings": {
            "embedding_model": embedding_model,
            "dataset_name": dataset_name,
            "limit": limit,
        },
        "modes": [m.label for m in ALL_MODES],
    }
    path = output_dir / "run.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    logger.info(f"Wrote {path}")


def write_results_jsonl(output_dir: Path, query_results: list[QueryResult]) -> None:
    """Write results.jsonl with per-query, per-mode results.

    Each line is a JSON object with query, mode, expected_docs, and results.

    Args:
        output_dir: Output directory.
        query_results: All query results from retrieval.
    """
    path = output_dir / "results.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for qr in query_results:
            line = {
                "query": qr.query,
                "mode": qr.mode_label,
                "difficulty": qr.difficulty,
                "expected_docs": qr.expected_docs,
                "results": qr.results,
            }
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")
    logger.info(f"Wrote {path} ({len(query_results)} entries)")


def write_metrics_json(output_dir: Path, metrics: dict[str, Any]) -> None:
    """Write metrics.json with aggregated metrics by mode and difficulty.

    Args:
        output_dir: Output directory.
        metrics: Aggregated metrics dict.
    """
    path = output_dir / "metrics.json"
    path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    logger.info(f"Wrote {path}")


def write_trace_jsonl(output_dir: Path, query_results: list[QueryResult]) -> None:
    """Write trace.jsonl with per-result rank traces and score components.

    Each line represents a single retrieved document with its rank,
    final score, component scores, and source channel ranks.

    Args:
        output_dir: Output directory.
        query_results: All query results from retrieval.
    """
    path = output_dir / "trace.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for qr in query_results:
            for result in qr.results:
                scores = result.get("scores", {})

                # Attempt to extract source channel ranks from score components
                source_channel_ranks = None
                if "fts" in scores or "vector" in scores or "rrf" in scores:
                    source_channel_ranks = {}
                    for channel in ("fts", "vector", "rrf", "rerank", "retrieval", "bonus"):
                        if channel in scores:
                            source_channel_ranks[channel] = scores[channel]

                trace_line = {
                    "query": qr.query,
                    "mode": qr.mode_label,
                    "rank": result["rank"],
                    "doc_id": result["doc_id"],
                    "score_final": result["score"],
                    "score_components": scores,
                    "source_channel_ranks": source_channel_ranks,
                }
                fh.write(json.dumps(trace_line, ensure_ascii=False) + "\n")
    logger.info(f"Wrote {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """Run a full retrieval experiment.

    Steps:
    1. Parse arguments and configure environment.
    2. Ingest corpus (Obsidian vault or corpus.jsonl).
    3. Load queries.
    4. Run retrieval across all modes.
    5. Compute metrics.
    6. Write output artifacts.

    Args:
        argv: Optional argument list (defaults to sys.argv).

    Returns:
        Exit code (0 for success).
    """
    args = parse_args(argv)
    configure_logging(level=args.log_level)

    corpus_dir: Path = args.corpus_dir.expanduser().resolve()
    output_dir: Path = args.output_dir.expanduser().resolve()
    repo_root: Path = (args.repo_root or detect_repo_root()).expanduser().resolve()

    output_dir.mkdir(parents=True, exist_ok=True)

    # -- Environment isolation --
    setup_isolated_env(args.embedding_model)

    # -- Resolve queries file --
    if args.queries_file:
        queries_path = args.queries_file.expanduser().resolve()
    else:
        queries_path = detect_queries_file(corpus_dir)

    queries = load_queries(queries_path)
    if not queries:
        logger.error("No queries loaded. Aborting.")
        return 1

    # -- Corpus hash --
    logger.info("Computing corpus hash...")
    corpus_hash = compute_corpus_hash(corpus_dir)
    logger.info(f"Corpus hash: {corpus_hash}")

    # -- Git metadata --
    git_meta = collect_git_metadata(repo_root)

    # -- Timestamp --
    run_time = datetime.now(timezone.utc)
    timestamp = run_time.isoformat()

    # -- Write run.json early (before potentially long ingestion) --
    write_run_json(
        output_dir=output_dir,
        slug=args.slug,
        timestamp=timestamp,
        git_meta=git_meta,
        corpus_dir=corpus_dir,
        corpus_hash=corpus_hash,
        queries_path=queries_path,
        query_count=len(queries),
        embedding_model=args.embedding_model,
        dataset_name=args.dataset_name,
        limit=args.limit,
    )

    # -- Ingestion --
    t0 = time.perf_counter()
    if is_obsidian_vault(corpus_dir):
        logger.info("Detected Obsidian vault -- ingesting directly.")
        ingest_vault(corpus_dir, args.dataset_name)
    elif (corpus_dir / "corpus.jsonl").exists():
        logger.info("Detected corpus.jsonl -- staging and ingesting.")
        ingest_corpus_jsonl(corpus_dir, args.dataset_name)
    else:
        logger.error(
            f"Cannot determine corpus type for {corpus_dir}. "
            f"Expected either an Obsidian vault (.obsidian/) or corpus.jsonl."
        )
        return 1
    ingest_elapsed = time.perf_counter() - t0
    logger.info(f"Ingestion completed in {ingest_elapsed:.1f}s")

    # -- Retrieval across modes --
    t0 = time.perf_counter()
    query_results = run_retrieval(
        queries=queries,
        modes=ALL_MODES,
        dataset_name=args.dataset_name,
        limit=args.limit,
    )
    retrieval_elapsed = time.perf_counter() - t0
    logger.info(f"Retrieval completed in {retrieval_elapsed:.1f}s ({len(query_results)} query-mode pairs)")

    # -- Metrics --
    metrics = aggregate_metrics(query_results, limit=args.limit)

    # -- Write artifacts --
    write_results_jsonl(output_dir, query_results)
    write_metrics_json(output_dir, metrics)
    write_trace_jsonl(output_dir, query_results)

    # -- Summary --
    print(f"\nExperiment '{args.slug}' complete.")
    print(f"  Corpus:    {corpus_dir}")
    print(f"  Queries:   {len(queries)}")
    print(f"  Modes:     {', '.join(m.label for m in ALL_MODES)}")
    print(f"  Artifacts: {output_dir}")
    print()

    for mode_label, difficulties in metrics["by_mode"].items():
        for diff, m in difficulties.items():
            hit1 = m.get("hit_at_1", 0.0)
            hit3 = m.get("hit_at_3", 0.0)
            mrr = m.get(f"mrr_at_{args.limit}", 0.0)
            count = int(m.get("count", 0))
            print(f"  {mode_label:16s} [{diff:8s}] hit@1={hit1:.2f}  hit@3={hit3:.2f}  mrr@{args.limit}={mrr:.2f}  (n={count})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
