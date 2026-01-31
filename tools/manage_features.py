#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "typer",
#   "rich",
# ]
# ///
"""Interactive feature completion workflow.

This script replaces the argument-only interface with a Rich-powered selection
experience while keeping full compatibility with the original usage. When the
script runs without positional arguments and the terminal supports interactive
rendering, maintainers see an indexed list of incomplete feature folders and
can choose one or more identifiers to complete. The selection prompt supports
basic filtering and pagination shortcuts:

* Enter comma-separated numbers (e.g., ``1,3,4``) to select specific feature(s).
* Enter ``f <term>`` to filter by substring across identifiers and PRD titles.
* Enter ``n`` or ``p`` to move to the next or previous page.
* Enter ``q`` to cancel without making any changes.

If the terminal cannot render interactive prompts (for example, when ``stdin``
is not a TTY), the script prints guidance and expects explicit feature IDs via
positional arguments (the legacy behaviour). The non-interactive path accepts
one or more identifiers plus ``--force/--yes`` to skip confirmation.

Usage examples:

```bash
uv run tools/complete_feature.py            # Interactive multi-select
uv run tools/complete_feature.py FEAT-002   # Argument-only workflow
uv run tools/complete_feature.py 12 13 --yes
```
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table


PAGE_SIZE_DEFAULT = 10


@dataclass(frozen=True)
class FeatureOption:
    """Lightweight view model for displaying available features."""

    feature_id: str
    source_path: Path
    prd_title: str | None = None


def normalize_feature_id(raw: str) -> str:
    """Normalize various inputs ("FEAT-012", "12", "012") to ``FEAT-NNN``."""

    if re.fullmatch(r"FEAT-\d{3}", raw):
        return raw

    if re.fullmatch(r"\d+", raw):
        return f"FEAT-{int(raw):03d}"

    raise ValueError(
        "Input must be FEAT-NNN or a numeric identifier (e.g., FEAT-002, 2, 002)."
    )


def discover_incomplete_features(features_dir: Path) -> list[FeatureOption]:
    """Return sorted feature folders that have not been moved to ``completed``."""

    if not features_dir.exists():
        return []

    options: list[FeatureOption] = []
    for entry in features_dir.iterdir():
        if not entry.is_dir():
            continue
        if entry.name == "completed":
            continue
        if not re.fullmatch(r"FEAT-\d{3}", entry.name):
            continue

        options.append(
            FeatureOption(
                feature_id=entry.name,
                source_path=entry,
                prd_title=_read_prd_title(entry),
            )
        )

    return sorted(options, key=lambda opt: opt.feature_id)


def _read_prd_title(feature_dir: Path) -> str | None:
    """Return the first Markdown heading from ``PRD.md`` if available."""

    prd_path = feature_dir / "PRD.md"
    if not prd_path.exists():
        return None

    try:
        with prd_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped.startswith("#"):
                    return stripped.lstrip("# ").strip()
        return None
    except OSError:
        return None


def has_tty_support(console: Console) -> bool:
    """Check whether the current execution context can show an interactive UI."""

    return sys.stdin.isatty() and console.is_terminal


def build_move_plan(
    feature_ids: Sequence[str],
    features_dir: Path,
    completed_dir: Path,
) -> tuple[list[FeatureOption], list[str]]:
    """Validate requested features and return move plan plus any errors."""

    available = {opt.feature_id: opt for opt in discover_incomplete_features(features_dir)}

    selections: list[FeatureOption] = []
    errors: list[str] = []

    seen: set[str] = set()
    for raw_id in feature_ids:
        try:
            feature_id = normalize_feature_id(raw_id)
        except ValueError as exc:
            errors.append(str(exc))
            continue

        if feature_id in seen:
            continue
        seen.add(feature_id)

        option = available.get(feature_id)
        if option is None:
            errors.append(f"Feature '{feature_id}' is not available in {features_dir}.")
            continue

        destination = completed_dir / feature_id
        if destination.exists():
            errors.append(f"Feature '{feature_id}' is already marked as completed.")
            continue

        selections.append(option)

    return selections, errors


def execute_move_plan(
    console: Console,
    selections: Sequence[FeatureOption],
    completed_dir: Path,
) -> int:
    """Move each selected feature directory and render a summary."""

    completed_dir.mkdir(parents=True, exist_ok=True)

    successes: list[FeatureOption] = []
    failures: list[tuple[FeatureOption, str]] = []

    for option in selections:
        destination = completed_dir / option.feature_id
        try:
            shutil.move(str(option.source_path), str(destination))
        except Exception as exc:  # noqa: BLE001 - we want to report any failure
            failures.append((option, str(exc)))
        else:
            successes.append(
                FeatureOption(option.feature_id, destination, option.prd_title)
            )

    if successes:
        console.print(_render_summary_table("Completed", successes))

    if failures:
        failure_table = Table(title="Errors", show_lines=False)
        failure_table.add_column("Feature", style="bold red")
        failure_table.add_column("Reason", style="yellow")
        for option, reason in failures:
            failure_table.add_row(option.feature_id, reason)
        console.print(failure_table)
        console.print("One or more moves failed. Resolve the issues and re-run as needed.")
        return 1

    console.print("All selected features have been marked as completed.")
    return 0


def _render_summary_table(title: str | None, options: Sequence[FeatureOption]) -> Table:
    table = Table(title=title, show_lines=False)
    table.add_column("Feature", style="bold")
    table.add_column("Location", style="cyan")
    table.add_column("Title", style="green")
    for option in options:
        location = str(option.source_path)
        table.add_row(option.feature_id, location, option.prd_title or "—")
    return table


def interactive_selection(
    console: Console,
    features: Sequence[FeatureOption],
    page_size: int = PAGE_SIZE_DEFAULT,
) -> list[FeatureOption]:
    """Render an interactive prompt and return chosen feature options."""

    if not features:
        console.print("No incomplete features found. Nothing to do.")
        return []

    filtered = list(features)
    filter_term: str | None = None
    page = 0

    while True:
        total_pages = max(1, (len(filtered) - 1) // page_size + 1)
        page = max(0, min(page, total_pages - 1))
        start = page * page_size
        end = start + page_size
        page_slice = filtered[start:end]

        console.print(
            _render_feature_table(
                page_slice, start=start, filter_term=filter_term, page=page + 1, total_pages=total_pages
            )
        )

        response = Prompt.ask(
            "Select features by number (comma separated). Commands: "
            "'f <term>' to filter, 'n'/'p' for paging, 'q' to cancel",
            default="",
        ).strip()

        if not response:
            console.print("No selection provided. Please choose feature numbers or 'q' to cancel.")
            continue

        lower = response.lower()
        if lower == "q":
            console.print("Selection cancelled. No changes made.")
            return []
        if lower == "n":
            if page + 1 < total_pages:
                page += 1
            else:
                console.print("Already on the last page.")
            continue
        if lower == "p":
            if page > 0:
                page -= 1
            else:
                console.print("Already on the first page.")
            continue
        if lower.startswith("f "):
            term = response[2:].strip()
            if not term:
                filter_term = None
                filtered = list(features)
                page = 0
                console.print("Cleared filter.")
            else:
                filter_term = term.lower()
                filtered = [opt for opt in features if _matches_filter(opt, filter_term)]
                page = 0
                if not filtered:
                    console.print(f"No features match '{term}'. Showing all entries again.")
                    filter_term = None
                    filtered = list(features)
            continue

        try:
            selections = _parse_selection_indices(response)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            continue

        chosen: list[FeatureOption] = []
        for index in selections:
            absolute_index = index - 1
            if absolute_index < 0 or absolute_index >= len(filtered):
                console.print(f"[red]Index {index} is out of range for the current view.[/red]")
                chosen = []
                break
            chosen.append(filtered[absolute_index])

        if not chosen:
            continue

        return chosen


def _render_feature_table(
    page_slice: Sequence[FeatureOption],
    *,
    start: int,
    filter_term: str | None,
    page: int,
    total_pages: int,
) -> Table:
    table = Table(title=f"Incomplete Features (page {page}/{total_pages})", show_lines=False)
    table.add_column("#", justify="right", style="bold")
    table.add_column("Feature", style="cyan")
    table.add_column("PRD Title", style="green")

    for offset, option in enumerate(page_slice, start=start + 1):
        table.add_row(str(offset), option.feature_id, option.prd_title or "—")

    if filter_term:
        table.caption = f"Filter active: '{filter_term}'"

    return table


def _matches_filter(option: FeatureOption, filter_term: str) -> bool:
    haystacks = [option.feature_id.lower()]
    if option.prd_title:
        haystacks.append(option.prd_title.lower())
    return any(filter_term in hay for hay in haystacks)


def _parse_selection_indices(raw: str) -> list[int]:
    tokens = [token.strip() for token in raw.replace(";", ",").split(",") if token.strip()]
    if not tokens:
        raise ValueError("No selection provided.")

    indices: list[int] = []
    for token in tokens:
        if not token.isdigit():
            raise ValueError(f"'{token}' is not a valid index.")
        indices.append(int(token))

    unique_indices = sorted(set(indices))
    return unique_indices


def confirm_selection(console: Console, options: Sequence[FeatureOption]) -> bool:
    console.print(_render_summary_table("Selected Features", options))
    return Confirm.ask("Move the selected feature(s) to completed?", default=False)


def print_available_features(console: Console, features: Iterable[FeatureOption]) -> None:
    options = list(features)
    if not options:
        console.print("No incomplete features found.")
        return
    console.print(_render_summary_table("Available Features", options))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mark feature documentation as completed using an interactive workflow.",
    )
    parser.add_argument(
        "feature_ids",
        nargs="*",
        help="Feature identifiers (FEAT-NNN or numeric). Leave empty for interactive selection.",
    )
    parser.add_argument(
        "-y",
        "--yes",
        "--force",
        dest="force",
        action="store_true",
        help="Skip confirmation prompts in non-interactive mode.",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=PAGE_SIZE_DEFAULT,
        help=f"Number of rows to display per page in interactive mode (default: {PAGE_SIZE_DEFAULT}).",
    )

    args = parser.parse_args(argv)

    console = Console()
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    features_dir = project_root / "docs" / "features"
    completed_dir = features_dir / "completed"

    if args.feature_ids:
        selections, errors = build_move_plan(args.feature_ids, features_dir, completed_dir)
        if errors:
            for message in errors:
                console.print(f"[red]{message}[/red]")
            available = discover_incomplete_features(features_dir)
            if available:
                print_available_features(console, available)
            return 1

        if not selections:
            console.print("No valid feature identifiers were provided.")
            return 1

        if not args.force:
            if not confirm_selection(console, selections):
                console.print("Aborted at user request. No changes made.")
                return 0

        return execute_move_plan(console, selections, completed_dir)

    # Interactive path
    if not has_tty_support(console):
        console.print(
            Panel(
                "Interactive mode requires a TTY. Re-run with explicit identifiers, e.g.\n"
                "  uv run tools/complete_feature.py FEAT-001",
                title="TTY Not Available",
                border_style="yellow",
            )
        )
        return 1

    available = discover_incomplete_features(features_dir)
    if not available:
        console.print("No incomplete features found. Nothing to do.")
        return 0

    selections = interactive_selection(console, available, page_size=max(1, args.page_size))
    if not selections:
        return 0

    if not confirm_selection(console, selections):
        console.print("Aborted at user request. No changes made.")
        return 0

    return execute_move_plan(console, selections, completed_dir)


if __name__ == "__main__":
    raise SystemExit(main())
