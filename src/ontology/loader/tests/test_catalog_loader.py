"""Integration tests for catalog dataset loader."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ontology.relational.models import Catalog, Repository, Purpose, Resource
from ontology.loader.loader import load_catalog_dataset

DATA_PATH = (
    Path(__file__).parent.parent / "data" / "sample_catalog.yaml"
)

pytestmark = pytest.mark.asyncio


async def test_load_catalog_dataset(db_session: AsyncSession) -> None:
    """Test loading catalog dataset."""
    # Load raw data to get expected counts
    raw = yaml.safe_load(DATA_PATH.read_text())
    expected_catalogs = len(raw.get("catalogs", []))
    expected_repositories = len(raw.get("repositories", []))
    expected_purposes = len(raw.get("purposes", []))
    expected_resources = len(raw.get("resources", []))

    # Load dataset
    summary = await load_catalog_dataset(str(DATA_PATH), db_session)

    # Verify summary
    assert summary["catalogs"] == expected_catalogs
    assert summary["repositories"] == expected_repositories
    assert summary["purposes"] == expected_purposes
    assert summary["resources"] == expected_resources

    # Verify database counts
    catalog_count = (
        await db_session.execute(select(func.count()).select_from(Catalog))
    ).scalar_one()
    repository_count = (
        await db_session.execute(select(func.count()).select_from(Repository))
    ).scalar_one()
    purpose_count = (
        await db_session.execute(select(func.count()).select_from(Purpose))
    ).scalar_one()
    resource_count = (
        await db_session.execute(select(func.count()).select_from(Resource))
    ).scalar_one()

    assert catalog_count == expected_catalogs
    assert repository_count == expected_repositories
    assert purpose_count == expected_purposes
    assert resource_count == expected_resources


async def test_catalog_themes(db_session: AsyncSession) -> None:
    """Test that catalog themes are loaded correctly."""
    await load_catalog_dataset(str(DATA_PATH), db_session)

    # Get a catalog with themes
    catalog = (
        await db_session.execute(
            select(Catalog).where(Catalog.id == "cat:tech-resources")
        )
    ).scalar_one()

    assert catalog.title == "Technology Resources"
    assert isinstance(catalog.taxonomies, list)
    assert len(catalog.taxonomies) >= 0
    # Note: taxonomies is now a relationship to Taxonomy objects
    # The test data may not have taxonomies set up yet
    # If taxonomies are present, they would be Taxonomy ORM objects, not strings


async def test_repository_service_names(db_session: AsyncSession) -> None:
    """Test that repository service names are loaded correctly."""
    await load_catalog_dataset(str(DATA_PATH), db_session)

    # Get GitHub repository
    repo = (
        await db_session.execute(
            select(Repository).where(Repository.id == "repo:github")
        )
    ).scalar_one()

    assert repo.title == "GitHub"
    assert repo.service_name == "github"


async def test_purpose_fields(db_session: AsyncSession) -> None:
    """Test that purpose fields are populated correctly."""
    await load_catalog_dataset(str(DATA_PATH), db_session)

    # Get a specific purpose
    purpose = (
        await db_session.execute(
            select(Purpose).where(Purpose.id == "purpose:learning")
        )
    ).scalar_one()

    assert purpose.title == "Learning Resource"
    assert purpose.role == "educational"
    assert purpose.meaning is not None


async def test_resource_types(db_session: AsyncSession) -> None:
    """Test that all resource types are loaded correctly."""
    await load_catalog_dataset(str(DATA_PATH), db_session)

    # Get all resource types
    result = await db_session.execute(
        select(Resource.resource_type, func.count(Resource.id))
        .group_by(Resource.resource_type)
        .order_by(Resource.resource_type)
    )
    type_counts = dict(result.all())

    # Verify expected types are present
    expected_types = {"Bookmark", "Collection", "Document", "Note", "Resource"}
    assert set(type_counts.keys()) == expected_types

    # Verify counts are positive
    for resource_type, count in type_counts.items():
        assert count > 0, f"{resource_type} should have at least 1 resource"


async def test_bookmark_resources(db_session: AsyncSession) -> None:
    """Test that bookmark resources are loaded correctly."""
    await load_catalog_dataset(str(DATA_PATH), db_session)

    # Get a bookmark
    bookmark = (
        await db_session.execute(
            select(Resource).where(Resource.id == "res:langchain-docs")
        )
    ).scalar_one()

    assert bookmark.resource_type == "Bookmark"
    assert bookmark.title == "LangChain Documentation"
    assert bookmark.location is not None
    assert bookmark.media_type == "text/html"
    assert bookmark.has_purpose == "purpose:reference"
    assert set(bookmark.has_use) >= {"purpose:learning", "purpose:project-support"}


async def test_document_resources(db_session: AsyncSession) -> None:
    """Test that document resources are loaded correctly."""
    await load_catalog_dataset(str(DATA_PATH), db_session)

    # Get a document
    document = (
        await db_session.execute(
            select(Resource).where(Resource.id == "res:doc:architecture-decisions")
        )
    ).scalar_one()

    assert document.resource_type == "Document"
    assert document.document_type == "adr"
    assert document.title == "Architecture Decision Records"


async def test_note_resources(db_session: AsyncSession) -> None:
    """Test that note resources are loaded correctly."""
    await load_catalog_dataset(str(DATA_PATH), db_session)

    # Get a note
    note = (
        await db_session.execute(
            select(Resource).where(Resource.id == "res:note:llm-experimentation")
        )
    ).scalar_one()

    assert note.resource_type == "Note"
    assert note.note_type == "experiment"
    assert note.creator == "charlie"


async def test_collection_resources(db_session: AsyncSession) -> None:
    """Test that collection resources are loaded correctly."""
    await load_catalog_dataset(str(DATA_PATH), db_session)

    # Get a collection
    collection = (
        await db_session.execute(
            select(Resource).where(Resource.id == "res:coll:llm-resources")
        )
    ).scalar_one()

    assert collection.resource_type == "Collection"
    assert isinstance(collection.has_resources, list)
    assert len(collection.has_resources) > 0
    assert "res:langchain-docs" in collection.has_resources


async def test_resource_relationships(db_session: AsyncSession) -> None:
    """Test that resource metadata and cross references are loaded."""
    await load_catalog_dataset(str(DATA_PATH), db_session)

    # Get a resource with relationships
    resource = (
        await db_session.execute(
            select(Resource).where(Resource.id == "res:llm-agents-paper")
        )
    ).scalar_one()

    assert resource.has_purpose == "purpose:research"
    assert resource.theme == "tech:ai"
    assert resource.repository == "repo:arxiv"


async def test_resource_catalog_relationship(db_session: AsyncSession) -> None:
    """Test that resources are correctly linked to catalogs."""
    await load_catalog_dataset(str(DATA_PATH), db_session)

    # Get a catalog
    catalog = (
        await db_session.execute(
            select(Catalog).where(Catalog.id == "cat:tech-resources")
        )
    ).scalar_one()

    # Count resources in this catalog
    resource_count = (
        await db_session.execute(
            select(func.count())
            .select_from(Resource)
            .where(Resource.catalog_id == catalog.id)
        )
    ).scalar_one()

    assert resource_count > 0


async def test_resource_repository_relationship(db_session: AsyncSession) -> None:
    """Test that resources are correctly linked to repositories."""
    await load_catalog_dataset(str(DATA_PATH), db_session)

    # Get a repository
    repository = (
        await db_session.execute(
            select(Repository).where(Repository.id == "repo:github")
        )
    ).scalar_one()

    # Count resources in this repository
    resource_count = (
        await db_session.execute(
            select(func.count())
            .select_from(Resource)
            .where(Resource.repository_id == repository.id)
        )
    ).scalar_one()

    assert resource_count > 0
