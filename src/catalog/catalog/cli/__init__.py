"""catalog.cli - Command-line interface for catalog.

Provides CLI commands for managing catalog operations including
search evaluation, document ingestion, and quality assessment.

Commands:
    eval: Evaluation commands for RAG search quality
        golden: Run golden query evaluation

Example usage:
    # Run golden query evaluation
    uv run python -m catalog eval golden
"""

import typer

from catalog.cli.eval import eval_app

__all__ = ["app", "eval_app"]

app = typer.Typer(
    name="catalog",
    help="Catalog CLI for managing document search and evaluation.",
)

# Register sub-apps
app.add_typer(eval_app, name="eval")


def main() -> None:
    """Entry point for the CLI."""
    app()
