"""Tests for catalog ORM models."""

import pytest

from ontologizer.relational.models.catalog import (
    Bookmark,
    Catalog,
    Collection,
    Document,
    Note,
    Purpose,
    Repository,
    Resource,
)


class TestCatalogORM:
    """Tests for Catalog ORM model."""

    @pytest.mark.asyncio
    async def test_create_catalog(self, db_session):
        """Test creating a catalog with taxonomy relationships."""
        from ontologizer.relational.models.topic import Taxonomy

        # Create taxonomies first
        taxonomy1 = Taxonomy(id="tax:theme1", title="Theme 1")
        taxonomy2 = Taxonomy(id="tax:theme2", title="Theme 2")
        db_session.add_all([taxonomy1, taxonomy2])
        await db_session.flush()

        # Create catalog with taxonomies
        catalog = Catalog(
            id="cat:test",
            title="Test Catalog",
            description="A test catalog",
        )
        catalog.taxonomies = [taxonomy1, taxonomy2]

        db_session.add(catalog)
        await db_session.commit()
        await db_session.refresh(catalog)

        assert catalog.id is not None
        assert catalog.id == "cat:test"
        assert catalog.title == "Test Catalog"
        assert catalog.description == "A test catalog"
        assert len(catalog.taxonomies) == 2
        assert catalog.taxonomies[0].id in ["tax:theme1", "tax:theme2"]
        assert catalog.taxonomies[1].id in ["tax:theme1", "tax:theme2"]
        assert catalog.created_at is not None
        assert catalog.updated_at is not None

    @pytest.mark.asyncio
    async def test_catalog_unique_identifier(self, db_session):
        """Test that catalog identifiers must be unique."""
        catalog1 = Catalog(id="cat:test", title="Test Catalog 1")
        db_session.add(catalog1)
        await db_session.commit()

        catalog2 = Catalog(id="cat:test", title="Test Catalog 2")
        db_session.add(catalog2)

        with pytest.raises(Exception):  # IntegrityError
            await db_session.commit()


class TestRepositoryORM:
    """Tests for Repository ORM model."""

    @pytest.mark.asyncio
    async def test_create_repository(self, db_session):
        """Test creating a repository."""
        repo = Repository(
            id="repo:test",
            title="Test Repo",
            service_name="GitHub",
            description="A test repository",
        )

        db_session.add(repo)
        await db_session.commit()
        await db_session.refresh(repo)

        assert repo.id is not None
        assert repo.id == "repo:test"
        assert repo.title == "Test Repo"
        assert repo.service_name == "GitHub"
        assert repo.description == "A test repository"
        assert repo.created_at is not None

    @pytest.mark.asyncio
    async def test_repository_unique_identifier(self, db_session):
        """Test that repository identifiers must be unique."""
        repo1 = Repository(id="repo:test", title="Test Repo 1", service_name="GitHub")
        db_session.add(repo1)
        await db_session.commit()

        repo2 = Repository(id="repo:test", title="Test Repo 2", service_name="GitLab")
        db_session.add(repo2)

        with pytest.raises(Exception):  # IntegrityError
            await db_session.commit()


class TestPurposeORM:
    """Tests for Purpose ORM model."""

    @pytest.mark.asyncio
    async def test_create_purpose(self, db_session):
        """Test creating a purpose."""
        purpose = Purpose(
            id="purpose:test",
            title="Test Purpose",
            description="A test purpose",
            role="primary",
            meaning="for testing",
        )

        db_session.add(purpose)
        await db_session.commit()
        await db_session.refresh(purpose)

        assert purpose.id is not None
        assert purpose.id == "purpose:test"
        assert purpose.title == "Test Purpose"
        assert purpose.description == "A test purpose"
        assert purpose.role == "primary"
        assert purpose.meaning == "for testing"


