"""Database layer for the ontology system.

This module provides database models, connection management, and session handling
using Advanced-Alchemy for infrastructure configuration.
"""

from ontologizer.relational.database.config import create_alchemy_config, get_alchemy_config
from ontologizer.relational.database.connection import dispose_engine, get_engine, get_session, dispose_engine_async, register_all_listeners
from ontologizer.relational.database.models import CURIEBase, JSONDict, Base, IdBase

# Import legacy session utilities for backwards compatibility
# These are being phased out in favor of get_session() from connection
from ontologizer.relational.database.session import (
    async_transactional,
    create_all_tables,
    create_all_tables_async,
    create_async_session_factory,
    create_session_factory,
    drop_all_tables,
    drop_all_tables_async,
    get_async_session,
    get_async_session_factory,
    get_session_factory,
    transactional,
)

# Note: session.get_session (sync) is imported for CLI compatibility
# connection.get_session (async) is preferred for async contexts
from ontologizer.relational.database.session import get_session as get_sync_session

__all__ = [
    # Models
    "CURIEBase",
    "JSONDict",
    "Base",
    "IdBase",
    # Connection (Advanced-Alchemy)
    "create_alchemy_config",
    "dispose_engine",
    "get_alchemy_config",
    "get_engine",
    "get_session",
    # Legacy Session API (for backwards compatibility)
    "async_transactional",
    "create_all_tables",
    "create_all_tables_async",
    "create_async_session_factory",
    "create_session_factory",
    "drop_all_tables",
    "drop_all_tables_async",
    "get_async_session",
    "get_async_session_factory",
    "get_session_factory",
    "get_sync_session",
    "transactional",
]
