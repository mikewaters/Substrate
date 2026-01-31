#!/usr/bin/env python3

# Document Classification Utility Script
#
# This script demonstrates the full document classification pipeline using the ontology system.
#
# PROCESSING PIPELINE:
# ====================
#
# 1. INPUT VALIDATION
#    - Accepts document text via CLI argument or interactive input
#    - Validates that input is not empty
#
# 2. TAXONOMY CLASSIFICATION (Stage 1)
#    - Sends document to configured LLM (Anthropic, LM Studio, vLLM, Ollama, etc.)
#    - LLM analyzes document themes and matches against all available taxonomies
#    - Returns ranked list of taxonomy suggestions with confidence scores
#    - Filters results by minimum confidence threshold (default: 0.3)
#
# 3. TOPIC CLASSIFICATION (Stage 2)
#    - Using primary taxonomy suggestion from Stage 1
#    - LLM analyzes document content and matches to topics within that taxonomy
#    - Returns ranked list of topic suggestions with confidence scores
#
# 4. OPTIONAL: ALTERNATIVE TAXONOMIES
#    - Secondary taxonomy suggestions are available if document matches multiple taxonomies
#    - Useful for understanding cross-domain relevance
#
# 5. OPTIONAL: NEW TOPIC PROPOSALS
#    - With --suggest-new flag: LLM proposes new topics that should be added to taxonomy
#    - Identifies gaps where existing topics don't adequately cover document concepts
#    - Includes reasoning and suggested parent topics for new proposals
#
# 6. OPTIONAL: PARENT TOPIC SUGGESTIONS
#    - With --suggest-parents flag: For each suggested topic, LLM proposes parent topics
#    - Helps understand taxonomy hierarchy and topic relationships
#
# EXPECTED OUTPUT:
# ================
#
# The script renders a structured report including:
# - Document Summary: Preview and metadata
# - Taxonomy Classification: Primary + alternatives with confidence scores
# - Topic Classifications: Ranked topics with confidence and reasoning
# - Metadata: Model used, processing version, execution timestamps
# - Optional: New topic proposals and parent suggestions (if enabled)
#
# All output is rendered using Rich library for attractive terminal formatting.
#
# CONFIGURATION:
# ==============
#
# The classifier uses environment variables for LLM configuration:
#   - SUBSTRATE_LLM_PROVIDER: "anthropic" (default) or "openai-compatible"
#   - SUBSTRATE_LLM_MODEL_NAME: Model identifier
#   - SUBSTRATE_LLM_OPENAI_BASE_URL: Endpoint URL (for local models)
#   - SUBSTRATE_LLM_API_KEY: API key
#
# See docs/LLM_CONFIGURATION.md for setup examples.
#
# EXAMPLES:
# =========
#
# Basic classification with direct text:
#   uv run python scripts/classify-document.py "Python is a popular programming language"
#
# Classification from a file:
#   uv run python scripts/classify-document.py docs/my-document.txt --file
#
# Classification with minimum confidence threshold:
#   uv run python scripts/classify-document.py --min-confidence 0.5 "Your document text"
#
# Include new topic proposals:
#   uv run python scripts/classify-document.py --suggest-new "Your document text"
#
# Include parent topic suggestions:
#   uv run python scripts/classify-document.py --suggest-parents "Your document text"
#
# Both new topics and parents:
#   uv run python scripts/classify-document.py --suggest-new --suggest-parents "text"
#
# File classification with all options:
#   uv run python scripts/classify-document.py /path/to/file.txt --file -n -p -c 0.5
#
# Interactive input mode (enter text via stdin):
#   uv run python scripts/classify-document.py
#   (script will prompt for document text)

import asyncio
from typing import Annotated

import typer
from rich.box import ROUNDED
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from ontology.relational.services.document_classification import (
    DocumentClassificationService,
)
from ontology.relational.database import Base
from ontology.relational.repository import (
    TopicRepository,
)
from ontology.relational.repository import TaxonomyRepository
from ontology.schema import DocumentClassificationRequest

