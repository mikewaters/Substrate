"""Dependency injection for FastAPI.

This module provides dependencies for database sessions and services
using Advanced-Alchemy's session management.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from ontologizer.relational.database import get_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session dependency using Advanced-Alchemy.

    This provides a database session with proper lifecycle management:
    - Automatic commit on success
    - Automatic rollback on exception
    - Proper cleanup after request

    Yields:
        AsyncSession: Database session for the request
    """
    async for session in get_session():
        yield session
