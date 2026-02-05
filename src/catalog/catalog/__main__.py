"""Catalog CLI entry point.

Run with:
    uv run python -m catalog <command>

Example:
    uv run python -m catalog eval golden
    uv run python -m catalog eval compare "search query"
"""

from catalog.cli import main

if __name__ == "__main__":
    main()