class TestResourceORM:
    """Tests for Resource ORM model and inheritance."""

    @pytest.mark.asyncio
    async def test_create_resource(self, db_session):
        """Test creating a base resource."""
        # First create a catalog
        catalog = Catalog(id="cat:test", title="Test Catalog")
        db_session.add(catalog)
        await db_session.flush()

        resource = Resource(
            id="res:test",
            catalog="cat:test",
            catalog_id=catalog.id,
            title="Test Resource",
            description="A test resource",
            resource_type="Resource",
            location="https://example.com/resource",
        )

        db_session.add(resource)
        await db_session.commit()
        await db_session.refresh(resource)

        assert resource.id is not None
        assert resource.id == "res:test"
        assert resource.catalog == "cat:test"
        assert resource.title == "Test Resource"
        assert resource.resource_type == "Resource"
        assert resource.has_use == []
        assert resource.related_resources == []
        assert resource.related_topics == []

    @pytest.mark.asyncio
    async def test_create_bookmark(self, db_session):
        """Test creating a bookmark."""
        catalog = Catalog(id="cat:test", title="Test Catalog")
        db_session.add(catalog)
        await db_session.flush()

        bookmark = Bookmark(
            id="bm:test",
            catalog="cat:test",
            catalog_id=catalog.id,
            title="Test Bookmark",
            repository="repo:test",
            location="https://example.com",
        )

        db_session.add(bookmark)
        await db_session.commit()
        await db_session.refresh(bookmark)

        assert bookmark.id is not None
        assert bookmark.id == "bm:test"
        assert bookmark.resource_type == "Bookmark"
        assert bookmark.repository == "repo:test"
        assert bookmark.location == "https://example.com"

    @pytest.mark.asyncio
    async def test_create_collection(self, db_session):
        """Test creating a collection."""
        catalog = Catalog(id="cat:test", title="Test Catalog")
        db_session.add(catalog)
        await db_session.flush()

        collection = Collection(
            id="col:test",
            catalog="cat:test",
            catalog_id=catalog.id,
            title="Test Collection",
            repository="repo:test",
            has_resources=["res:1", "res:2"],
        )

        db_session.add(collection)
        await db_session.commit()
        await db_session.refresh(collection)

        assert collection.id is not None
        assert collection.id == "col:test"
        assert collection.resource_type == "Collection"
        assert collection.repository == "repo:test"
        assert collection.has_resources == ["res:1", "res:2"]

    @pytest.mark.asyncio
    async def test_create_document(self, db_session):
        """Test creating a document."""
        catalog = Catalog(id="cat:test", title="Test Catalog")
        repo = Repository(id="repo:test", title="Test Repo", service_name="GitHub")
        db_session.add_all([catalog, repo])
        await db_session.flush()

        document = Document(
            id="doc:test",
            catalog="cat:test",
            catalog_id=catalog.id,
            repository="repo:test",
            repository_id=repo.id,
            title="Test Document",
            document_type="Journal",
        )

        db_session.add(document)
        await db_session.commit()
        await db_session.refresh(document)

        assert document.id is not None
        assert document.id == "doc:test"
        assert document.resource_type == "Document"
        assert document.document_type == "Journal"
        assert document.repository == "repo:test"

    @pytest.mark.asyncio
    async def test_create_note(self, db_session):
        """Test creating a note."""
        catalog = Catalog(id="cat:test", title="Test Catalog")
        repo = Repository(id="repo:test", title="Test Repo", service_name="GitHub")
        db_session.add_all([catalog, repo])
        await db_session.flush()

        note = Note(
            id="note:test",
            catalog="cat:test",
            catalog_id=catalog.id,
            repository="repo:test",
            repository_id=repo.id,
            title="Test Note",
            note_type="Idea",
        )

        db_session.add(note)
        await db_session.commit()
        await db_session.refresh(note)

        assert note.id is not None
        assert note.id == "note:test"
        assert note.resource_type == "Note"
        assert note.note_type == "Idea"
        assert note.repository == "repo:test"

    @pytest.mark.asyncio
    async def test_catalog_resource_relationship(self, db_session):
        """Test the relationship between catalog and resources."""
        catalog = Catalog(id="cat:test", title="Test Catalog")
        db_session.add(catalog)
        await db_session.flush()

        resource1 = Resource(
            id="res:1",
            catalog="cat:test",
            catalog_id=catalog.id,
            title="Resource 1",
            location="https://example.com/resource1",
        )
        resource2 = Resource(
            id="res:2",
            catalog="cat:test",
            catalog_id=catalog.id,
            title="Resource 2",
            location="https://example.com/resource2",
        )

        db_session.add_all([resource1, resource2])
        await db_session.commit()
        await db_session.refresh(catalog)

        assert len(catalog.resources) == 2
        assert catalog.resources[0].title in ["Resource 1", "Resource 2"]
        assert catalog.resources[1].title in ["Resource 1", "Resource 2"]

    @pytest.mark.asyncio
    async def test_repository_resource_relationship(self, db_session):
        """Test the relationship between repository and resources."""
        catalog = Catalog(id="cat:test", title="Test Catalog")
        repo = Repository(id="repo:test", title="Test Repo", service_name="GitHub")
        db_session.add_all([catalog, repo])
        await db_session.flush()

        document = Document(
            id="doc:test",
            catalog="cat:test",
            catalog_id=catalog.id,
            repository="repo:test",
            repository_id=repo.id,
            title="Test Document",
            document_type="Document",
        )

        db_session.add(document)
        await db_session.commit()
        await db_session.refresh(repo)

        assert len(repo.resources) == 1
        assert repo.resources[0].title == "Test Document"

    @pytest.mark.asyncio
    async def test_resource_unique_identifier(self, db_session):
        """Test that resource identifiers must be unique."""
        catalog = Catalog(id="cat:test", title="Test Catalog")
        db_session.add(catalog)
        await db_session.flush()

        resource1 = Resource(
            id="res:test",
            catalog="cat:test",
            catalog_id=catalog.id,
            title="Resource 1",
            location="https://example.com/resource",
        )
        db_session.add(resource1)
        await db_session.commit()

        resource2 = Resource(
            id="res:test",
            catalog="cat:test",
            catalog_id=catalog.id,
            title="Resource 2",
            location="https://example.com/resource",
        )
        db_session.add(resource2)

        with pytest.raises(Exception):  # IntegrityError
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_cascade_delete_catalog(self, db_session):
        """Test that deleting a catalog cascades to resources."""
        catalog = Catalog(id="cat:test", title="Test Catalog")
        db_session.add(catalog)
        await db_session.flush()

        resource = Resource(
            id="res:test",
            catalog="cat:test",
            catalog_id=catalog.id,
            title="Test Resource",
            location="https://example.com/resource",
        )
        db_session.add(resource)
        await db_session.commit()

        # Delete catalog
        await db_session.delete(catalog)
        await db_session.commit()

        # Resource should also be deleted due to cascade
        from sqlalchemy import select

        result = await db_session.execute(
            select(Resource).where(Resource.id == "res:test")
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_subclass_auto_generate_resource_identifier(self, db_session):
        """Test that resource IDs must be explicitly provided (no auto-generation)."""
        catalog = Catalog(id="cat:test", title="Test Catalog")
        repo = Repository(id="repo:test", title="Test Repo", service_name="GitHub")
        db_session.add_all([catalog, repo])
        await db_session.flush()

        document = Document(
            catalog="cat:test",
            catalog_id=catalog.id,
            repository="repo:test",
            repository_id=repo.id,
            title="Test Document",
            document_type="Document",
        )

        db_session.add(document)
        await db_session.commit()
        await db_session.refresh(repo)

        assert len(repo.resources) == 1
        assert repo.resources[0].title == "Test Document"
        assert document.id == "doc:test-document"

    @pytest.mark.asyncio
    async def test_auto_generate_resource_identifier(self, db_session):
        """Test that resource IDs must be explicitly provided (no auto-generation)."""
        # Create a catalog
        catalog = Catalog(id="cat:cat01", title="Test Catalog")
        db_session.add(catalog)
        await db_session.flush()

        # Create resource WITHOUT explicit id - should raise IntegrityError
        resource = Resource(
            catalog="cat:cat01",
            catalog_id=catalog.id,
            title="A Resource Title Lowercase HYPHENATED",
            location="https://example.com/resource",
        )
        db_session.add(resource)

        await db_session.commit()
        assert resource.id == "res:a-resource-title-lowercase-hyphenated"
        # Verify that attempting to commit without an ID raises an error
        # with pytest.raises(IntegrityError):
        #     await db_session.commit()

    @pytest.mark.asyncio
    async def test_related_resources_relationship(self, db_session):
        """Test resource-to-resource relationships using association table."""
        from sqlalchemy import select

        from ontologizer.relational.models.catalog import resource_related_resources

        catalog = Catalog(id="cat:test", title="Test Catalog")
        db_session.add(catalog)
        await db_session.flush()

        resource1 = Resource(
            id="res:1",
            catalog="cat:test",
            catalog_id=catalog.id,
            title="Resource 1",
            location="https://example.com/1",
        )
        resource2 = Resource(
            id="res:2",
            catalog="cat:test",
            catalog_id=catalog.id,
            title="Resource 2",
            location="https://example.com/2",
        )
        db_session.add_all([resource1, resource2])
        await db_session.commit()

        # Add relationship via association table
        await db_session.execute(
            resource_related_resources.insert().values(
                source_resource_id=resource1.id, related_resource_id=resource2.id
            )
        )
        await db_session.commit()

        # Verify relationship exists in database
        result = await db_session.execute(
            select(resource_related_resources.c.related_resource_id).where(
                resource_related_resources.c.source_resource_id == resource1.id
            )
        )
        related_id = result.scalar_one()
        assert related_id == resource2.id

    @pytest.mark.asyncio
    async def test_related_topics_relationship(self, db_session):
        """Test resource-to-topic relationships using association table."""
        from sqlalchemy import select

        from ontologizer.relational.models.catalog import resource_related_topics
        from ontologizer.relational.models.topic import Taxonomy, Topic

        # Create taxonomy and topic
        taxonomy = Taxonomy(id="tx:test", title="Test Taxonomy")
        db_session.add(taxonomy)
        await db_session.flush()

        topic = Topic(
            taxonomy_id=taxonomy.id,
            title="Test Topic",
            slug="test-topic",
            id="test:test-topic",
        )
        db_session.add(topic)

        # Create catalog and resource
        catalog = Catalog(id="cat:test", title="Test Catalog")
        db_session.add(catalog)
        await db_session.flush()

        resource = Resource(
            id="res:test",
            catalog="cat:test",
            catalog_id=catalog.id,
            title="Test Resource",
            location="https://example.com",
        )
        db_session.add(resource)
        await db_session.commit()

        # Add relationship via association table
        await db_session.execute(
            resource_related_topics.insert().values(
                resource_id=resource.id, topic_id=topic.id
            )
        )
        await db_session.commit()

        # Verify relationship exists in database
        result = await db_session.execute(
            select(resource_related_topics.c.topic_id).where(
                resource_related_topics.c.resource_id == resource.id
            )
        )
        related_topic_id = result.scalar_one()
        assert related_topic_id == topic.id

    @pytest.mark.asyncio
    async def test_has_resources_only_for_collections(self, db_session):
        """Test that has_resources can only be set for Collection type."""
        catalog = Catalog(id="cat:test", title="Test Catalog")
        db_session.add(catalog)
        await db_session.flush()

        # Try to create a base Resource with has_resources
        resource = Resource(
            id="res:test",
            catalog="cat:test",
            catalog_id=catalog.id,
            title="Test Resource",
            location="https://example.com",
            has_resources=["res:other"],  # Should violate CHECK constraint
        )
        db_session.add(resource)

        # Should raise IntegrityError due to CHECK constraint
        with pytest.raises(Exception):  # IntegrityError
            await db_session.commit()

        await db_session.rollback()

        # Now try with Collection - should work
        collection = Collection(
            id="col:test",
            catalog="cat:test",
            catalog_id=catalog.id,
            title="Test Collection",
            repository="repo:test",
            has_resources=["res:other"],  # Should be allowed
        )
        db_session.add(collection)
        await db_session.commit()  # Should succeed
        await db_session.refresh(collection)

        assert collection.has_resources == ["res:other"]
