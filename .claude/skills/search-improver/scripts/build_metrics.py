# /// script
# dependencies = []
# ///
"""Post-process experiment artifacts to compute enriched retrieval metrics.

Reads results.jsonl, trace.jsonl, and metrics.json produced by run_experiment.py,
then computes additional metrics (nDCG@k, heading-dominance rate) and merges them
into the existing artifacts.

Usage:
    uv run python build_metrics.py --experiment-dir /path/to/experiment/output
    uv run python build_metrics.py --experiment-dir /path/to/output --k 5
    uv run python build_metrics.py summary --experiment-dir /path/to/output
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentlayer.logging import configure_logging, get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class ResultEntry:
    """A single row from results.jsonl.

    Attributes:
        query: The search query text.
        mode: Retrieval mode label.
        expected_docs: Ground-truth document identifiers.
        difficulty: Difficulty tier (easy/medium/hard/fusion).
        results: Ranked list of result dicts with rank, doc_id, score, scores.
    """

    query: str
    mode: str
    expected_docs: list[str]
    difficulty: str
    results: list[dict[str, Any]]


@dataclass
class TraceEntry:
    """A single row from trace.jsonl.

    Attributes:
        query: The search query text.
        mode: Retrieval mode label.
        rank: Result rank (1-based).
        doc_id: Document identifier.
        score_final: Final combined score.
        score_components: Dict of component scores by channel.
        source_channel_ranks: Dict of per-channel rank/score info.
    """

    query: str
    mode: str
    rank: int
    doc_id: str
    score_final: float
    score_components: dict[str, Any]
    source_channel_ranks: dict[str, Any] | None


@dataclass
class BucketMetrics:
    """Accumulated metrics for a (mode, difficulty) bucket.

    Attributes:
        mode: Retrieval mode label.
        difficulty: Difficulty tier.
        ndcg_values: Per-query nDCG@k values.
        heading_dominated_count: Number of top-k results flagged as heading-dominated.
        total_result_count: Total number of top-k results in this bucket.
    """

    mode: str
    difficulty: str
    ndcg_values: list[float] = field(default_factory=list)
    heading_dominated_count: int = 0
    total_result_count: int = 0


# ---------------------------------------------------------------------------
# nDCG computation
# ---------------------------------------------------------------------------

def compute_dcg(relevances: list[float], k: int) -> float:
    """Compute Discounted Cumulative Gain at k.

    Args:
        relevances: Ordered list of relevance values for ranked results.
        k: Cutoff rank.

    Returns:
        DCG@k value.
    """
    dcg = 0.0
    for i, rel in enumerate(relevances[:k]):
        dcg += rel / math.log2(i + 2)  # i+2 because rank is 1-based (log2(1+1), log2(2+1), ...)
    return dcg


def _normalize_doc_id(doc_id: str) -> str:
    """Strip .md suffix from a doc_id for consistent matching."""
    if doc_id.endswith(".md"):
        return doc_id[:-3]
    return doc_id


def compute_ndcg(expected_docs: list[str], ranked_results: list[dict[str, Any]], k: int) -> float:
    """Compute normalized Discounted Cumulative Gain at k.

    Uses binary relevance: rel=1 if doc_id is in expected_docs, else 0.

    Args:
        expected_docs: List of relevant document identifiers.
        ranked_results: Ranked list of result dicts with 'doc_id' keys.
        k: Cutoff rank.

    Returns:
        nDCG@k value in [0, 1]. Returns 0.0 if no relevant docs exist.
    """
    expected_set = {_normalize_doc_id(d) for d in expected_docs}
    relevances = [1.0 if _normalize_doc_id(r["doc_id"]) in expected_set else 0.0 for r in ranked_results[:k]]

    dcg = compute_dcg(relevances, k)

    # Ideal ranking: all relevant docs first
    num_relevant = min(len(expected_set), k)
    ideal_relevances = [1.0] * num_relevant + [0.0] * (k - num_relevant)
    idcg = compute_dcg(ideal_relevances, k)

    if idcg == 0.0:
        return 0.0
    return dcg / idcg


# ---------------------------------------------------------------------------
# Heading dominance detection
# ---------------------------------------------------------------------------

def is_heading_dominated(
    result: dict[str, Any],
    mode: str,
    heading_threshold: float,
) -> bool:
    """Determine whether a result is heading-dominated.

    A result is heading-dominated if the FTS or retrieval channel contributes
    more than heading_threshold fraction of the total final score, suggesting
    the match is driven by heading/title content rather than body semantics.

    For pure FTS mode, all results are considered heading-dominated by default
    since FTS inherently favors short, keyword-dense text like headings.

    Args:
        result: A result dict with score, scores fields.
        mode: The retrieval mode label.
        heading_threshold: Fraction threshold above which a channel is dominant.

    Returns:
        True if the result appears heading-dominated.
    """
    scores = result.get("scores", {})
    if not scores:
        # No component scores available; for FTS mode assume heading-dominated
        return mode == "fts"

    total_score = result.get("score", 0.0)
    if total_score <= 0.0:
        return False

    # Check if FTS or retrieval channel dominates
    fts_score = scores.get("fts", 0.0)
    retrieval_score = scores.get("retrieval", 0.0)
    dominant_channel_score = max(fts_score, retrieval_score)

    return (dominant_channel_score / total_score) >= heading_threshold


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_results(experiment_dir: Path) -> list[ResultEntry]:
    """Load result entries from results.jsonl.

    Args:
        experiment_dir: Directory containing experiment artifacts.

    Returns:
        List of ResultEntry instances.

    Raises:
        FileNotFoundError: If results.jsonl does not exist.
    """
    path = experiment_dir / "results.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"results.jsonl not found in {experiment_dir}")

    entries = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            entries.append(ResultEntry(
                query=raw["query"],
                mode=raw["mode"],
                expected_docs=raw["expected_docs"],
                difficulty=raw.get("difficulty", "medium"),
                results=raw.get("results", []),
            ))
    logger.info(f"Loaded {len(entries)} result entries from {path}")
    return entries


def load_trace(experiment_dir: Path) -> list[TraceEntry]:
    """Load trace entries from trace.jsonl.

    Args:
        experiment_dir: Directory containing experiment artifacts.

    Returns:
        List of TraceEntry instances. Empty list if file does not exist.
    """
    path = experiment_dir / "trace.jsonl"
    if not path.exists():
        logger.warning(f"trace.jsonl not found in {experiment_dir}, skipping trace enrichment")
        return []

    entries = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            entries.append(TraceEntry(
                query=raw["query"],
                mode=raw["mode"],
                rank=raw["rank"],
                doc_id=raw["doc_id"],
                score_final=raw.get("score_final", 0.0),
                score_components=raw.get("score_components", {}),
                source_channel_ranks=raw.get("source_channel_ranks"),
            ))
    logger.info(f"Loaded {len(entries)} trace entries from {path}")
    return entries


def load_metrics(experiment_dir: Path) -> dict[str, Any]:
    """Load existing metrics.json.

    Args:
        experiment_dir: Directory containing experiment artifacts.

    Returns:
        Existing metrics dict, or empty structure if file does not exist.
    """
    path = experiment_dir / "metrics.json"
    if not path.exists():
        logger.warning(f"metrics.json not found in {experiment_dir}, starting fresh")
        return {"by_mode": {}}

    raw = json.loads(path.read_text(encoding="utf-8"))
    logger.info(f"Loaded existing metrics from {path}")
    return raw


# ---------------------------------------------------------------------------
# Enrichment
# ---------------------------------------------------------------------------

def compute_enriched_metrics(
    results: list[ResultEntry],
    k: int,
    heading_threshold: float,
) -> dict[str, dict[str, dict[str, float]]]:
    """Compute nDCG@k and heading-dominance rate per (mode, difficulty) bucket.

    Args:
        results: Loaded result entries from results.jsonl.
        k: Cutoff rank for metrics.
        heading_threshold: Threshold for heading-dominance detection.

    Returns:
        Nested dict: mode -> difficulty -> {ndcg_at_k, heading_dominance_rate}.
    """
    buckets: dict[tuple[str, str], BucketMetrics] = {}

    for entry in results:
        key = (entry.mode, entry.difficulty)
        if key not in buckets:
            buckets[key] = BucketMetrics(mode=entry.mode, difficulty=entry.difficulty)
        bucket = buckets[key]

        # nDCG@k
        ndcg = compute_ndcg(entry.expected_docs, entry.results, k)
        bucket.ndcg_values.append(ndcg)

        # Heading dominance per result in top-k
        for result in entry.results[:k]:
            bucket.total_result_count += 1
            if is_heading_dominated(result, entry.mode, heading_threshold):
                bucket.heading_dominated_count += 1

    # Aggregate per bucket
    enriched: dict[str, dict[str, dict[str, float]]] = {}
    for (mode, difficulty), bucket in buckets.items():
        avg_ndcg = (
            sum(bucket.ndcg_values) / len(bucket.ndcg_values)
            if bucket.ndcg_values
            else 0.0
        )
        heading_rate = (
            bucket.heading_dominated_count / bucket.total_result_count
            if bucket.total_result_count > 0
            else 0.0
        )
        enriched.setdefault(mode, {})[difficulty] = {
            f"ndcg_at_{k}": round(avg_ndcg, 6),
            "heading_dominance_rate": round(heading_rate, 6),
        }

    return enriched


def merge_metrics(
    existing: dict[str, Any],
    enriched: dict[str, dict[str, dict[str, float]]],
) -> dict[str, Any]:
    """Merge enriched metrics into existing metrics.json structure.

    Adds ndcg_at_k and heading_dominance_rate fields to each (mode, difficulty)
    bucket without removing existing fields.

    Args:
        existing: The current metrics.json content.
        enriched: Newly computed metrics keyed by mode -> difficulty -> metric.

    Returns:
        Updated metrics dict with enriched fields merged in.
    """
    by_mode = existing.setdefault("by_mode", {})

    for mode, difficulties in enriched.items():
        mode_dict = by_mode.setdefault(mode, {})
        for difficulty, new_metrics in difficulties.items():
            diff_dict = mode_dict.setdefault(difficulty, {})
            diff_dict.update(new_metrics)

    return existing


# ---------------------------------------------------------------------------
# Subcommand: enrich
# ---------------------------------------------------------------------------

def cmd_enrich(experiment_dir: Path, k: int, heading_threshold: float) -> int:
    """Run the enrich subcommand.

    Loads results.jsonl and existing metrics.json, computes nDCG@k and
    heading-dominance rate, then writes the updated metrics.json.

    Args:
        experiment_dir: Directory containing experiment artifacts.
        k: Cutoff rank for metrics.
        heading_threshold: Threshold for heading-dominance detection.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    try:
        results = load_results(experiment_dir)
    except FileNotFoundError as exc:
        logger.error(str(exc))
        return 1

    existing_metrics = load_metrics(experiment_dir)

    enriched = compute_enriched_metrics(results, k, heading_threshold)
    merged = merge_metrics(existing_metrics, enriched)

    # Write updated metrics.json
    metrics_path = experiment_dir / "metrics.json"
    metrics_path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    logger.info(f"Wrote enriched metrics to {metrics_path}")

    # Count what was added
    bucket_count = sum(len(diffs) for diffs in enriched.values())
    logger.info(f"Enriched {bucket_count} (mode, difficulty) buckets with ndcg_at_{k} and heading_dominance_rate")

    return 0