app = typer.Typer(
    help="Classify documents into taxonomies and topics using the ontology system",
    add_completion=False,
    no_args_is_help=False,
)
console = Console()


def setup_database():
    """Initialize database and create async session factory."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from ontology.settings import get_settings

    settings = get_settings()

    async_engine = create_async_engine(
        settings.database.url,
        echo=False,
    )
    async_session_factory = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )

    return async_session_factory, async_engine


async def init_database(async_engine) -> None:
    """Initialize database tables asynchronously."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def render_header() -> None:
    """Render welcome header."""
    header_text = Text()
    header_text.append("📚 ", style="bold blue")
    header_text.append("Document Classification System", style="bold cyan")
    console.print(
        Panel(
            header_text,
            box=ROUNDED,
            style="blue",
            expand=False,
        )
    )


def render_document_info(content: str, doc_type: str = "text") -> None:
    """Render input document information."""
    table = Table(
        title="📄 Input Document",
        box=ROUNDED,
        show_header=False,
        title_style="bold cyan",
    )
    table.add_column("Property", style="green")
    table.add_column("Value", style="white")

    preview = content[:200] + ("..." if len(content) > 200 else "")
    table.add_row("Preview", preview)
    table.add_row("Length", f"{len(content)} characters")
    table.add_row("Type", doc_type)

    console.print(table)
    console.print()


def render_taxonomy_results(
    primary_taxonomy,
    alternative_taxonomies: list | None = None,
) -> None:
    """Render taxonomy classification results."""
    table = Table(
        title="🗂️  Taxonomy Classification",
        box=ROUNDED,
        show_header=True,
        title_style="bold cyan",
        header_style="bold magenta",
    )
    table.add_column("Taxonomy", style="green", width=30)
    table.add_column("Confidence", justify="right", width=15)
    table.add_column("Reasoning", style="white")

    primary_row = [
        primary_taxonomy.taxonomy_title or str(primary_taxonomy.taxonomy_id),
        f"{primary_taxonomy.confidence:.1%}",
        primary_taxonomy.reasoning or "No reasoning provided",
    ]
    table.add_row(*primary_row, style="bold green")

    if alternative_taxonomies:
        for tax in alternative_taxonomies:
            table.add_row(
                tax.taxonomy_title or str(tax.taxonomy_id),
                f"{tax.confidence:.1%}",
                tax.reasoning or "No reasoning provided",
            )

    console.print(table)
    console.print()


def render_topic_results(topics: list) -> None:
    """Render topic classification results."""
    if not topics:
        console.print("[yellow]ℹ️  No topics matched the confidence threshold[/yellow]")
        console.print()
        return

    table = Table(
        title="🎯 Topic Classifications",
        box=ROUNDED,
        show_header=True,
        title_style="bold cyan",
        header_style="bold magenta",
    )
    table.add_column("Rank", justify="center", width=6, style="cyan")
    table.add_column("Topic", style="green", width=30)
    table.add_column("Confidence", justify="right", width=15)
    table.add_column("Reasoning", style="white")

    for topic in topics:
        table.add_row(
            str(topic.rank),
            topic.topic_title or str(topic.topic_id),
            f"{topic.confidence:.1%}",
            topic.reasoning or "No reasoning provided",
        )

    console.print(table)
    console.print()


