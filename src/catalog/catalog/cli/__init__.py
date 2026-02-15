"""catalog.cli - Command-line interface for catalog.

Provides CLI commands for managing catalog operations including
search evaluation, document ingestion, and quality assessment.

Commands:
    search: Search method commands
        methods: Run all documented search methods for a query
    eval: Evaluation commands for RAG search quality
        golden: Run golden query evaluation

Example usage:
    # Run search method comparison
    uv run python -m catalog search methods "python async"

    # Run golden query evaluation
    uv run python -m catalog eval golden
"""

import typer

from catalog.cli.eval import eval_app
from catalog.cli.search import search_app

__all__ = ["app", "eval_app", "search_app"]

app = typer.Typer(
    name="catalog",
    help="Catalog CLI for managing document search and evaluation.",
)

# Register sub-apps
app.add_typer(eval_app, name="eval")
app.add_typer(search_app, name="search")


def main() -> None:
    """Entry point for the CLI."""
    app()
