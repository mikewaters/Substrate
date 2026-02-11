"""Tests for TaxonomyService.

This module tests the service layer for taxonomies, including conversion
between Pydantic schemas and domain models.
"""

import pytest
from advanced_alchemy.exceptions import NotFoundError
from advanced_alchemy.filters import LimitOffset

from ontologizer.schema.taxonomy import TaxonomyCreate, TaxonomyUpdate
from ontologizer.relational.services import TaxonomyService

pytestmark = pytest.mark.asyncio


class TestTaxonomyServiceCreate:
    """Tests for creating taxonomies via service."""

    async def test_create_taxonomy_basic(
        self, taxonomy_service: TaxonomyService
    ) -> None:
        """Test creating a taxonomy with all fields."""
        schema = TaxonomyCreate(
            title="Test Taxonomy",
            description="A test taxonomy",
            skos_uri="http://example.org/test",
        )

        response = await taxonomy_service.create(schema)

        assert response.title == "Test Taxonomy"
        assert response.description == "A test taxonomy"
        assert response.skos_uri == "http://example.org/test"
        assert response.id is not None
        assert response.created_at is not None
        assert response.updated_at is not None

    async def test_create_taxonomy_minimal(
        self, taxonomy_service: TaxonomyService
    ) -> None:
        """Test creating a taxonomy with minimal fields."""
        schema = TaxonomyCreate(title="Minimal Taxonomy")

        response = await taxonomy_service.create(schema)

        assert response.title == "Minimal Taxonomy"
        assert response.description is None
        assert response.skos_uri is None


class TestTaxonomyServiceRead:
    """Tests for reading taxonomies via service."""

    async def test_get_taxonomy_by_id(self, taxonomy_service: TaxonomyService) -> None:
        """Test getting a taxonomy by ID."""
        # Create
        create_schema = TaxonomyCreate(title="Test Taxonomy")
        created = await taxonomy_service.create(create_schema)

        # Get
        retrieved = await taxonomy_service.get(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.title == created.title

    async def test_get_taxonomy_not_found(
        self, taxonomy_service: TaxonomyService
    ) -> None:
        """Test getting a non-existent taxonomy returns None."""
        with pytest.raises(NotFoundError):
            await taxonomy_service.get("tax:test")

    async def test_list_taxonomies_empty(
        self, taxonomy_service: TaxonomyService
    ) -> None:
        """Test listing taxonomies when none exist."""
        response = await taxonomy_service.list()

        assert len(response) == 0

    async def test_list_taxonomies_with_data(
        self, taxonomy_service: TaxonomyService
    ) -> None:
        """Test listing taxonomies with data."""
        # Create some taxonomies
        for i in range(3):
            schema = TaxonomyCreate(title=f"Taxonomy {i}")
            await taxonomy_service.create(schema)

        # List
        response = await taxonomy_service.list()

        assert len(response) == 3

    async def test_list_taxonomies_with_pagination(
        self, taxonomy_service: TaxonomyService
    ) -> None:
        """Test listing taxonomies with pagination."""
        # Create some taxonomies
        for i in range(5):
            schema = TaxonomyCreate(title=f"Taxonomy {i}")
            await taxonomy_service.create(schema)

        # List with pagination
        response = await taxonomy_service.list(LimitOffset(limit=2, offset=1))
        assert len(response) == 2


class TestTaxonomyServiceUpdate:
    """Tests for updating taxonomies via service."""

    async def test_update_taxonomy_title(
        self, taxonomy_service: TaxonomyService
    ) -> None:
        """Test updating a taxonomy's title."""
        # Create
        create_schema = TaxonomyCreate(title="Original Title")
        created = await taxonomy_service.create(create_schema)

        # Update
        update_schema = TaxonomyUpdate(title="Updated Title")
        updated = await taxonomy_service.update(update_schema, created.id)

        assert updated is not None
        assert updated.title == "Updated Title"
        assert updated.id == created.id

    async def test_update_taxonomy_multiple_fields(
        self, taxonomy_service: TaxonomyService
    ) -> None:
        """Test updating multiple fields."""
        # Create
        create_schema = TaxonomyCreate(title="Original")
        created = await taxonomy_service.create(create_schema)

        # Update
        update_schema = TaxonomyUpdate(
            title="Updated",
            description="New description",
        )
        updated = await taxonomy_service.update(update_schema, created.id)

        assert updated is not None
        assert updated.title == "Updated"
        assert updated.description == "New description"

    async def test_update_taxonomy_not_found(
        self, taxonomy_service: TaxonomyService
    ) -> None:
        """Test updating a non-existent taxonomy returns None."""
        update_schema = TaxonomyUpdate(title="New Title")
        with pytest.raises(NotFoundError):
            await taxonomy_service.update(update_schema, "tax:test")


class TestTaxonomyServiceDelete:
    """Tests for deleting taxonomies via service."""

    async def test_delete_taxonomy(self, taxonomy_service: TaxonomyService) -> None:
        """Test deleting a taxonomy."""
        # Create
        create_schema = TaxonomyCreate(title="To Delete")
        created = await taxonomy_service.create(create_schema)

        # Delete
        await taxonomy_service.delete(created.id)

        # Verify deleted
        with pytest.raises(NotFoundError):
            await taxonomy_service.get(created.id)

    async def test_delete_taxonomy_not_found(
        self, taxonomy_service: TaxonomyService
    ) -> None:
        """Test deleting a non-existent taxonomy returns False."""
        with pytest.raises(NotFoundError):
            await taxonomy_service.delete("tax:test")
