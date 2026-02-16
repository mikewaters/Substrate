"""Human-operator `substrate-admin` command entrypoint."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated

import click
import typer
from typer.main import get_command

from catalog.cli.eval import eval_app
from catalog.cli.search import search_app
from tool.cli.logging_config import DEFAULT_ADMIN_LOG_LEVEL, configure_cli_logging


app = typer.Typer(
    name="substrate-admin",
    help=(
        "Human-operator command surface for Substrate.\n"
        "v0 exposes evaluation and search-metrics commands delegated from catalog."
    ),
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(eval_app, name="eval")
app.add_typer(search_app, name="search")


@app.callback()
def _global_options(
    log_level: Annotated[
        str,
        typer.Option(
            "--log-level",
            "--debug-level",
            help="Global logging verbosity.",
            case_sensitive=False,
            show_default=False,
        ),
    ] = DEFAULT_ADMIN_LOG_LEVEL,
) -> None:
    """Configure global CLI options prior to subcommand execution."""
    configure_cli_logging(log_level)


def _normalize_exit_code(exit_code: int) -> int:
    """Normalize delegated command exits into the approved CLI taxonomy."""
    if exit_code in {0, 2, 3, 4, 5, 6, 130}:
        return exit_code
    if exit_code == 1:
        return 5
    if exit_code < 0:
        return 130
    return 5


def main(argv: Sequence[str] | None = None) -> int:
    """Run the `substrate-admin` CLI."""
    command = get_command(app)
    args = list(argv) if argv is not None else None

    try:
        command.main(
            args=args,
            prog_name="substrate-admin",
            standalone_mode=True,
        )
        return 0
    except SystemExit as exc:
        if exc.code is None:
            return 0
        if isinstance(exc.code, int):
            return _normalize_exit_code(exc.code)
        return 5
    except click.UsageError as exc:
        exc.show()
        return 2
    except click.ClickException as exc:
        exc.show()
        return _normalize_exit_code(exc.exit_code)
    except click.exceptions.Exit as exc:
        return _normalize_exit_code(exc.exit_code)
    except click.Abort:
        return 130
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