def render_new_topics(proposals: list) -> None:
    """Render new topic proposals."""
    if not proposals:
        console.print("[yellow]ℹ️  No new topics proposed[/yellow]")
        console.print()
        return

    console.print("[bold cyan]💡 Proposed New Topics[/bold cyan]")
    console.print()

    for i, proposal in enumerate(proposals, 1):
        panel_content = Text()
        panel_content.append("Title: ", style="bold green")
        panel_content.append(f"{proposal.title}\n")
        panel_content.append("Description: ", style="bold green")
        panel_content.append(f"{proposal.description}\n")
        panel_content.append("Confidence: ", style="bold green")
        panel_content.append(f"{proposal.confidence:.1%}\n")
        panel_content.append("Reasoning: ", style="bold green")
        panel_content.append(f"{proposal.reasoning or 'N/A'}\n")

        console.print(
            Panel(
                panel_content,
                title=f"Proposal {i}",
                box=ROUNDED,
                style="yellow",
                expand=False,
            )
        )

    console.print()


def render_parent_suggestions(parent_suggestions: dict) -> None:
    """Render parent topic suggestions by topic."""
    if not parent_suggestions:
        console.print("[yellow]ℹ️  No parent topics suggested[/yellow]")
        console.print()
        return

    console.print("[bold cyan]👥 Parent Topic Suggestions[/bold cyan]")
    console.print()

    for topic_title, parents in parent_suggestions.items():
        table = Table(
            title=f"Parents for: {topic_title}",
            box=ROUNDED,
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Parent Topic", style="green")
        table.add_column("Confidence", justify="right")
        table.add_column("Reasoning", style="white")

        if parents:
            for parent in parents:
                table.add_row(
                    parent.parent_topic_title or str(parent.parent_topic_id),
                    f"{parent.confidence:.1%}",
                    parent.reasoning or "No reasoning provided",
                )
        else:
            table.add_row(
                "[gray]No parents suggested[/gray]",
                "",
                "",
            )

        console.print(table)
        console.print()


def render_metadata(response) -> None:
    """Render classification metadata."""
    table = Table(
        title="ℹ️  Classification Metadata",
        box=ROUNDED,
        show_header=False,
        title_style="bold cyan",
    )
    table.add_column("Property", style="green")
    table.add_column("Value", style="white")

    table.add_row("Model", response.model_name)
    table.add_row("Model Version", response.model_version)
    table.add_row("Prompt Version", response.prompt_version)
    if response.created_at:
        table.add_row("Classified At", response.created_at.isoformat())
    if response.classification_id:
        table.add_row("Classification ID", str(response.classification_id))

    console.print(table)
    console.print()


@app.command()
def classify(
    document: Annotated[
        str | None,
        typer.Argument(
            help="Document text to classify, or path to file (--file). If not provided, will prompt for input."
        ),
    ] = None,
    min_confidence: Annotated[
        float,
        typer.Option(
            "--min-confidence",
            "-c",
            min=0.0,
            max=1.0,
            help="Minimum confidence threshold for suggestions (0.0-1.0)",
        ),
    ] = 0.3,
    max_topics: Annotated[
        int,
        typer.Option(
            "--max-topics",
            "-t",
            min=1,
            max=20,
            help="Maximum number of topics to suggest",
        ),
    ] = 5,
    suggest_new: Annotated[
        bool,
        typer.Option(
            "--suggest-new",
            "-n",
            help="Request LLM to suggest new topics for the taxonomy",
        ),
    ] = False,
    suggest_parents: Annotated[
        bool,
        typer.Option(
            "--suggest-parents",
            "-p",
            help="Request LLM to suggest parent topics for each matched topic",
        ),
    ] = False,
    doc_type: Annotated[
        str,
        typer.Option(
            "--type",
            "-T",
            help="Document type (e.g., 'article', 'note', 'email')",
        ),
    ] = "text",
    file: Annotated[
        bool,
        typer.Option(
            "--file",
            "-f",
            help="Treat the DOCUMENT argument as a file path instead of text",
        ),
    ] = False,
) -> None:
    """
    Classify a document into taxonomies and topics.

    Processes the input document through the full classification pipeline:
    1. Validates input
    2. Classifies into primary taxonomy
    3. Classifies into topics within that taxonomy
    4. Optionally suggests new topics or parent relationships

    The classifier uses your configured LLM provider (see docs/LLM_CONFIGURATION.md).

    USAGE:
        # Classify text directly
        classify-document.py "Your document text here"

        # Classify from file
        classify-document.py path/to/document.txt --file

        # Interactive mode (enter text via stdin)
        classify-document.py
    """
    if file:
        # Load from file
        if not document:
            console.print("[red]Error: File path required when using --file[/red]")
            raise typer.Exit(1)
        try:
            from pathlib import Path

            document = Path(document).read_text(encoding="utf-8")
        except FileNotFoundError:
            console.print(f"[red]Error: File not found: {document}[/red]")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]Error reading file: {str(e)}[/red]")
            raise typer.Exit(1)
    elif not document:
        # Interactive input
        console.print("[cyan]Enter document text (press Ctrl+D when done):[/cyan]")
        try:
            document = console.file.read()
        except EOFError:
            console.print("[red]Error: No input provided[/red]")
            raise typer.Exit(1)

    document = document.strip()
    if not document:
        console.print("[red]Error: Document cannot be empty[/red]")
        raise typer.Exit(1)

    render_header()
    render_document_info(document, doc_type)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("Initializing database...", total=None)

            async_session_factory, async_engine = setup_database()

            loop = asyncio.get_event_loop()
            response, new_topics, parent_suggestions = loop.run_until_complete(
                run_classification(
                    async_session_factory,
                    async_engine,
                    document,
                    min_confidence,
                    max_topics,
                    suggest_new,
                    suggest_parents,
                    doc_type,
                )
            )

        render_taxonomy_results(
            response.suggested_taxonomy,
            response.alternative_taxonomies,
        )

        render_topic_results(response.suggested_topics)

        if suggest_new:
            render_new_topics(new_topics)

        if suggest_parents:
            render_parent_suggestions(parent_suggestions)

        render_metadata(response)

        console.print("[green]✓ Classification complete[/green]")

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")

        # Provide helpful context for known errors
        error_msg = str(e).lower()
        if "result_type" in error_msg or "unknown keyword arguments" in error_msg:
            console.print(
                "\n[yellow]Note: The DocumentClassificationService API may need updating for the current PydanticAI version.[/yellow]"
            )
            console.print(
                "[yellow]See: src/ontology/information/services/classifier.py[/yellow]"
            )

        import sys
        import traceback

        if sys.platform != "win32":
            traceback.print_exc()
        raise typer.Exit(1)


