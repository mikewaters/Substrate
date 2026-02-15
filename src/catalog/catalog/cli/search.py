"""catalog.cli.search - Search CLI commands.

Provides CLI commands for exercising supported search methods.

Commands:
    methods: Run FTS, vector, hybrid, and hybrid+rerank for a query

Practical usage examples:
    # 1) Quick comparison across all search methods (table output)
    uv run python -m catalog search methods "python async patterns"

    # 2) JSON output for automation or piping to jq
    uv run python -m catalog search methods "oauth token refresh" --output json

    # 3) Restrict search to a specific dataset
    uv run python -m catalog search methods "meeting notes" --dataset obsidian

    # 4) Tune result size and rerank candidate pool
    uv run python -m catalog search methods "error handling" --limit 5 --rerank-candidates 30

Notes:
    - This command executes 4 strategies in one run: fts, vector, hybrid,
      and hybrid+rerank.
    - Use table output for fast inspection and json output for scripts.
"""

import json
from typing import Annotated, Any

import typer

from agentlayer.logging import get_logger

__all__ = ["search_app"]

logger = get_logger(__name__)

search_app = typer.Typer(
    name="search",
    help="Search commands for exercising retrieval methods.",
)


@search_app.command()
def methods(
    query: Annotated[
        str,
        typer.Argument(help="Search query to run across all methods."),
    ],
    dataset: Annotated[
        str | None,
        typer.Option(
            "--dataset",
            "-d",
            help="Optional dataset filter.",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-l",
            min=1,
            max=100,
            help="Maximum number of results per method.",
        ),
    ] = 10,
    rerank_candidates: Annotated[
        int,
        typer.Option(
            "--rerank-candidates",
            help="Candidates passed to LLM reranker for hybrid+rerank.",
            min=1,
            max=100,
        ),
    ] = 20,
    output: Annotated[
        str,
        typer.Option(
            "--output",
            "-o",
            help="Output format: json or table.",
        ),
    ] = "table",
) -> None:
    """Run and compare the documented search methods for a query.

    Executes the four methods documented in search-methods.md:
    - FTS (BM25)
    - Vector similarity
    - Hybrid (RRF)
    - Hybrid + rerank
    """
    from catalog.search.models import SearchCriteria
    from catalog.search.service import SearchService
    from catalog.store.database import get_session
    from catalog.store.session_context import use_session

    if output not in {"json", "table"}:
        typer.echo(f"Error: Invalid output format: {output}", err=True)
        raise typer.Exit(1)

    plan = [
        ("fts", SearchCriteria(query=query, mode="fts", dataset_name=dataset, limit=limit)),
        (
            "vector",
            SearchCriteria(query=query, mode="vector", dataset_name=dataset, limit=limit),
        ),
        (
            "hybrid",
            SearchCriteria(query=query, mode="hybrid", dataset_name=dataset, limit=limit),
        ),
        (
            "hybrid_rerank",
            SearchCriteria(
                query=query,
                mode="hybrid",
                dataset_name=dataset,
                limit=limit,
                rerank=True,
                rerank_candidates=rerank_candidates,
            ),
        ),
    ]

    results: dict[str, Any] = {
        "query": query,
        "dataset": dataset,
        "limit": limit,
        "rerank_candidates": rerank_candidates,
        "methods": {},
    }

    with get_session() as session:
        with use_session(session):
            service = SearchService(session)
            for method_name, criteria in plan:
                try:
                    search_results = service.search(criteria)
                    results["methods"][method_name] = {
                        "mode": criteria.mode,
                        "rerank": criteria.rerank,
                        "timing_ms": search_results.timing_ms,
                        "total_candidates": search_results.total_candidates,
                        "results": [r.model_dump() for r in search_results.results],
                    }
                except Exception as e:
                    logger.error(
                        f"search_methods_failed method={method_name} query={query!r} error={e}"
                    )
                    results["methods"][method_name] = {
                        "mode": criteria.mode,
                        "rerank": criteria.rerank,
                        "timing_ms": None,
                        "total_candidates": 0,
                        "results": [],
                        "error": str(e),
                    }

    if output == "json":
        typer.echo(json.dumps(results, indent=2))
    else:
        _print_methods_table(results)


def _print_methods_table(results: dict[str, Any]) -> None:
    """Print search method comparison as compact tables."""
    typer.echo("\nSearch Method Comparison")
    typer.echo("=" * 90)
    typer.echo(f"Query: {results['query']}")
    if results.get("dataset"):
        typer.echo(f"Dataset: {results['dataset']}")
    typer.echo()

    typer.echo(
        f"{'Method':<16} {'Mode':<8} {'Rerank':<8} {'Count':>7} {'Timing(ms)':>12} {'Status':>4}"
    )
    typer.echo("-" * 90)
    for method_name, payload in results["methods"].items():
        method_count = len(payload.get("results", []))
        timing = payload.get("timing_ms")
        timing_text = f"{timing:.1f}" if isinstance(timing, (int, float)) else "n/a"
        status = "ERR" if payload.get("error") else "OK"
        typer.echo(
            f"{method_name:<16} {payload.get('mode', ''):<8} "
            f"{str(payload.get('rerank', False)):<8} {method_count:>7} {timing_text:>12} {status:>4}"
        )

    typer.echo("\nTop results by method")
    typer.echo("-" * 90)
    for method_name, payload in results["methods"].items():
        typer.echo(f"\n{method_name.upper()}")
        if payload.get("error"):
            typer.echo(f"  Error: {payload['error']}")
            continue
        for idx, item in enumerate(payload.get("results", [])[:3], start=1):
            score = item.get("score", 0.0)
            path = item.get("path", "")
            dataset_name = item.get("dataset_name", "")
            typer.echo(f"  {idx:>2}. [{score:.3f}] {dataset_name}:{path}")
            snippet = item.get("snippet")
            if snippet:
                typer.echo(f"      {snippet['header']}")
                # Show first 2 lines of snippet text as preview
                preview_lines = snippet["text"].split("\n")[:2]
                for line in preview_lines:
                    typer.echo(f"      | {line}")
