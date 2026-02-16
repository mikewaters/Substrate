"""catalog.store.database - SQLAlchemy engine and session management.

Provides database connectivity for the idx library using SQLite with
multi-database support via ATTACH.

The catalog database stores metadata, FTS indexes, and resource hierarchy.
The content database stores document bodies (ATTACHed to catalog connections).

Example usage:
    from catalog.store.database import get_engine, get_session

    engine = get_engine()  # Returns catalog engine (with content ATTACHed)
    with get_session() as session:
        # perform database operations
        pass
"""

from collections.abc import Generator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from catalog.store.models.catalog import CatalogBase
from catalog.store.models.content import ContentBase
from catalog.store.fts import create_fts_table
from catalog.store.fts_chunk import create_chunks_fts_table

if TYPE_CHECKING:
    from catalog.core.settings import Settings

# Backward compatibility alias
Base = CatalogBase

__all__ = [
    "Base",
    "CatalogBase",
    "ContentBase",
    "DatabaseRegistry",
    "create_engine_for_path",
    "get_engine",
    "get_registry",
    "get_session",
    "get_session_factory",
]


DatabaseName = Literal["catalog", "content"]


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
    Does NOT create tables - use DatabaseRegistry for full initialization.

    Args:
        database_path: Path to the SQLite database file.
        echo: If True, log all SQL statements (default: False).

    Returns:
        A configured SQLAlchemy Engine instance.
    """
    # Ensure parent directory exists
    database_path.parent.mkdir(parents=True, exist_ok=True)

    # Create engine with SQLite-specific settings.
    # timeout: seconds to wait for lock; avoids immediate "database is locked"
    # when a single writer is busy (e.g. another process or tool).
    engine = create_engine(
        f"sqlite:///{database_path}",
        echo=echo,
        pool_pre_ping=True,
        connect_args={"timeout": 30},
    )
    # Register pragma listener BEFORE using the engine
    event.listen(engine, "connect", _set_sqlite_pragmas)

    return engine


class DatabaseRegistry:
    """Centralized registry for multiple SQLite databases.

    Manages the catalog and content databases with proper initialization order:
    1. Create all engines
    2. Create all tables (metadata.create_all)
    3. Register ATTACH event listeners

    The content database is ATTACHed to catalog connections, allowing
    cross-database queries via the 'content.' schema prefix.

    Note on WAL mode and transactions:
        With WAL mode, transactions spanning attached databases are NOT fully
        atomic. From SQLite docs: "If main is :memory: or journal_mode is WAL,
        transactions are atomic only within individual database files."
        This is an acceptable trade-off for better concurrency.
    """

    def __init__(self, settings: "Settings") -> None:
        """Initialize the database registry.

        Args:
            settings: Application settings containing database paths.
        """
        self._settings = settings

        # 1. Create all engines
        self._engines: dict[DatabaseName, Engine] = {
            "catalog": create_engine_for_path(settings.databases.catalog_path),
            "content": create_engine_for_path(settings.databases.content_path),
        }

        # 2. Create all tables (ORM)
        CatalogBase.metadata.create_all(self._engines["catalog"])
        ContentBase.metadata.create_all(self._engines["content"])

        # 3. Create FTS virtual tables (not managed by SQLAlchemy metadata)
        create_fts_table(self._engines["catalog"])
        create_chunks_fts_table(self._engines["catalog"])

        # 4. Register ATTACH listener on catalog engine
        # This ensures every connection from the pool has content attached
        event.listen(
            self._engines["catalog"],
            "connect",
            self._attach_content_database,
        )

    def _attach_content_database(
        self, dbapi_connection: Any, connection_record: Any
    ) -> None:
        """Attach the content database to a catalog connection.

        Called automatically for each new connection from the catalog pool.
        """
        content_path = self._settings.databases.content_path.expanduser()
        cursor = dbapi_connection.cursor()
        cursor.execute(f"ATTACH DATABASE '{content_path}' AS content")
        cursor.close()

    def get_engine(self, db: DatabaseName = "catalog") -> Engine:
        """Get the engine for the specified database.

        Args:
            db: Database name ('catalog' or 'content'). Defaults to 'catalog'.

        Returns:
            The SQLAlchemy Engine for the specified database.

        Raises:
            KeyError: If db is not a valid database name.
        """
        return self._engines[db]

    def get_session_factory(
        self, db: DatabaseName = "catalog"
    ) -> "sessionmaker[Session]":
        """Get a session factory for the specified database.

        Args:
            db: Database name ('catalog' or 'content'). Defaults to 'catalog'.

        Returns:
            A sessionmaker bound to the specified database engine.
        """
        return sessionmaker(bind=self._engines[db], expire_on_commit=False)


@lru_cache(maxsize=1)
def get_registry() -> DatabaseRegistry:
    """Get the singleton DatabaseRegistry instance.

    Creates the registry on first call, which initializes all databases.
    Subsequent calls return the cached registry.

    Returns:
        The singleton DatabaseRegistry instance.
    """
    from catalog.core.settings import get_settings

    return DatabaseRegistry(get_settings())


def get_engine(db: DatabaseName = "catalog") -> Engine:
    """Get the singleton SQLAlchemy engine for the specified database.

    This is a convenience wrapper around get_registry().get_engine().
    The default 'catalog' engine has the content database ATTACHed.

    Args:
        db: Database name ('catalog' or 'content'). Defaults to 'catalog'.

    Returns:
        The singleton Engine instance for the specified database.
    """
    return get_registry().get_engine(db)


@lru_cache(maxsize=1)
def get_session_factory() -> "sessionmaker[Session]":
    """Get the singleton session factory for the catalog database.

    Returns:
        A sessionmaker bound to the catalog engine (with content ATTACHed).
    """
    return get_registry().get_session_factory("catalog")


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context manager for database sessions.

    Yields a session connected to the catalog database (with content ATTACHed).
    The session is automatically committed on success and rolled back on exception.

    Yields:
        A SQLAlchemy Session instance.

    Example:
        with get_session() as session:
            session.add(some_model)
            # commits automatically on exit
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