async def run_classification(
    async_session_factory,
    async_engine,
    document: str,
    min_confidence: float,
    max_topics: int,
    suggest_new: bool,
    suggest_parents: bool,
    doc_type: str,
) -> tuple:
    """Run the classification pipeline asynchronously."""
    # Initialize database tables
    await init_database(async_engine)

    async with async_session_factory() as session:
        taxonomy_repo = TaxonomyRepository(session=session)
        topic_repo = TopicRepository(session=session)

        service = DocumentClassificationService(
            classification_repo=None,
            taxonomy_repo=taxonomy_repo,
            topic_repo=topic_repo,
        )

        request = DocumentClassificationRequest(
            content=document,
            document_type=doc_type,
            min_confidence=min_confidence,
            max_topics=max_topics,
            store_result=False,
        )

        response = await service.classify_document(request)

        new_topics = []
        parent_suggestions = {}

        if suggest_new:
            new_topics = await service.suggest_new_topics(
                content=document,
                taxonomy_id=response.suggested_taxonomy.taxonomy_id,
                existing_suggestions=response.suggested_topics,
                max_proposals=3,
            )

        if suggest_parents:
            for topic in response.suggested_topics:
                parents = await service.suggest_parent_topics(
                    topic_id=topic.topic_id,
                    max_suggestions=3,
                )
                parent_suggestions[topic.topic_title] = parents

        return response, new_topics, parent_suggestions


if __name__ == "__main__":
    app()
