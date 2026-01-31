"""Database connection management using Advanced-Alchemy.

This module provides database engine and session management using
Advanced-Alchemy's configuration system. It bridges the ontology
application settings with Advanced-Alchemy's infrastructure.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from ontology.relational.database.config import get_alchemy_config
from ontology.relational.database.listeners import register_all_listeners

logger = logging.getLogger(__name__)


# Global engine instance (initialized lazily)
_engine: AsyncEngine | None = None
_listeners_registered: bool = False


def get_engine(reload: bool = False) -> AsyncEngine:
    """Get the global database engine instance.

    This function returns a singleton engine instance managed by
    Advanced-Alchemy's configuration. Event listeners for database-specific
    optimizations are registered automatically on first access.

    Args:
        reload: If True, recreate the engine from current settings

    Returns:
        SQLAlchemy AsyncEngine instance
    """
    global _engine, _listeners_registered

    if _engine is None or reload:
        # Get engine from Advanced-Alchemy config
        config = get_alchemy_config(reload=reload)
        _engine = config.get_engine()

        # Register database-specific event listeners
        if not _listeners_registered or reload:
            register_all_listeners(_engine)
            _listeners_registered = True

        logger.info("Database engine initialized via Advanced-Alchemy")

    return _engine


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session.

    This is a context manager that provides a database session with
    proper lifecycle management (commit on success, rollback on error).

    Yields:
        AsyncSession: Database session

    Example:
        async with get_session() as session:
            result = await session.execute(query)
    """
    config = get_alchemy_config()
    async with config.get_session() as session:
        yield session


async def dispose_engine_async() -> None:
    """Dispose of the global engine instance.

    This should be called when shutting down the application.
    Properly closes all connections and cleans up resources.
    """
    global _engine, _listeners_registered

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _listeners_registered = False
        logger.info("Database engine disposed")


def dispose_engine() -> None:
    """Synchronous helper to dispose of the global engine.

    This provides backwards compatibility for synchronous call sites
    such as existing test fixtures that are not yet async aware.
    """
    if _engine is None:
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        loop.create_task(dispose_engine_async())
    else:
        asyncio.run(dispose_engine_async())
