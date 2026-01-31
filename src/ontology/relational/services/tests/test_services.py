"""Tests for catalog services."""

import pytest
from advanced_alchemy.filters import LimitOffset
from sqlalchemy.ext.asyncio import AsyncSession

from ontology.relational.models import Catalog as CatalogORM, Repository as RepositoryORM
from ontology.schema import (
    CatalogCreate,
    CatalogResponse,
    CatalogUpdate,
    RepositoryCreate,
    RepositoryResponse,
    RepositoryUpdate,
    ResourceCreate,
    ResourceResponse,
)
from ontology.relational.services import (
    CatalogService,
    RepositoryService,
    ResourceService,
)


class TestCatalogService:
    """Tests for CatalogService."""

    @pytest.mark.asyncio
    async def test_create_catalog(self, db_session: AsyncSession):
        """Test creating a catalog."""
        service = CatalogService(session=db_session)

        data = CatalogCreate(
            id="cat:test",
            title="Test Catalog",
            description="A test catalog",
        )

        catalog_orm = await service.create(data)
        result = CatalogResponse.model_validate(catalog_orm)

        assert result.id == "cat:test"
        assert result.title == "Test Catalog"
        assert result.id is not None

    @pytest.mark.asyncio
    async def test_get_catalog(
        self, db_session: AsyncSession, sample_catalog: CatalogORM
    ):
        """Test getting a catalog by ID."""
        service = CatalogService(session=db_session)

        catalog_orm = await service.get(sample_catalog.id)
        result = CatalogResponse.model_validate(catalog_orm)

        assert result.id == sample_catalog.id
        assert result.id == sample_catalog.id

    @pytest.mark.asyncio
    async def test_get_catalog_by_identifier(
        self, db_session: AsyncSession, sample_catalog: CatalogORM
    ):
        """Test getting a catalog by identifier."""
        service = CatalogService(session=db_session)

        catalog_orm = await service.get_one_or_none(id=sample_catalog.id)

        assert catalog_orm is not None
        result = CatalogResponse.model_validate(catalog_orm)
        assert result.id == sample_catalog.id
        assert result.id == sample_catalog.id

    @pytest.mark.asyncio
    async def test_list_catalogs(
        self, db_session: AsyncSession, sample_catalog: CatalogORM
    ):
        """Test listing catalogs."""
        service = CatalogService(session=db_session)

        # Create another catalog
        data = CatalogCreate(id="cat:test2", title="Test Catalog 2")
        await service.create(data)

        results, total = await service.list_and_count(LimitOffset(10, 0))

        assert total == 2
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_update_catalog(
        self, db_session: AsyncSession, sample_catalog: CatalogORM
    ):
        """Test updating a catalog."""
        service = CatalogService(session=db_session)

        update_data = CatalogUpdate(title="Updated Title")
        catalog_orm = await service.update(update_data, sample_catalog.id)
        result = CatalogResponse.model_validate(catalog_orm)

        assert result.id == sample_catalog.id
        assert result.title == "Updated Title"

    @pytest.mark.asyncio
    async def test_delete_catalog(
        self, db_session: AsyncSession, sample_catalog: CatalogORM
    ):
        """Test deleting a catalog."""
        service = CatalogService(session=db_session)

        await service.delete(sample_catalog.id)

        # Verify deletion
        retrieved = await service.get_one_or_none(id=sample_catalog.id)
        assert retrieved is None


