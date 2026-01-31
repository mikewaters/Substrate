#!/usr/bin/env python3
"""Standalone FastAPI development server runner.

This script starts the FastAPI application using Uvicorn with support for
hot-reloading, custom host/port configuration, and request logging.
"""

import logging
from typing import Literal

import typer
import uvicorn

logger = logging.getLogger(__name__)

LogLevel = Literal["critical", "error", "warning", "info", "debug", "trace"]


def main(
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        "-h",
        help="Host to bind the server to",
    ),
    port: int = typer.Option(
        8000,
        "--port",
        "-p",
        help="Port to bind the server to",
    ),
    reload: bool = typer.Option(
        True,
        "--reload/--no-reload",
        help="Enable auto-reload on code changes",
    ),
    log_level: LogLevel = typer.Option(
        "info",
        "--log-level",
        help="Log level (critical, error, warning, info, debug, trace)",
        case_sensitive=False,
    ),
) -> None:
    """Start the FastAPI development server.

    This command starts the FastAPI application using Uvicorn with support for
    hot-reloading, custom host/port configuration, and request logging.

    Examples:
        # Start with defaults (127.0.0.1:8000, reload enabled)
        python tools/serve.py

        # Start on all interfaces, custom port
        python tools/serve.py --host 0.0.0.0 --port 8080

        # Disable reload, set log level
        python tools/serve.py --no-reload --log-level debug

        # Short flags
        python tools/serve.py -h 0.0.0.0 -p 8080

        # Via just command
        just api-dev

    Args:
        host: Host to bind the server to (default: 127.0.0.1)
        port: Port to bind the server to (default: 8000)
        reload: Enable auto-reload on code changes (default: True)
        log_level: Log level for the server (default: info)
    """
    typer.echo(f"Starting FastAPI server at http://{host}:{port}")
    typer.echo(f"Auto-reload: {'enabled' if reload else 'disabled'}")
    typer.echo(f"Log level: {log_level}")
    typer.echo("")
    typer.echo("Press CTRL+C to quit")
    typer.echo("")

    try:
        uvicorn.run(
            "ontology.api.app:app",
            host=host,
            port=port,
            reload=reload,
            log_level=log_level.lower(),
            access_log=True,
        )
    except KeyboardInterrupt:
        typer.echo("\nShutting down server...")
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        typer.echo(f"Error starting server: {e}", err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    typer.run(main)