# ---------------------------------------------------------------------------
# Subcommand: summary
# ---------------------------------------------------------------------------

def cmd_summary(experiment_dir: Path) -> int:
    """Print a human-readable summary table of all metrics.

    Args:
        experiment_dir: Directory containing experiment artifacts.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    metrics = load_metrics(experiment_dir)
    by_mode = metrics.get("by_mode", {})

    if not by_mode:
        print("No metrics found.")
        return 0

    # Collect all metric keys across all buckets for column headers
    all_metric_keys: set[str] = set()
    for difficulties in by_mode.values():
        for bucket in difficulties.values():
            all_metric_keys.update(bucket.keys())

    # Sort keys for deterministic output; put count last
    sorted_keys = sorted(k for k in all_metric_keys if k != "count")
    sorted_keys.append("count")

    # Header
    mode_col_w = 18
    diff_col_w = 10
    val_col_w = 12

    header_parts = [f"{'Mode':<{mode_col_w}}", f"{'Difficulty':<{diff_col_w}}"]
    for key in sorted_keys:
        header_parts.append(f"{key:>{val_col_w}}")
    header = "  ".join(header_parts)
    print(header)
    print("-" * len(header))

    # Rows sorted by mode then difficulty
    for mode in sorted(by_mode.keys()):
        difficulties = by_mode[mode]
        for difficulty in sorted(difficulties.keys()):
            bucket = difficulties[difficulty]
            row_parts = [f"{mode:<{mode_col_w}}", f"{difficulty:<{diff_col_w}}"]
            for key in sorted_keys:
                val = bucket.get(key)
                if val is None:
                    row_parts.append(f"{'--':>{val_col_w}}")
                elif key == "count":
                    row_parts.append(f"{int(val):>{val_col_w}}")
                else:
                    row_parts.append(f"{val:>{val_col_w}.4f}")
            print("  ".join(row_parts))

    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Post-process experiment artifacts to compute enriched retrieval metrics. "
            "Reads results.jsonl and metrics.json from an experiment output directory "
            "and adds nDCG@k and heading-dominance rate."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommand")

    # -- enrich (default) ---------------------------------------------------
    enrich_cmd = subparsers.add_parser(
        "enrich",
        help="Compute additional metrics and merge into metrics.json.",
    )
    enrich_cmd.add_argument(
        "--experiment-dir",
        type=Path,
        required=True,
        help="Directory containing experiment output artifacts.",
    )
    enrich_cmd.add_argument(
        "--k",
        type=int,
        default=10,
        help="Cutoff rank for nDCG and heading-dominance computation (default: 10).",
    )
    enrich_cmd.add_argument(
        "--heading-threshold",
        type=float,
        default=0.7,
        help="Fraction threshold for heading-dominance detection (default: 0.7).",
    )
    enrich_cmd.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Log level (default: INFO).",
    )

    # -- summary ------------------------------------------------------------
    summary_cmd = subparsers.add_parser(
        "summary",
        help="Print a human-readable summary table of metrics.",
    )
    summary_cmd.add_argument(
        "--experiment-dir",
        type=Path,
        required=True,
        help="Directory containing experiment output artifacts.",
    )
    summary_cmd.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Log level (default: INFO).",
    )

    args = parser.parse_args(argv)

    # Default to enrich if no subcommand given but --experiment-dir is present
    if args.command is None:
        # Re-parse with enrich as default
        parser.set_defaults(command="enrich")
        enrich_cmd.parse_args(argv or sys.argv[1:], namespace=args)
        args.command = "enrich"

    return args


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """Entry point for build_metrics.

    Args:
        argv: Optional argument list (defaults to sys.argv).

    Returns:
        Exit code (0 for success).
    """
    args = parse_args(argv)
    configure_logging(level=args.log_level)

    experiment_dir: Path = args.experiment_dir.expanduser().resolve()

    if not experiment_dir.is_dir():
        logger.error(f"Experiment directory does not exist: {experiment_dir}")
        return 1

    if args.command == "enrich":
        return cmd_enrich(
            experiment_dir=experiment_dir,
            k=args.k,
            heading_threshold=args.heading_threshold,
        )
    elif args.command == "summary":
        return cmd_summary(experiment_dir=experiment_dir)
    else:
        logger.error(f"Unknown command: {args.command}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
