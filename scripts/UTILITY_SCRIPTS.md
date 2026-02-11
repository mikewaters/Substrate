# Console script example

This document describes the utility script standards for this project.. **All utility scripts** should follow this pattern.

## Utility Script Location

Utility scripts should be placed in the project's top-leve `scripts/` directory.

## Utility Script Requirements

1. Uses `uv` to execute the script
2. Uses Python's "inline script metadata" standard to define the dependencies in the script itself
3. Uses the `Typer` library for command-line interaction, like setting parameters and interacting with the shell
4. Uses the `Rich` library for rendering structured information into the terminal.

## Integrating utility scripts with your code

If a utility script needs to make calls into one of our python modules, it should use normal python import semantics. Please see the example for more information.

**You should never** need to modify the system PATH or PYTHON_PATH, or do any shell tricks whatsoever. As long as you use `uv` to run the script it should be able to import any python module present in `src/`.

## Executing Utility Scripts

Scripts can be executed using python, but the preferred method is using `uv`:
`uv run --with . scripts/my-script-name.py`, from the project root directory.

## Utility Script Example

Use the below script as a starting point for new utilities.

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "ontology",
#   "typer",
#   "rich",
# ]
# ///

"""
This is an example of a console script
"""
import typer
from rich import box
from rich.console import Console
from rich.table import Table

# Note: This shouuld work without path munging:
from ontologizer import utils

app = typer.Typer(
    help="This is a utility script",
    add_completion=False,
)
console = Console()

THINGS = {
    'thing1': "Thing number one",
    'thing2': "Thing number two"
}


def valid_name(thing_name: str) -> bool:
    """Validate the name of a thing isnt too short"""
    if len(thing_name) < 2:
        return False
    return True


## Typer CLI Function with one argument
@app.command()
def get(
        thing_name: Annotated[
            str, typer.Argument(help="Thing to get"),
        ]
):
    """
    Get and display details about a thing.
    """
    # Example of a script error
    if len(thing_name) < 2:  # name is too short
        console.print(f"[red]Error:[/red] {thing_name}")
        raise typer.Exit(1) from None

    if thing_name in THINGS:
        console.print(
            f"\n[green]Found:[/green] {THINGS[thing_name]}"
        )
        raise Typer.Exit(0) from None
    else:
        console.print("Not found")
        raise typer.Exit(1) from None


## Typer CLI Function with no arguments
@app.command()
def list_things():
    """
    List all known things using a terminal ui Table from `rich.table`.
    """
    table = Table(
        title="Known Things",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )

    table.add_column("Column 1", style="green", no_wrap=True)
    table.add_column("Column 2", style="blue")

    for item_name, description in sorted(THINGS.items()):
        table.add_row(item_name, description)

    console.print()
    console.print(table)
    console.print()


if __name__ == "__main__":
    app()
```
