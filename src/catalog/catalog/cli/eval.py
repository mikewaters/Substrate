"""catalog.cli.eval - Evaluation CLI commands.

Provides CLI commands for running golden query evaluations.

Commands:
    golden: Run golden query evaluation against thresholds

Example usage:
    # Run golden query evaluation
    uv run python -m catalog eval golden
"""

import json
from typing import Annotated

import typer

from agentlayer.logging import get_logger

__all__ = ["eval_app"]

logger = get_logger(__name__)

eval_app = typer.Typer(
    name="eval",
    help="Evaluation commands for RAG search quality.",
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
    ] = "tests/rag/fixtures/golden_queries.json",
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
    from catalog.search.service import SearchService
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
            service = SearchService(session)
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


