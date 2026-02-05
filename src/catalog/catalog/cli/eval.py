"""catalog.cli.eval - Evaluation CLI commands.

Provides CLI commands for running golden query evaluations and
comparing v1/v2 search results.

Commands:
    golden: Run golden query evaluation against thresholds
    compare: Compare v1 and v2 results for a single query
    compare-batch: Compare v1 and v2 on multiple queries from file

Example usage:
    # Run golden query evaluation
    uv run python -m catalog eval golden

    # Compare single query
    uv run python -m catalog eval compare "authentication configuration"

    # Batch comparison
    uv run python -m catalog eval compare-batch queries.txt --output summary
"""

import json
from pathlib import Path
from typing import Annotated

import typer

from agentlayer.logging import get_logger

__all__ = ["eval_app"]

logger = get_logger(__name__)

eval_app = typer.Typer(
    name="eval",
    help="Evaluation commands for RAG v2 search quality.",
)


@eval_app.command()
def golden(
    queries_file: Annotated[
        str,
        typer.Option(
            "--queries-file",
            "-f",
            help="Path to golden queries JSON file.",
        ),
    ] = "tests/rag_v2/fixtures/golden_queries.json",
    output: Annotated[
        str,
        typer.Option(
            "--output",
            "-o",
            help="Output format: json or table.",
        ),
    ] = "json",
    check_thresholds: Annotated[
        bool,
        typer.Option(
            "--check",
            "-c",
            help="Check results against thresholds and exit with error if failed.",
        ),
    ] = False,
) -> None:
    """Run golden query evaluation.

    Evaluates search quality against a set of golden (ground truth) queries.
    Results are grouped by retriever type (bm25, vector, hybrid) and
    difficulty level (easy, medium, hard, fusion).
    """
    from catalog.eval.golden import (
        EVAL_THRESHOLDS,
        evaluate_golden_queries,
        load_golden_queries,
    )
    from catalog.search.service_v2 import SearchServiceV2
    from catalog.store.database import get_session
    from catalog.store.session_context import use_session

    # Load golden queries
    try:
        queries = load_golden_queries(queries_file)
        typer.echo(f"Loaded {len(queries)} golden queries from {queries_file}")
    except FileNotFoundError:
        typer.echo(f"Error: File not found: {queries_file}", err=True)
        raise typer.Exit(1)
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        typer.echo(f"Error: Invalid golden queries file: {e}", err=True)
        raise typer.Exit(1)

    # Run evaluation
    with get_session() as session:
        with use_session(session):
            service = SearchServiceV2(session)
            results = evaluate_golden_queries(service, queries)

    # Output results
    if output == "json":
        typer.echo(json.dumps(results, indent=2))
    else:
        _print_table(results)

    # Check against thresholds if requested
    if check_thresholds:
        failures = _check_against_thresholds(results, EVAL_THRESHOLDS)
        if failures:
            typer.echo("\nThreshold failures:", err=True)
            for failure in failures:
                typer.echo(f"  {failure}", err=True)
            raise typer.Exit(1)
        else:
            typer.echo("\nAll thresholds passed!")


@eval_app.command()
def compare(
    query: Annotated[
        str,
        typer.Argument(help="Search query to compare."),
    ],
    dataset: Annotated[
        str | None,
        typer.Option(
            "--dataset",
            "-d",
            help="Optional dataset filter.",
        ),
    ] = None,
    mode: Annotated[
        str,
        typer.Option(
            "--mode",
            "-m",
            help="Search mode: fts, vector, or hybrid.",
        ),
    ] = "hybrid",
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-l",
            help="Maximum results to return.",
        ),
    ] = 10,
) -> None:
    """Compare v1 and v2 results for a single query.

    Runs the query against both SearchService (v1) and SearchServiceV2 (v2),
    then displays timing and overlap metrics.
    """
    from catalog.search.comparison import SearchComparison
    from catalog.search.models import SearchCriteria
    from catalog.store.database import get_session
    from catalog.store.session_context import use_session

    with get_session() as session:
        with use_session(session):
            comparison = SearchComparison(session)
            criteria = SearchCriteria(
                query=query,
                mode=mode,  # type: ignore
                limit=limit,
                dataset_name=dataset,
            )
            result = comparison.compare(criteria)
            _print_comparison(result)


