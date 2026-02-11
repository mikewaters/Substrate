"""Tests for catalog repositories."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ontologizer.relational.models import (
    Catalog as CatalogORM,
    Repository as RepositoryORM,
    Resource as ResourceORM,
)
from ontologizer.relational.repository import (
    CatalogRepository,
    RepositoryRepository,
    ResourceRepository,
)


class TestCatalogRepository:
    """Tests for CatalogRepository."""

    @pytest.mark.asyncio
    async def test_add_catalog(self, db_session: AsyncSession):
        """Test adding a catalog."""
        repo = CatalogRepository(session=db_session)

        catalog = CatalogORM(
            id="cat:test",
            title="Test Catalog",
            description="A test catalog",
        )

        result = await repo.add(catalog)
        await db_session.commit()

        assert result.id is not None
        assert result.id == "cat:test"
        assert result.title == "Test Catalog"

    @pytest.mark.asyncio
    async def test_get_catalog(
        self, db_session: AsyncSession, sample_catalog: CatalogORM
    ):
        """Test getting a catalog by ID."""
        repo = CatalogRepository(session=db_session)

        result = await repo.get(sample_catalog.id)

        assert result.id == sample_catalog.id

    @pytest.mark.asyncio
    async def test_list_catalogs(
        self, db_session: AsyncSession, sample_catalog: CatalogORM
    ):
        """Test listing catalogs."""
        repo = CatalogRepository(session=db_session)

        # Add another catalog
        catalog2 = CatalogORM(id="cat:test2", title="Test Catalog 2")
        await repo.add(catalog2)
        await db_session.commit()

        results = await repo.list()

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_update_catalog(
        self, db_session: AsyncSession, sample_catalog: CatalogORM
    ):
        """Test updating a catalog."""
        repo = CatalogRepository(session=db_session)

        sample_catalog.title = "Updated Title"
        result = await repo.update(sample_catalog)
        await db_session.commit()

        assert result.title == "Updated Title"

    @pytest.mark.asyncio
    async def test_delete_catalog(
        self, db_session: AsyncSession, sample_catalog: CatalogORM
    ):
        """Test deleting a catalog."""
        repo = CatalogRepository(session=db_session)

        await repo.delete(sample_catalog.id)
        await db_session.commit()

        result = await repo.get_one_or_none(id=sample_catalog.id)
        assert result is None


class TestRepositoryRepository:
    """Tests for RepositoryRepository."""

    @pytest.mark.asyncio
    async def test_add_repository(self, db_session: AsyncSession):
        """Test adding a repository."""
        repo = RepositoryRepository(session=db_session)

        repository = RepositoryORM(
            id="repo:test",
            title="Test Repository",
            service_name="GitHub",
        )

        result = await repo.add(repository)
        await db_session.commit()

        assert result.id is not None
        assert result.id == "repo:test"
        assert result.service_name == "GitHub"

    @pytest.mark.asyncio
    async def test_get_repository(
        self, db_session: AsyncSession, sample_repository: RepositoryORM
    ):
        """Test getting a repository by ID."""
        repo = RepositoryRepository(session=db_session)

        result = await repo.get(sample_repository.id)

        assert result.id == sample_repository.id


class TestResourceRepository:
    """Tests for ResourceRepository."""

    @pytest.mark.asyncio
    async def test_add_resource(
        self, db_session: AsyncSession, sample_catalog: CatalogORM
    ):
        """Test adding a resource."""
        repo = ResourceRepository(session=db_session)

        resource = ResourceORM(
            id="res:test",
            catalog="cat:test",
            catalog_id=sample_catalog.id,
            title="Test Resource",
            location="https://example.com/resource",
        )

        result = await repo.add(resource)
        await db_session.commit()

        assert result.id is not None
        assert result.id == "res:test"
        assert result.catalog == "cat:test"
        assert result.location == "https://example.com/resource"

    @pytest.mark.asyncio
    async def test_get_resource(
        self, db_session: AsyncSession, sample_catalog: CatalogORM
    ):
        """Test getting a resource by ID."""
        repo = ResourceRepository(session=db_session)

        # Create a resource first
        resource = ResourceORM(
            id="res:test",
            catalog="cat:test",
            catalog_id=sample_catalog.id,
            title="Test Resource",
            location="https://example.com/resource",
        )
        added = await repo.add(resource)
        await db_session.commit()

        result = await repo.get(added.id)

        assert result.id == added.id
        assert result.id == "res:test"

    @pytest.mark.asyncio
    async def test_list_resources(
        self, db_session: AsyncSession, sample_catalog: CatalogORM
    ):
        """Test listing resources."""
        repo = ResourceRepository(session=db_session)

        # Add multiple resources
        resource1 = ResourceORM(
            id="res:1",
            catalog="cat:test",
            catalog_id=sample_catalog.id,
            title="Resource 1",
            location="https://example.com/resource1",
        )
        resource2 = ResourceORM(
            id="res:2",
            catalog="cat:test",
            catalog_id=sample_catalog.id,
            title="Resource 2",
            location="https://example.com/resource2",
        )
        await repo.add(resource1)
        await repo.add(resource2)
        await db_session.commit()

        results = await repo.list()

        assert len(results) == 2
