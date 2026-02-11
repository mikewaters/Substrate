"""Advanced-Alchemy configuration bridge.

This module bridges the ontology application settings with Advanced-Alchemy's
database infrastructure configuration. It translates high-level application
settings into Advanced-Alchemy's EngineConfig and SQLAlchemyAsyncConfig.
"""

import logging
from pathlib import Path

from advanced_alchemy.config import (
    AlembicAsyncConfig,
    AsyncSessionConfig,
    EngineConfig,
    SQLAlchemyAsyncConfig,
)
from sqlalchemy.pool import StaticPool

from ontologizer.settings import get_settings

logger = logging.getLogger(__name__)


def create_alchemy_config(
    connection_string: str | None = None,
    echo: bool | None = None,
) -> SQLAlchemyAsyncConfig:
    """Create Advanced-Alchemy configuration from ontology settings.

    This function translates ontology application settings into Advanced-Alchemy's
    configuration format, setting up engine configuration, session management,
    and Alembic integration.

    Args:
        connection_string: Override connection string (uses settings if None)
        echo: Override echo setting (uses settings if None)

    Returns:
        Configured SQLAlchemyAsyncConfig instance
    """
    settings = get_settings()

    # Use overrides or fall back to settings
    conn_str = connection_string or settings.database.connection_string
    echo_sql = echo if echo is not None else settings.database.echo

    # Ensure database directory exists
    db_path = Path(settings.database.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Configure SQLite-specific engine settings
    # For SQLite with StaticPool, don't set pool_size, max_overflow, pool_timeout
    # as StaticPool doesn't use these parameters
    engine_config = EngineConfig(
        echo=echo_sql,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    # Configure session behavior
    session_config = AsyncSessionConfig(
        expire_on_commit=False,  # Don't expire objects after commit
    )

    # Configure Alembic for migrations
    alembic_config = AlembicAsyncConfig(
        script_location="src/ontology/database/migrations",
        version_table_name="alembic_version",
    )

    config = SQLAlchemyAsyncConfig(
        connection_string=conn_str,
        engine_config=engine_config,
        session_config=session_config,
        alembic_config=alembic_config,
        create_all=False,  # Use Alembic for schema management
    )

    logger.debug(
        f"Advanced-Alchemy config created: connection_string={conn_str}, "
        f"echo={echo_sql}"
    )

    return config


# Global configuration instance
_alchemy_config: SQLAlchemyAsyncConfig | None = None


def get_alchemy_config(reload: bool = False) -> SQLAlchemyAsyncConfig:
    """Get the global Advanced-Alchemy configuration instance.

    This provides a singleton pattern for the Advanced-Alchemy configuration,
    similar to the get_settings() pattern used for application settings.

    Args:
        reload: If True, recreate the configuration from current settings

    Returns:
        SQLAlchemyAsyncConfig instance
    """
    global _alchemy_config

    if _alchemy_config is None or reload:
        _alchemy_config = create_alchemy_config()
        logger.info("Advanced-Alchemy configuration initialized")

    return _alchemy_config