@eval_app.command("compare-batch")
def compare_batch(
    queries_file: Annotated[
        str,
        typer.Argument(help="Path to file with queries (one per line or JSON array)."),
    ],
    output: Annotated[
        str,
        typer.Option(
            "--output",
            "-o",
            help="Output format: summary or detailed.",
        ),
    ] = "summary",
    mode: Annotated[
        str,
        typer.Option(
            "--mode",
            "-m",
            help="Search mode: fts, vector, or hybrid.",
        ),
    ] = "hybrid",
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-l",
            help="Maximum results per query.",
        ),
    ] = 10,
    dataset: Annotated[
        str | None,
        typer.Option(
            "--dataset",
            "-d",
            help="Optional dataset filter.",
        ),
    ] = None,
) -> None:
    """Compare v1 and v2 on multiple queries.

    Reads queries from a file (one per line, or JSON array) and runs
    side-by-side comparison for each. Outputs either a summary report
    or detailed results for each query.
    """
    from catalog.search.comparison import SearchComparison
    from catalog.store.database import get_session
    from catalog.store.session_context import use_session

    # Load queries from file
    queries = _load_queries(queries_file)
    if not queries:
        typer.echo(f"Error: No queries found in {queries_file}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Loaded {len(queries)} queries from {queries_file}")

    # Run comparisons
    with get_session() as session:
        with use_session(session):
            comparison = SearchComparison(session)
            results = comparison.compare_batch(
                queries=queries,
                mode=mode,
                limit=limit,
                dataset_name=dataset,
            )

            if output == "summary":
                summary = comparison.summary_report(results)
                typer.echo(json.dumps(summary, indent=2))
            else:
                for i, result in enumerate(results, 1):
                    typer.echo(f"\n--- Query {i}/{len(results)} ---")
                    _print_comparison(result)


def _print_table(results: dict[str, dict[str, dict[str, float]]]) -> None:
    """Print evaluation results as a formatted table."""
    typer.echo("\nEvaluation Results")
    typer.echo("=" * 80)

    for retriever_type, difficulties in sorted(results.items()):
        typer.echo(f"\n{retriever_type.upper()}")
        typer.echo("-" * 60)
        typer.echo(
            f"{'Difficulty':<12} {'Hit@1':>8} {'Hit@3':>8} {'Hit@5':>8} {'Hit@10':>8} {'Count':>8}"
        )
        typer.echo("-" * 60)

        for difficulty, metrics in sorted(difficulties.items()):
            hit_1 = metrics.get("hit_at_1", 0.0)
            hit_3 = metrics.get("hit_at_3", 0.0)
            hit_5 = metrics.get("hit_at_5", 0.0)
            hit_10 = metrics.get("hit_at_10", 0.0)
            count = int(metrics.get("count", 0))

            typer.echo(
                f"{difficulty:<12} {hit_1:>7.1%} {hit_3:>7.1%} "
                f"{hit_5:>7.1%} {hit_10:>7.1%} {count:>8}"
            )


def _check_against_thresholds(
    results: dict[str, dict[str, dict[str, float]]],
    thresholds: dict[str, dict[str, dict[str, float]]],
) -> list[str]:
    """Check results against thresholds and return list of failures."""
    failures = []

    for retriever_type, difficulties in results.items():
        if retriever_type not in thresholds:
            continue

        for difficulty, metrics in difficulties.items():
            if difficulty not in thresholds[retriever_type]:
                continue

            threshold_metrics = thresholds[retriever_type][difficulty]
            for metric_name, threshold in threshold_metrics.items():
                actual = metrics.get(metric_name, 0.0)
                if actual < threshold:
                    failures.append(
                        f"{retriever_type}/{difficulty}/{metric_name}: "
                        f"{actual:.1%} < {threshold:.1%}"
                    )

    return failures


def _print_comparison(result) -> None:
    """Print a single comparison result."""
    typer.echo(f"\nQuery: {result.query}")
    typer.echo("-" * 60)
    typer.echo(f"V1 time: {result.v1_time_ms:.1f}ms")
    typer.echo(f"V2 time: {result.v2_time_ms:.1f}ms")
    typer.echo(f"Overlap@5: {result.overlap_at_5:.1%}")
    typer.echo(f"Overlap@10: {result.overlap_at_10:.1%}")
    typer.echo(f"Rank correlation: {result.rank_correlation:.3f}")

    typer.echo(f"\nV1 results ({len(result.v1_results)}):")
    for i, r in enumerate(result.v1_results[:5], 1):
        typer.echo(f"  {i}. {r.dataset_name}:{r.path} (score: {r.score:.3f})")

    typer.echo(f"\nV2 results ({len(result.v2_results)}):")
    for i, r in enumerate(result.v2_results[:5], 1):
        typer.echo(f"  {i}. {r.dataset_name}:{r.path} (score: {r.score:.3f})")


def _load_queries(path: str) -> list[str]:
    """Load queries from a file.

    Supports both plain text (one query per line) and JSON array format.

    Args:
        path: Path to file containing queries.

    Returns:
        List of query strings.
    """
    file_path = Path(path)
    if not file_path.exists():
        typer.echo(f"Error: File not found: {path}", err=True)
        raise typer.Exit(1)

    content = file_path.read_text().strip()

    # Try JSON array first
    if content.startswith("["):
        try:
            data = json.loads(content)
            if isinstance(data, list):
                return [str(q) for q in data if q]
        except json.JSONDecodeError:
            pass

    # Fall back to line-by-line
    return [line.strip() for line in content.splitlines() if line.strip()]