class TestRepositoryService:
    """Tests for RepositoryService."""

    @pytest.mark.asyncio
    async def test_create_repository(self, db_session: AsyncSession):
        """Test creating a repository."""
        service = RepositoryService(session=db_session)

        data = RepositoryCreate(
            id="repo:test",
            title="Test Repository",
            service_name="GitHub",
        )

        repository_orm = await service.create(data)
        result = RepositoryResponse.model_validate(repository_orm)

        assert result.id == "repo:test"
        assert result.title == "Test Repository"
        assert result.service_name == "GitHub"
        assert result.id is not None

    @pytest.mark.asyncio
    async def test_get_repository(
        self, db_session: AsyncSession, sample_repository: RepositoryORM
    ):
        """Test getting a repository by ID."""
        service = RepositoryService(session=db_session)

        repository_orm = await service.get(sample_repository.id)
        result = RepositoryResponse.model_validate(repository_orm)

        assert result.id == sample_repository.id
        assert result.id == sample_repository.id

    @pytest.mark.asyncio
    async def test_get_repository_by_identifier(
        self, db_session: AsyncSession, sample_repository: RepositoryORM
    ):
        """Test getting a repository by identifier."""
        service = RepositoryService(session=db_session)

        repository_orm = await service.get_one_or_none(id=sample_repository.id)

        assert repository_orm is not None
        result = RepositoryResponse.model_validate(repository_orm)
        assert result.id == sample_repository.id
        assert result.id == sample_repository.id

    @pytest.mark.asyncio
    async def test_list_repositories(
        self, db_session: AsyncSession, sample_repository: RepositoryORM
    ):
        """Test listing repositories."""
        service = RepositoryService(session=db_session)

        results, total = await service.list_and_count(LimitOffset(10, 0))

        assert total >= 1
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_update_repository(
        self, db_session: AsyncSession, sample_repository: RepositoryORM
    ):
        """Test updating a repository."""
        service = RepositoryService(session=db_session)

        update_data = RepositoryUpdate(title="Updated Repository")
        repository_orm = await service.update(update_data, sample_repository.id)
        result = RepositoryResponse.model_validate(repository_orm)

        assert result.id == sample_repository.id
        assert result.title == "Updated Repository"


class TestResourceService:
    """Tests for ResourceService."""

    @pytest.mark.asyncio
    async def test_create_resource(
        self, db_session: AsyncSession, sample_catalog: CatalogORM
    ):
        """Test creating a resource."""
        service = ResourceService(session=db_session)

        data = ResourceCreate(
            id="res:test",
            catalog="cat:test",
            catalog_id=sample_catalog.id,
            title="Test Resource",
            location="https://example.com/resource",
        )

        resource_orm = await service.create(data)
        result = ResourceResponse.model_validate(resource_orm)

        assert result.id == "res:test"
        assert result.title == "Test Resource"
        assert result.location == "https://example.com/resource"
        assert result.catalog_id == sample_catalog.id
        assert result.id is not None

    @pytest.mark.asyncio
    async def test_get_resource(
        self, db_session: AsyncSession, sample_catalog: CatalogORM
    ):
        """Test getting a resource by ID."""
        service = ResourceService(session=db_session)

        # Create a resource first
        data = ResourceCreate(
            id="res:test",
            catalog="cat:test",
            catalog_id=sample_catalog.id,
            title="Test Resource",
            location="https://example.com/resource",
        )
        created_orm = await service.create(data)

        resource_orm = await service.get(created_orm.id)
        result = ResourceResponse.model_validate(resource_orm)

        assert result.id == created_orm.id
        assert result.id == "res:test"

    @pytest.mark.asyncio
    async def test_list_resources(
        self, db_session: AsyncSession, sample_catalog: CatalogORM
    ):
        """Test listing resources."""
        service = ResourceService(session=db_session)

        # Create a resource
        data = ResourceCreate(
            id="res:test",
            catalog="cat:test",
            catalog_id=sample_catalog.id,
            title="Test Resource",
            location="https://example.com/resource",
        )
        await service.create(data)

        results, total = await service.list_and_count(LimitOffset(10, 0))

        assert total >= 1
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_list_resources_by_catalog(
        self, db_session: AsyncSession, sample_catalog: CatalogORM
    ):
        """Test listing resources filtered by catalog."""
        from ontology.relational.models import Resource as ResourceORM

        service = ResourceService(session=db_session)

        # Create resources
        data1 = ResourceCreate(
            id="res:1",
            catalog="cat:test",
            catalog_id=sample_catalog.id,
            title="Resource 1",
            location="https://example.com/resource1",
        )
        data2 = ResourceCreate(
            id="res:2",
            catalog="cat:test",
            catalog_id=sample_catalog.id,
            title="Resource 2",
            location="https://example.com/resource2",
        )
        await service.create(data1)
        await service.create(data2)

        results, total = await service.list_and_count(
            ResourceORM.catalog_id == sample_catalog.id
        )

        assert total == 2
        assert len(results) == 2
