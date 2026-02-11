"""Async fixtures for ontology catalog module tests."""

from __future__ import annotations

from ontologizer.api.tests.conftest import client  # noqa: F401
from ontologizer.relational.models import (
    Catalog as CatalogORM,
)
from ontologizer.relational.models import (
    Repository as RepositoryORM,
)
from ontologizer.relational.models import Taxonomy as TaxonomyORM
from ontologizer.relational.models import Topic as TopicORM
from ontologizer.relational.repository import (
    TopicEdgeRepository,
    TopicRepository,
)
from ontologizer.relational.repository import TaxonomyRepository
from ontologizer.relational.services import (
    TaxonomyService,
    TopicQueryService,
    TopicTaxonomyService,
)
from ontologizer.relational.services.topic_suggestion import TopicSuggestionService
from ontologizer.tests.conftest import *  # noqa: F401,F403  # noqa: F401,F403

# Toggle to inspect raw SQLAlchemy exceptions during debugging.
DEBUG_SQLALCHEMY_EXCEPTIONS = False


@pytest_asyncio.fixture
async def sample_catalog(db_session: AsyncSession) -> CatalogORM:
    """Create a sample catalog ORM model for testing."""
    catalog = CatalogORM(
        id="cat:test",
        title="Test Catalog",
        description="A catalog for testing",
    )
    db_session.add(catalog)
    await db_session.flush()
    return catalog


@pytest_asyncio.fixture
async def sample_repository(db_session: AsyncSession) -> RepositoryORM:
    """Create a sample repository ORM model for testing."""
    repository = RepositoryORM(
        id="repo:test",
        title="Test Repository",
        service_name="GitHub",
        description="A repository for testing",
    )
    db_session.add(repository)
    await db_session.flush()
    return repository


"""Async fixtures for ontology information module tests."""


@pytest_asyncio.fixture
async def topic_repo(db_session: AsyncSession) -> TopicRepository:
    """Create a TopicRepository for testing."""
    return TopicRepository(
        session=db_session, wrap_exceptions=not DEBUG_SQLALCHEMY_EXCEPTIONS
    )


@pytest_asyncio.fixture
async def edge_repo(topic_repo: TopicRepository) -> TopicEdgeRepository:
    """Create a TopicEdgeRepository for testing."""
    return TopicEdgeRepository(
        topic_repo=topic_repo,
        session=topic_repo.session,
        wrap_exceptions=not DEBUG_SQLALCHEMY_EXCEPTIONS,
    )


@pytest_asyncio.fixture
async def taxonomy_repo(db_session: AsyncSession) -> TaxonomyRepository:
    """Create a TaxonomyRepository for testing."""
    return TaxonomyRepository(
        session=db_session, wrap_exceptions=not DEBUG_SQLALCHEMY_EXCEPTIONS
    )


@pytest_asyncio.fixture
async def taxonomy_service(db_session: AsyncSession) -> TaxonomyService:
    """Create a TaxonomyService for testing."""
    return TaxonomyService(session=db_session)


@pytest_asyncio.fixture
async def topic_service(db_session: AsyncSession) -> TopicTaxonomyService:
    """Create a TopicService for testing."""
    return TopicTaxonomyService(session=db_session)


@pytest_asyncio.fixture
async def query_service(db_session: AsyncSession) -> TopicQueryService:
    """Create a TopicQueryService for testing."""
    return TopicQueryService(session=db_session)


@pytest_asyncio.fixture
async def classifier_service(db_session: AsyncSession) -> TopicSuggestionService:
    """Create a ClassifierService for testing."""
    return TopicSuggestionService(session=db_session)


@pytest_asyncio.fixture
async def sample_taxonomy(db_session: AsyncSession) -> TaxonomyORM:
    """Create a sample taxonomy ORM model for testing."""
    taxonomy = TaxonomyORM(
        title="Test Taxonomy",
        description="A taxonomy for testing",
    )
    db_session.add(taxonomy)
    await db_session.flush()
    return taxonomy


@pytest_asyncio.fixture
async def sample_topic(
    db_session: AsyncSession, sample_taxonomy: TaxonomyORM
) -> TopicORM:
    """Create a sample topic ORM model for testing."""
    topic = TopicORM(
        taxonomy_id=sample_taxonomy.id,
        title="Test Topic",
        slug="test-topic",
        description="A topic for testing",
        status="draft",
    )
    db_session.add(topic)
    await db_session.flush()
    return topic


@pytest_asyncio.fixture
async def sample_taxonomy_domain(db_session: AsyncSession) -> Taxonomy:
    """Create a sample taxonomy domain model for testing."""
    taxonomy_orm = TaxonomyORM(
        title="Test Taxonomy",
        description="A taxonomy for testing",
    )
    db_session.add(taxonomy_orm)
    await db_session.flush()

    return Taxonomy(
        id=taxonomy_orm.id,
        title=taxonomy_orm.title,
        description=taxonomy_orm.description,
        skos_uri=taxonomy_orm.skos_uri,
        created_at=taxonomy_orm.created_at,
        updated_at=taxonomy_orm.updated_at,
    )
