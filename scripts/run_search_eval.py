"""Run a reproducible search eval and emit a run record JSON artifact."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from catalog.eval.harness import (
    baseline_key,
    build_run_record,
    prepare_eval_environment,
    read_eval_metrics,
)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for eval harness execution."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True, help="Path to fixed eval corpus")
    parser.add_argument(
        "--queries-file",
        type=Path,
        required=True,
        help="Path to golden queries JSON",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/evals"),
        help="Directory where run record artifacts are written",
    )
    parser.add_argument(
        "--dataset-name",
        default="eval-vault",
        help="Dataset name used during ingestion",
    )
    parser.add_argument(
        "--embedding-model",
        default="mlx-community/all-MiniLM-L6-v2-bf16",
        help="Embedding model identifier for eval run",
    )
    parser.add_argument(
        "--catalog-db-path",
        type=Path,
        default=Path("/tmp/catalog-eval/catalog.db"),
        help="Isolated catalog DB path",
    )
    parser.add_argument(
        "--content-db-path",
        type=Path,
        default=Path("/tmp/catalog-eval/content.db"),
        help="Isolated content DB path",
    )
    parser.add_argument(
        "--vector-store-path",
        type=Path,
        default=Path("/tmp/catalog-eval/vectors"),
        help="Isolated vector store path",
    )
    parser.add_argument(
        "--baseline-dir",
        type=Path,
        default=Path("reports/evals/baselines"),
        help="Directory containing baseline run records",
    )
    parser.add_argument(
        "--compare-baseline",
        action="store_true",
        help="Fail if no baseline exists for current config",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Repository root for git metadata collection",
    )
    return parser.parse_args()


def run() -> int:
    """Execute ingest + eval flow and persist run record artifact."""

    args = parse_args()
    env = prepare_eval_environment(
        catalog_db_path=args.catalog_db_path,
        content_db_path=args.content_db_path,
        vector_store_path=args.vector_store_path,
        embedding_model=args.embedding_model,
    )

    args.catalog_db_path.parent.mkdir(parents=True, exist_ok=True)
    args.content_db_path.parent.mkdir(parents=True, exist_ok=True)
    args.vector_store_path.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            "uv",
            "run",
            "python",
            "scripts/ingest_obsidian_vault.py",
            str(args.corpus),
            "--dataset-name",
            args.dataset_name,
        ],
        env=env,
        check=True,
    )

    eval_run = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "catalog",
            "eval",
            "golden",
            "--queries-file",
            str(args.queries_file),
            "--output",
            "json",
        ],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    metrics = read_eval_metrics(eval_run.stdout)
    run_time = datetime.now(timezone.utc)
    run_record = build_run_record(
        corpus_path=args.corpus,
        queries_file=args.queries_file,
        embedding_model=args.embedding_model,
        metrics=metrics,
        run_time=run_time,
        repo_root=args.repo_root,
    )

    day_dir = args.output_dir / run_time.strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    output_path = day_dir / f"{run_time.strftime('%Y-%m-%dT%H-%M-%SZ')}.json"
    output_path.write_text(json.dumps(run_record, indent=2))

    baseline_id = baseline_key(run_record)
    baseline_path = args.baseline_dir / f"{baseline_id}.json"

    if args.compare_baseline and not baseline_path.exists():
        raise FileNotFoundError(
            f"Baseline not found for current config. Expected: {baseline_path}"
        )

    print(f"Run record written: {output_path}")
    print(f"Baseline key: {baseline_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
