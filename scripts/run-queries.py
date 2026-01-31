#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "ontology",
#   "typer",
#   "rich",
#   "sqlalchemy",
# ]
# ///
"""Interactive SQL query runner for the ontology database."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from sqlalchemy import text

from ontology.relational.database import get_async_session

app = typer.Typer(
    add_completion=False,
    help="Run pre-defined SQL queries against the ontology database.",
)
console = Console()

# Default location for queries
QUERIES_FILE = Path(__file__).parent / "queries.jsonl"


@app.command()
def run(
    queries_file: Path | None = typer.Option(
        None,
        "--file",
        "-f",
        path_type=Path,
        help="Path to JSONL file containing queries.",
    ),
    query_id: str | None = typer.Option(
        None,
        "--id",
        "-i",
        help="Directly run a query by its ID without prompting.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        path_type=Path,
        help="Save results to markdown file (default: run-query.md).",
    ),
) -> None:
    """Display available queries and execute the selected one."""
    file_path = queries_file or QUERIES_FILE

    if not file_path.exists():
        console.print(f"[red]Error:[/red] Queries file not found: {file_path}")
        raise typer.Exit(code=1)

    # Load queries from JSONL
    queries = _load_queries(file_path)

    if not queries:
        console.print(f"[yellow]No queries found in {file_path}[/yellow]")
        raise typer.Exit(code=0)

    # Select query
    if query_id:
        selected = next((q for q in queries if q["id"] == query_id), None)
        if not selected:
            console.print(f"[red]Error:[/red] Query ID '{query_id}' not found")
            raise typer.Exit(code=1)
    else:
        console.print(_build_queries_table(queries))
        selected = _select_query(queries)

    if not selected:
        console.print("[yellow]No query selected; exiting.[/yellow]")
        raise typer.Exit(code=0)

    # Display selected query info
    console.print()
    console.print(f"[bold cyan]Query:[/bold cyan] {selected['description']}")
    console.print(f"[bold cyan]ID:[/bold cyan] {selected['id']}")
    if selected.get("tags"):
        console.print(f"[bold cyan]Tags:[/bold cyan] {', '.join(selected['tags'])}")
    console.print()

    # Execute query
    with console.status("Executing query...", spinner="dots"):
        results = asyncio.run(_execute_query(selected["sql"]))

    if not results:
        console.print("[yellow]Query returned no results.[/yellow]")
        raise typer.Exit(code=0)

    # Display results
    console.print(_build_results_table(results))
    console.print()
    console.print(f"[green]Returned {len(results)} row(s)[/green]")

    # Save to file if output specified
    if output is not None:
        _save_to_markdown(output, selected, results)
        console.print(f"[green]Results saved to {output}[/green]")


def _load_queries(file_path: Path) -> list[dict[str, Any]]:
    """Load queries from JSONL file."""
    queries = []
    try:
        with file_path.open() as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    query = json.loads(line)
                    # Validate required fields
                    if (
                        "id" not in query
                        or "description" not in query
                        or "sql" not in query
                    ):
                        console.print(
                            f"[yellow]Warning:[/yellow] Line {line_num} missing required fields (id, description, sql), skipping"
                        )
                        continue
                    queries.append(query)
                except json.JSONDecodeError as e:
                    console.print(
                        f"[yellow]Warning:[/yellow] Line {line_num} is not valid JSON: {e}"
                    )
                    continue
    except Exception as e:
        console.print(f"[red]Error reading queries file:[/red] {e}")
        raise typer.Exit(code=1) from None

    return queries


def _build_queries_table(queries: list[dict[str, Any]]) -> Table:
    """Render a table with available queries."""
    table = Table(
        title="Available Queries",
        header_style="bold cyan",
        show_lines=False,
    )
    table.add_column("#", justify="right", style="bold")
    table.add_column("ID", style="green")
    table.add_column("Description", style="white")
    table.add_column("Tags", style="blue")

    for index, query in enumerate(queries, start=1):
        tags = ", ".join(query.get("tags", [])) if query.get("tags") else ""
        table.add_row(
            str(index),
            query["id"],
            query["description"],
            tags,
        )

    return table


def _select_query(queries: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Prompt user to select a query."""
    count = len(queries)

    while True:
        answer = Prompt.ask(
            f"Enter query number (1-{count}), query ID, or press Enter to cancel"
        ).strip()

        if not answer:
            return None

        # Try as number
        if answer.isdigit():
            index = int(answer)
            if 1 <= index <= count:
                return queries[index - 1]
            console.print(f"[red]Selection {index} is out of range (1-{count})[/red]")
            continue

        # Try as ID
        matching = next((q for q in queries if q["id"] == answer), None)
        if matching:
            return matching

        console.print(f"[red]No query found with ID '{answer}'[/red]")


async def _execute_query(sql: str) -> list[dict[str, Any]]:
    """Execute a SQL query and return results as list of dicts."""
    async with get_async_session() as session:
        result = await session.execute(text(sql))

        # Get column names
        if result.returns_rows:
            columns = list(result.keys())
            rows = result.fetchall()

            # Convert to list of dicts
            return [dict(zip(columns, row)) for row in rows]

        return []


def _build_results_table(results: list[dict[str, Any]]) -> Table:
    """Render query results as a markdown-style table."""
    if not results:
        return Table(title="No Results")

    table = Table(
        title="Query Results",
        header_style="bold cyan",
        show_lines=True,
        expand=True,
    )

    # Add columns from first result
    for col_name in results[0].keys():
        table.add_column(col_name, overflow="fold")

    # Add rows
    for row in results:
        # Convert all values to strings, handle None
        row_values = [str(v) if v is not None else "" for v in row.values()]
        table.add_row(*row_values)

    return table


def _save_to_markdown(
    output_path: Path, query_info: dict[str, Any], results: list[dict[str, Any]]
) -> None:
    """Save query results to a markdown file."""
    lines = []

    # Add query information
    lines.append(f"# Query Results: {query_info['description']}\n")
    lines.append(f"**Query ID:** `{query_info['id']}`\n")
    if query_info.get("tags"):
        lines.append(f"**Tags:** {', '.join(query_info['tags'])}\n")
    lines.append(f"\n**SQL:**\n```sql\n{query_info['sql']}\n```\n")
    lines.append(f"\n**Results:** {len(results)} row(s)\n")

    if not results:
        lines.append("\nNo results returned.\n")
    else:
        # Build markdown table
        lines.append("\n## Data\n")

        # Get column names from first result
        columns = list(results[0].keys())

        # Header row
        lines.append("| " + " | ".join(columns) + " |")

        # Separator row
        lines.append("| " + " | ".join(["---"] * len(columns)) + " |")

        # Data rows
        for row in results:
            values = [str(v) if v is not None else "" for v in row.values()]
            # Escape pipe characters in cell values
            values = [v.replace("|", "\\|") for v in values]
            lines.append("| " + " | ".join(values) + " |")

    # Write to file
    output_path.write_text("\n".join(lines))


if __name__ == "__main__":
    app()
