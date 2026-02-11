"""Database event listeners.

This module provides SQLAlchemy event listeners for database-specific
optimizations and configurations.
"""

import logging
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


def register_sqlite_listeners(engine: AsyncEngine, enable_wal: bool = True) -> None:
    """Register SQLite-specific event listeners for optimization.

    This configures SQLite connections with optimal settings for the ontology
    system, including:
    - Foreign key constraint enforcement
    - Write-Ahead Logging (WAL) for better concurrency
    - Synchronous mode optimization
    - Memory-based temporary storage
    - Increased cache size

    Args:
        engine: SQLAlchemy AsyncEngine instance
        enable_wal: Enable Write-Ahead Logging (default: True)
    """

    @event.listens_for(engine.sync_engine, "connect")
    def configure_sqlite_connection(dbapi_conn: Any, connection_record: Any) -> None:
        """Configure SQLite connection on connect.

        This listener is called whenever a new connection is created to the
        SQLite database. It sets up pragmas for optimal performance and behavior.

        Args:
            dbapi_conn: Database API connection object
            connection_record: Connection record (unused)
        """
        cursor = dbapi_conn.cursor()

        # Enable foreign key constraints (off by default in SQLite)
        cursor.execute("PRAGMA foreign_keys=ON")

        # Enable WAL mode for better concurrency
        # This allows multiple readers and one writer simultaneously
        if enable_wal:
            cursor.execute("PRAGMA journal_mode=WAL")
            logger.debug("SQLite WAL mode enabled")

        # Synchronous mode: NORMAL is faster than FULL and still safe with WAL
        cursor.execute("PRAGMA synchronous=NORMAL")

        # Use memory for temporary storage instead of disk
        cursor.execute("PRAGMA temp_store=MEMORY")

        # Set cache size to 64MB (negative value = KB)
        cursor.execute("PRAGMA cache_size=-64000")

        cursor.close()

    logger.debug("SQLite event listeners registered")


def register_all_listeners(engine: AsyncEngine) -> None:
    """Register all database event listeners based on engine type.

    This function detects the database type from the engine and registers
    appropriate event listeners.

    Args:
        engine: SQLAlchemy AsyncEngine instance
    """
    # Get the dialect name from the engine
    dialect_name = engine.dialect.name

    if dialect_name == "sqlite":
        register_sqlite_listeners(engine, enable_wal=True)
        logger.info("SQLite listeners registered")
    else:
        logger.info(f"No specific listeners for dialect: {dialect_name}")
