"""agentlayer.database - Shared SQLAlchemy engine creation and SQLite pragmas.

Provides low-level database engine creation for SQLite with optimal pragma
configuration. Higher-level registry and session management live in
domain-specific packages (e.g. catalog.store.database).
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session

__all__ = [
    "create_engine_for_path",
    "get_session",
]


def _set_sqlite_pragmas(dbapi_connection: Any, connection_record: Any) -> None:
    """Set SQLite pragmas for optimal performance and data integrity.

    Enables:
    - WAL mode for better concurrent access
    - Foreign key enforcement
    - Synchronous mode for durability
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def create_engine_for_path(database_path: Path, *, echo: bool = False) -> Engine:
    """Create a SQLAlchemy engine for the given database path.

    Creates the parent directory if it doesn't exist.
    Does NOT create tables - use a registry or metadata.create_all for that.

    Args:
        database_path: Path to the SQLite database file.
        echo: If True, log all SQL statements (default: False).

    Returns:
        A configured SQLAlchemy Engine instance.
    """
    database_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        f"sqlite:///{database_path}",
        echo=echo,
        pool_pre_ping=True,
        connect_args={"timeout": 30},
    )
    event.listen(engine, "connect", _set_sqlite_pragmas)

    return engine


@contextmanager
def get_session(session_factory: Callable[[], Session]) -> Generator[Session, None, None]:
    """Generic session context manager that uses a provided factory.

    Yields a session, commits on success, rolls back on exception.

    Args:
        session_factory: Callable returning a new SQLAlchemy Session.

    Yields:
        A SQLAlchemy Session instance.
    """
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
