"""CLI entry point for loading YAML datasets into the database.

This module provides a command-line interface for developers to load
test data from YAML files into the database.

Usage:
    uv run python -m ontology.loader.cli [path]

Args:
    path: Path to YAML file or directory containing YAML files
          (defaults to src/ontology/loader/data/)
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from ontology.relational.database import get_async_session_factory
from ontology.loader.loader import load_yaml_dataset

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main(path: str | None = None) -> None:
    """Load YAML datasets into the database.

    Args:
        path: Optional path to YAML file or directory. If not provided,
              defaults to src/ontology/loader/data/
    """
    # Determine path
    if path is None:
        # Default to data directory relative to this file
        default_path = Path(__file__).parent / "data"
        data_path = default_path
    else:
        data_path = Path(path)

    if not data_path.exists():
        logger.error(f"Path does not exist: {data_path}")
        sys.exit(1)

    logger.info(f"Loading datasets from: {data_path}")

    # Ensure database tables exist
    from sqlalchemy import create_engine
    from ontology.settings import get_settings
    from ontology.relational.database import Base

    settings = get_settings()
    # Create synchronous engine for table creation
    sync_url = settings.database.url.replace("sqlite+aiosqlite", "sqlite")
    sync_engine = create_engine(sync_url)
    logger.info("Creating database tables if they don't exist...")
    Base.metadata.create_all(sync_engine)
    sync_engine.dispose()
    logger.info("Database tables ready")

    # Get database session
    async_session_factory = get_async_session_factory()
    async with async_session_factory() as session:
        try:
            # Load datasets
            summary = await load_yaml_dataset(data_path, session)

            # Print summary
            logger.info("=" * 60)
            logger.info("LOAD COMPLETE - Summary:")
            logger.info("=" * 60)
            for key, value in summary.items():
                logger.info(f"  {key}: {value}")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"Failed to load datasets: {e}", exc_info=True)
            sys.exit(1)


if __name__ == "__main__":
    # Get path from command line args if provided
    path_arg = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(main(path_arg))
