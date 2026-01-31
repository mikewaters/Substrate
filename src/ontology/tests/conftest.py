"""Shared async test fixtures for the ontology package."""

from __future__ import annotations

import uuid
from pathlib import Path
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from ontology.relational.models import (  # noqa: F401
    Bookmark,
    Catalog,
    Collection,
    Document,
    Note,
    Purpose,
    Repository,
    Resource,
)
from ontology.relational.database import create_alchemy_config
from ontology.relational.database import register_all_listeners
from ontology.relational.database import Base

# Import all models to register them with SQLAlchemy metadata
# This must happen before Base.metadata.create_all is called
from ontology.relational.models import (  # noqa: F401
    Taxonomy,
    Topic,
    TopicClosure,
    TopicEdge,
)
from ontology.relational.models.classifier import (  # noqa: F401
    DocumentClassification,
    DocumentTopicAssignment,
    Match,
    TopicSuggestion,
)


async def _create_test_engine(db_path: Path) -> AsyncEngine:
    """Create a test engine using Advanced-Alchemy configuration.

    Args:
        db_path: Path to the test database file

    Returns:
        Configured AsyncEngine instance with schema created
    """
    # Create Advanced-Alchemy config for test database
    connection_string = f"sqlite+aiosqlite:///{db_path}"
    config = create_alchemy_config(
        connection_string=connection_string,
        echo=False,
    )

    # Get engine and register listeners
    engine = config.get_engine()
    register_all_listeners(engine)

    # Create schema
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    return engine


@pytest_asyncio.fixture
async def db_session(
    tmp_path_factory: pytest.TempPathFactory,
) -> AsyncGenerator[AsyncSession, None]:
    """Provide an isolated async database session per test.

    This fixture uses Advanced-Alchemy's session management to provide
    a clean database session for each test. The session is automatically
    rolled back and cleaned up after the test completes.

    Yields:
        AsyncSession: Isolated database session for the test
    """
    db_dir = tmp_path_factory.mktemp("ontology-db")
    db_path = db_dir / f"{uuid.uuid4()}.db"

    # Create engine using Advanced-Alchemy config
    engine = await _create_test_engine(db_path)

    # Create Advanced-Alchemy config and use its session factory
    connection_string = f"sqlite+aiosqlite:///{db_path}"
    config = create_alchemy_config(
        connection_string=connection_string,
        echo=False,
    )

    # Get session from Advanced-Alchemy
    async with config.get_session() as session:
        try:
            yield session
        finally:
            # Rollback any uncommitted changes
            await session.rollback()

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    if db_path.exists():
        db_path.unlink()
