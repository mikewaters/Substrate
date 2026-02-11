#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "ontology",
#   "typer",
#   "rich",
# ]
# ///
"""Interactive dataset loader for ontology fixtures."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from ontologizer.loader import (
    DEFAULT_DATA_DIRECTORY,
    DatasetLoadStatus,
    list_dataset_files,
    load_selected_datasets,
)

app = typer.Typer(
    add_completion=False,
    help="Load ontology dataset fixtures into the database using an interactive TUI.",
)
console = Console()


@app.command()
def load(
    directory: Path | None = typer.Option(
        None,
        "--directory",
        "-d",
        path_type=Path,
        help="Directory containing dataset YAML files.",
    ),
    files: list[str] | None = typer.Option(
        None,
        "--file",
        "-f",
        help="Pre-select specific dataset files (relative to the chosen directory).",
    ),
    all_files: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Load all available dataset files without prompting.",
    ),
    assume_yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip the confirmation prompt.",
    ),
) -> None:
    """Display datasets and load the selected files."""
    data_dir = (directory or DEFAULT_DATA_DIRECTORY).resolve()

    try:
        available = list_dataset_files(data_dir)
    except (FileNotFoundError, NotADirectoryError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from None

    if not available:
        console.print(f"[yellow]No dataset files found in {data_dir}[/yellow]")
        raise typer.Exit(code=0)

    # Determine selection mode
    if all_files and files:
        console.print("[red]Error:[/red] Cannot use --all with --file options")
        raise typer.Exit(code=1)

    if all_files:
        selection = available
    else:
        preselected = list(files) if files else []

        if not preselected:
            console.print(_build_available_table(available, data_dir))

        selection = _resolve_selection(available, preselected, data_dir)
    if not selection:
        console.print("[yellow]No datasets selected; exiting.[/yellow]")
        raise typer.Exit(code=0)

    console.print(_build_selection_table(selection, data_dir))
    if not assume_yes:
        confirmed = Confirm.ask(
            f"Load [bold]{len(selection)}[/] dataset(s) into the database?",
            default=True,
        )
        if not confirmed:
            console.print("[yellow]Aborted by user.[/yellow]")
            raise typer.Exit(code=0)

    with console.status("Loading selected datasets...", spinner="dots"):
        results = asyncio.run(load_selected_datasets(selection))

    console.print(_build_results_table(results, data_dir))

    if any(result.success is False for result in results):
        raise typer.Exit(code=1)


def _resolve_selection(
    available: list[Path],
    preselected: list[str],
    base_dir: Path,
) -> list[Path]:
    """Return the dataset paths chosen by the user."""
    if preselected:
        indexed = {_normalize_name(path, base_dir): path for path in available}
        resolved: list[Path] = []
        for item in preselected:
            key = _normalize_name(Path(item), base_dir)
            if key not in indexed:
                console.print(
                    f"[red]Invalid selection:[/red] '{item}' is not in {base_dir}"
                )
                raise typer.Exit(code=1)
            resolved.append(indexed[key])
        return resolved

    count = len(available)
    prompt = "Enter dataset numbers separated by commas (e.g. 1,3,4) or 'all' to load everything"

    while True:
        answer = Prompt.ask(prompt).strip()
        if not answer:
            return []
        if answer.lower() in {"all", "*"}:
            return available

        try:
            indices = _parse_numeric_selection(answer, count)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            continue

        return [available[i] for i in indices]


def _build_available_table(available: list[Path], base_dir: Path) -> Table:
    """Render a table with the available dataset files."""
    table = Table(
        title="Available dataset files",
        header_style="bold cyan",
        show_lines=False,
    )
    table.add_column("#", justify="right", style="bold")
    table.add_column("Name", style="green")
    table.add_column("Path", style="blue")

    for index, path in enumerate(available, start=1):
        table.add_row(
            str(index),
            path.name,
            str(path.relative_to(base_dir)),
        )

    return table


def _build_results_table(results: list[DatasetLoadStatus], base_dir: Path) -> Table:
    """Render a table summarizing dataset load outcomes."""
    table = Table(
        title="Dataset load results",
        header_style="bold cyan",
        show_lines=False,
    )
    table.add_column("Name", style="green")
    table.add_column("Status", style="bold")
    table.add_column("Details", style="magenta")

    for result in results:
        relative_name = (
            str(result.path.relative_to(base_dir))
            if result.path.is_relative_to(base_dir)
            else str(result.path)
        )
        if result.success:
            status_text = Text("Success", style="green")
            detail = ", ".join(
                f"{key}={value}" for key, value in result.summary.items()
            )
        else:
            status_text = Text("Failed", style="red")
            detail = result.error or "Unknown error"

        table.add_row(relative_name, status_text, detail)

    return table


def _build_selection_table(selection: list[Path], base_dir: Path) -> Table:
    """Render a table showing the chosen datasets before loading."""
    table = Table(
        title="Selected dataset files",
        header_style="bold cyan",
        show_lines=False,
    )
    table.add_column("Name", style="green")
    table.add_column("Path", style="blue")

    for path in selection:
        display = (
            str(path.relative_to(base_dir))
            if path.is_relative_to(base_dir)
            else str(path)
        )
        table.add_row(path.name, display)

    return table


def _parse_numeric_selection(selection: str, count: int) -> list[int]:
    """Parse the comma/space separated selection string into zero-based indices."""
    tokens = re.split(r"[,\s]+", selection)
    indices: list[int] = []

    for token in tokens:
        if not token:
            continue
        if not token.isdigit():
            raise ValueError(f"'{token}' is not a valid number")
        index = int(token)
        if not 1 <= index <= count:
            raise ValueError(f"Selection {index} is out of range (1-{count})")
        normalized = index - 1
        if normalized not in indices:
            indices.append(normalized)

    if not indices:
        raise ValueError("No valid selections were provided")

    return indices


def _normalize_name(path: Path, base_dir: Path) -> str:
    """Normalize a dataset path to a comparable string key."""
    candidate = path
    if not candidate.is_absolute():
        candidate = (base_dir / candidate).resolve()
    try:
        return str(candidate.relative_to(base_dir))
    except ValueError:
        return str(candidate)


if __name__ == "__main__":
    app()
