"""Allow running the loader CLI as a module.

Usage:
    uv run python -m ontology.loader [path]
"""

from ontology.loader.cli import main
import asyncio
import sys

if __name__ == "__main__":
    path_arg = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(main(path_arg))
