"""Search evaluation harness utilities.

This module orchestrates reproducible golden-query evaluation runs and
normalizes run metadata into a JSON-serializable record format.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentlayer.logging import get_logger

from catalog.core.settings import get_settings

logger = get_logger(__name__)

DEFAULT_FTS_IMPL = "sqlite_fts5"


@dataclass
class GitMetadata:
    """Minimal git metadata for an eval run record."""

    commit: str
    branch: str
    dirty: bool


def compute_corpus_hash(corpus_path: Path) -> str:
    """Compute a stable sha256 hash for a corpus directory.

    The hash includes relative file paths and file bytes for all files in the
    corpus tree. Paths are sorted to ensure deterministic output.
    """

    if not corpus_path.exists():
        raise FileNotFoundError(f"Corpus path does not exist: {corpus_path}")

    if corpus_path.is_file():
        files = [corpus_path]
        root = corpus_path.parent
    else:
        files = sorted(path for path in corpus_path.rglob("*") if path.is_file())
        root = corpus_path

    digest = hashlib.sha256()
    for file_path in files:
        relative_path = file_path.relative_to(root).as_posix()
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_path.read_bytes())
        digest.update(b"\0")

    return f"sha256:{digest.hexdigest()}"


def read_queries_version(queries_file: Path) -> str:
    """Read golden query version from JSON.

    Returns ``"unversioned"`` when no explicit ``version`` key is present.
    """

    payload = json.loads(queries_file.read_text())
    if isinstance(payload, dict):
        version = payload.get("version")
        if isinstance(version, str) and version.strip():
            return version
    return "unversioned"


def read_eval_metrics(stdout: str) -> dict[str, Any]:
    """Parse evaluation metrics JSON emitted by ``catalog eval golden``.

    The eval CLI may print informational lines before the JSON payload. This
    parser extracts the last JSON object from stdout.
    """

    lines = [line for line in stdout.splitlines() if line.strip()]
    for start in range(len(lines)):
        candidate = "\n".join(lines[start:])
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
        raise ValueError("Expected eval JSON object")

    raise ValueError("Unable to parse eval JSON output")


def collect_git_metadata(repo_root: Path) -> GitMetadata:
    """Collect commit, branch, and dirty state for the run record."""

    commit = _run_git(repo_root, ["rev-parse", "HEAD"])
    branch = _run_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    dirty_exit = subprocess.run(
        ["git", "diff", "--quiet"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    ).returncode
    return GitMetadata(commit=commit, branch=branch, dirty=(dirty_exit != 0))


def build_run_record(
    *,
    corpus_path: Path,
    queries_file: Path,
    embedding_model: str,
    metrics: dict[str, Any],
    fts_impl: str = DEFAULT_FTS_IMPL,
    run_time: datetime | None = None,
    repo_root: Path,
) -> dict[str, Any]:
    """Build a canonical run record envelope for search evals."""

    now = run_time or datetime.now(timezone.utc)
    settings = get_settings()
    git_meta = collect_git_metadata(repo_root)

    rag_v2 = settings.rag_v2
    run_record = {
        "run_id": now.isoformat(),
        "git": asdict(git_meta),
        "corpus": {
            "path": str(corpus_path.resolve()),
            "hash": compute_corpus_hash(corpus_path),
        },
        "queries": {
            "path": str(queries_file.resolve()),
            "version": read_queries_version(queries_file),
        },
        "settings": {
            "embedding_model": embedding_model,
            "fts_impl": fts_impl,
            "rag_v2": {
                "chunk_size": rag_v2.chunk_size,
                "chunk_overlap": rag_v2.chunk_overlap,
                "rrf_k": rag_v2.rrf_k,
                "rerank_enabled": rag_v2.rerank_enabled,
                "expansion_enabled": rag_v2.expansion_enabled,
            },
        },
        "metrics": metrics,
    }
    return run_record


def baseline_key(run_record: dict[str, Any]) -> str:
    """Build deterministic baseline key from run metadata."""

    settings = run_record["settings"]
    rag_v2 = settings["rag_v2"]
    return "__".join(
        [
            run_record["corpus"]["hash"],
            run_record["queries"]["version"],
            settings["embedding_model"],
            settings["fts_impl"],
            f"chunk_size={rag_v2['chunk_size']}",
            f"chunk_overlap={rag_v2['chunk_overlap']}",
            f"rrf_k={rag_v2['rrf_k']}",
            f"rerank={int(rag_v2['rerank_enabled'])}",
            f"expand={int(rag_v2['expansion_enabled'])}",
        ]
    )


def prepare_eval_environment(
    *,
    catalog_db_path: Path,
    content_db_path: Path,
    vector_store_path: Path,
    embedding_model: str,
) -> dict[str, str]:
    """Prepare environment variables for isolated eval execution."""

    env = os.environ.copy()
    env.update(
        {
            "SUBSTRATE_DATABASES__CATALOG_PATH": str(catalog_db_path),
            "SUBSTRATE_DATABASES__CONTENT_PATH": str(content_db_path),
            "SUBSTRATE_VECTOR_STORE_PATH": str(vector_store_path),
            "SUBSTRATE_EMBEDDING_MODEL": embedding_model,
        }
    )
    return env


def _run_git(repo_root: Path, args: list[str]) -> str:
    """Run a git command and return stdout stripped."""

    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()
