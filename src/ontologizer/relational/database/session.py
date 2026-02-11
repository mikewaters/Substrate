"""Database session management.

This module provides session factory and context managers for database
operations using SQLAlchemy async and sync sessions.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from typing import Any

from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from ontologizer.relational.database.connection import get_engine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Synchronous session utilities (retained for CLI compatibility)
# ---------------------------------------------------------------------------


def create_session_factory(
    engine: AsyncEngine | None = None,
    **session_kwargs: Any,
) -> sessionmaker[Session]:
    """Create a synchronous session factory bound to the async engine's sync engine.

    Args:
        engine: SQLAlchemy async engine (uses global engine if None)
        **session_kwargs: Additional arguments for sessionmaker

    Returns:
        Session factory
    """
    if engine is None:
        engine = get_engine()

    sync_engine = engine.sync_engine

    factory_config: dict[str, Any] = {
        "bind": sync_engine,
        "expire_on_commit": False,
        "autoflush": True,
        "autocommit": False,
    }

    factory_config.update(session_kwargs)

    return sessionmaker(**factory_config)


# Global synchronous session factory
_sync_session_factory: sessionmaker[Session] | None = None


def get_session_factory(reload: bool = False) -> sessionmaker[Session]:
    """Get the global synchronous session factory."""
    global _sync_session_factory

    if _sync_session_factory is None or reload:
        _sync_session_factory = create_session_factory()
        logger.debug("Synchronous session factory created")

    return _sync_session_factory


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Synchronous context manager for database sessions.

    Retained to support existing synchronous workflows (e.g. CLI tools).
    """
    factory = get_session_factory()
    session = factory()

    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def transactional() -> Generator[Session, None, None]:
    """Synchronous transactional context manager."""
    factory = get_session_factory()
    session = factory()

    try:
        yield session
        session.commit()
        logger.debug("Transaction committed")
    except Exception as e:
        session.rollback()
        logger.error("Transaction rolled back: %s", e)
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Asynchronous session utilities
# ---------------------------------------------------------------------------


def create_async_session_factory(
    engine: AsyncEngine | None = None,
    **session_kwargs: Any,
) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory.

    Args:
        engine: SQLAlchemy async engine (uses global engine if None)
        **session_kwargs: Additional arguments for async_sessionmaker

    Returns:
        Async session factory
    """
    if engine is None:
        engine = get_engine()

    factory_config: dict[str, Any] = {
        "bind": engine,
        "expire_on_commit": False,
        "autoflush": True,
        "autocommit": False,
        # "close_resets_only": False
    }

    factory_config.update(session_kwargs)

    return async_sessionmaker(**factory_config)


_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_async_session_factory(reload: bool = False) -> async_sessionmaker[AsyncSession]:
    """Get the global async session factory."""
    global _async_session_factory

    if _async_session_factory is None or reload:
        _async_session_factory = create_async_session_factory()
        logger.debug("Async session factory created")

    return _async_session_factory


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager for database sessions."""
    factory = get_async_session_factory()
    session = factory()

    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


@asynccontextmanager
async def async_transactional() -> AsyncGenerator[AsyncSession, None]:
    """Async transactional context manager."""
    factory = get_async_session_factory()
    session = factory()

    try:
        yield session
        await session.commit()
        logger.debug("Async transaction committed")
    except Exception as e:
        await session.rollback()
        logger.error("Async transaction rolled back: %s", e)
        raise
    finally:
        await session.close()


# ---------------------------------------------------------------------------
# Table management
# ---------------------------------------------------------------------------


async def create_all_tables_async(engine: AsyncEngine | None = None) -> None:
    """Create all tables using the async engine."""
    if engine is None:
        engine = get_engine()

    from ontologizer.relational.database.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("All tables created (async)")


async def drop_all_tables_async(engine: AsyncEngine | None = None) -> None:
    """Drop all tables using the async engine."""
    if engine is None:
        engine = get_engine()

    from ontologizer.relational.database.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    logger.warning("All tables dropped (async)")


def create_all_tables(engine: AsyncEngine | None = None) -> None:
    """Synchronous helper to create tables (for compatibility)."""
    asyncio.run(create_all_tables_async(engine))


def drop_all_tables(engine: AsyncEngine | None = None) -> None:
    """Synchronous helper to drop tables (for compatibility)."""
    asyncio.run(drop_all_tables_async(engine))
