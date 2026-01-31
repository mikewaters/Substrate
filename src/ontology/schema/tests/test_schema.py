"""Tests for catalog Pydantic schemas."""


import pytest
from pydantic import ValidationError

from ontology.schema import (
    BookmarkCreate,
    CatalogCreate,
    CatalogUpdate,
    CollectionCreate,
    DocumentCreate,
    NoteCreate,
    PurposeCreate,
    RepositoryCreate,
    ResourceCreate,
)


class TestCatalogSchemas:
    """Tests for Catalog schemas."""

    def test_catalog_create_valid(self):
        """Test creating a valid catalog schema."""
        data = {
            "id": "cat:test",
            "title": "Test Catalog",
            "description": "A test catalog",
            "taxonomies": ["tax:theme1", "tax:theme2"],
        }
        catalog = CatalogCreate(**data)

        assert catalog.id == "cat:test"
        assert catalog.title == "Test Catalog"
        assert catalog.description == "A test catalog"
        assert catalog.taxonomies == ["tax:theme1", "tax:theme2"]

    def test_catalog_create_minimal(self):
        """Test creating a minimal catalog schema."""
        catalog = CatalogCreate(id="cat:test", title="Test Catalog")

        assert catalog.id == "cat:test"
        assert catalog.title == "Test Catalog"
        assert catalog.description is None
        assert catalog.taxonomies == []

    def test_catalog_create_invalid_empty_title(self):
        """Test that empty title is rejected."""
        with pytest.raises(ValidationError):
            CatalogCreate(id="cat:test", title="")

    def test_catalog_update(self):
        """Test catalog update schema."""
        update = CatalogUpdate(title="Updated Title")

        assert update.title == "Updated Title"
        assert update.description is None


class TestRepositorySchemas:
    """Tests for Repository schemas."""

    def test_repository_create_valid(self):
        """Test creating a valid repository schema."""
        data = {
            "id": "repo:test",
            "title": "Test Repository",
            "service_name": "GitHub",
            "description": "A test repository",
        }
        repo = RepositoryCreate(**data)

        assert repo.id == "repo:test"
        assert repo.title == "Test Repository"
        assert repo.service_name == "GitHub"
        assert repo.description == "A test repository"

    def test_repository_create_minimal(self):
        """Test creating a minimal repository schema."""
        repo = RepositoryCreate(
            id="repo:test", title="Test Repository", service_name="GitHub"
        )

        assert repo.id == "repo:test"
        assert repo.title == "Test Repository"
        assert repo.service_name == "GitHub"
        assert repo.description is None


class TestPurposeSchemas:
    """Tests for Purpose schemas."""

    def test_purpose_create_valid(self):
        """Test creating a valid purpose schema."""
        data = {
            "id": "purpose:test",
            "title": "Test Purpose",
            "description": "A test purpose",
            "role": "primary",
            "meaning": "for testing",
        }
        purpose = PurposeCreate(**data)

        assert purpose.id == "purpose:test"
        assert purpose.title == "Test Purpose"
        assert purpose.description == "A test purpose"
        assert purpose.role == "primary"
        assert purpose.meaning == "for testing"

    def test_purpose_create_minimal(self):
        """Test creating a minimal purpose schema."""
        purpose = PurposeCreate(id="purpose:test", title="Test Purpose")

        assert purpose.id == "purpose:test"
        assert purpose.title == "Test Purpose"
        assert purpose.description is None
        assert purpose.role is None
        assert purpose.meaning is None


class TestResourceSchemas:
    """Tests for Resource schemas."""

    def test_resource_create_valid(self):
        """Test creating a valid resource schema."""
        catalog_id = "cat:test"
        data = {
            "id": "res:test",
            "catalog": "cat:test",
            "catalog_id": catalog_id,
            "title": "Test Resource",
            "description": "A test resource",
            "location": "https://example.com",
        }
        resource = ResourceCreate(**data)

        assert resource.catalog == "cat:test"
        assert resource.catalog_id == catalog_id
        assert resource.title == "Test Resource"
        assert resource.resource_type == "Resource"

    def test_bookmark_create(self):
        """Test creating a bookmark schema."""
        catalog_id = "cat:test"
        bookmark = BookmarkCreate(
            id="bm:test",
            catalog="cat:test",
            catalog_id=catalog_id,
            title="Test Bookmark",
            repository="repo:test",
            location="https://example.com",
        )

        assert bookmark.resource_type == "Bookmark"
        assert bookmark.repository == "repo:test"
        assert bookmark.location == "https://example.com"

    def test_collection_create(self):
        """Test creating a collection schema."""
        catalog_id = "cat:test"
        collection = CollectionCreate(
            id="col:test",
            catalog="cat:test",
            catalog_id=catalog_id,
            title="Test Collection",
            repository="repo:test",
            has_resources=["res:1", "res:2"],
        )

        assert collection.resource_type == "Collection"
        assert collection.repository == "repo:test"
        assert collection.has_resources == ["res:1", "res:2"]

    def test_document_create(self):
        """Test creating a document schema."""
        catalog_id = "cat:test"
        repo_id = "repo:test"
        document = DocumentCreate(
            id="doc:test",
            catalog="cat:test",
            catalog_id=catalog_id,
            repository="repo:test",
            repository_id=repo_id,
            title="Test Document",
            document_type="Journal",
        )

        assert document.resource_type == "Document"
        assert document.document_type == "Journal"

    def test_note_create(self):
        """Test creating a note schema."""
        catalog_id = "cat:test"
        repo_id = "repo:test"
        note = NoteCreate(
            id="note:test",
            catalog="cat:test",
            catalog_id=catalog_id,
            repository="repo:test",
            repository_id=repo_id,
            title="Test Note",
            note_type="Idea",
        )

        assert note.resource_type == "Note"
        assert note.note_type == "Idea"

    def test_resource_create_invalid_type(self):
        """Test that invalid resource type is rejected."""
        catalog_id = "cat:test"
        with pytest.raises(ValidationError):
            ResourceCreate(
                id="res:test",
                catalog="cat:test",
                catalog_id=catalog_id,
                title="Test Resource",
                location="https://example.com/resource",
                resource_type="InvalidType",  # type: ignore
            )
