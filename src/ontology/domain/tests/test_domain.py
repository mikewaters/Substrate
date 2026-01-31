# """Tests for catalog domain models."""

# import uuid
# from datetime import datetime

# import pytest

# from ontology.domain import (
#     Bookmark,
#     Catalog,
#     Collection,
#     Document,
#     Note,
#     Purpose,
#     Repository,
#     Resource,
# )


# class TestCatalog:
#     """Tests for Catalog domain model."""

#     def test_create_catalog_minimal(self):
#         """Test creating a catalog with minimal required fields."""
#         catalog = Catalog(identifier="cat:test", title="Test Catalog")

#         assert catalog.identifier == "cat:test"
#         assert catalog.title == "Test Catalog"
#         assert isinstance(catalog.id, uuid.UUID)
#         assert catalog.description is None
#         assert catalog.taxonomies == []

#     def test_create_catalog_full(self):
#         """Test creating a catalog with all fields."""
#         taxonomies = ["tax:theme1", "tax:theme2"]
#         created_on = datetime.now()

#         catalog = Catalog(
#             identifier="cat:test",
#             title="Test Catalog",
#             description="A test catalog",
#             taxonomies=taxonomies,
#             created_by="user1",
#             created_on=created_on,
#         )

#         assert catalog.identifier == "cat:test"
#         assert catalog.title == "Test Catalog"
#         assert catalog.description == "A test catalog"
#         assert catalog.taxonomies == taxonomies
#         assert catalog.created_by == "user1"
#         assert catalog.created_on == created_on

#     def test_catalog_str(self):
#         """Test string representation."""
#         catalog = Catalog(identifier="cat:test", title="Test Catalog")
#         assert str(catalog) == "Catalog(Test Catalog)"


# class TestRepository:
#     """Tests for Repository domain model."""

#     def test_create_repository_minimal(self):
#         """Test creating a repository with minimal required fields."""
#         repo = Repository(
#             identifier="repo:test", title="Test Repo", service_name="GitHub"
#         )

#         assert repo.identifier == "repo:test"
#         assert repo.title == "Test Repo"
#         assert repo.service_name == "GitHub"
#         assert isinstance(repo.id, uuid.UUID)
#         assert repo.description is None

#     def test_create_repository_full(self):
#         """Test creating a repository with all fields."""
#         created_on = datetime.now()

#         repo = Repository(
#             identifier="repo:test",
#             title="Test Repo",
#             service_name="GitHub",
#             description="A test repository",
#             created_by="user1",
#             created_on=created_on,
#         )

#         assert repo.identifier == "repo:test"
#         assert repo.title == "Test Repo"
#         assert repo.service_name == "GitHub"
#         assert repo.description == "A test repository"
#         assert repo.created_by == "user1"

#     def test_repository_str(self):
#         """Test string representation."""
#         repo = Repository(
#             identifier="repo:test", title="Test Repo", service_name="GitHub"
#         )
#         assert str(repo) == "Repository(Test Repo, service=GitHub)"


# class TestPurpose:
#     """Tests for Purpose domain model."""

#     def test_create_purpose_minimal(self):
#         """Test creating a purpose with minimal required fields."""
#         purpose = Purpose(identifier="purpose:test", title="Test Purpose")

#         assert purpose.identifier == "purpose:test"
#         assert purpose.title == "Test Purpose"
#         assert isinstance(purpose.id, uuid.UUID)
#         assert purpose.description is None
#         assert purpose.role is None
#         assert purpose.meaning is None

#     def test_create_purpose_full(self):
#         """Test creating a purpose with all fields."""
#         purpose = Purpose(
#             identifier="purpose:test",
#             title="Test Purpose",
#             description="A test purpose",
#             role="primary",
#             meaning="for testing",
#         )

#         assert purpose.identifier == "purpose:test"
#         assert purpose.title == "Test Purpose"
#         assert purpose.description == "A test purpose"
#         assert purpose.role == "primary"
#         assert purpose.meaning == "for testing"

#     def test_purpose_str(self):
#         """Test string representation."""
#         purpose = Purpose(identifier="purpose:test", title="Test Purpose")
#         assert str(purpose) == "Purpose(Test Purpose)"


# class TestResource:
#     """Tests for Resource domain model."""

#     def test_create_resource_minimal(self):
#         """Test creating a resource with minimal required fields."""
#         resource = Resource(
#             identifier="res:test",
#             catalog="cat:test",
#             title="Test Resource",
#             location="https://example.com/resource",
#         )

#         assert resource.identifier == "res:test"
#         assert resource.catalog == "cat:test"
#         assert resource.title == "Test Resource"
#         assert resource.location == "https://example.com/resource"
#         assert isinstance(resource.id, uuid.UUID)
#         assert resource.resource_type == "Resource"
#         assert resource.related_resources == []
#         assert resource.related_topics == []
#         assert resource.has_use == []

#     def test_create_resource_full(self):
#         """Test creating a resource with all fields."""
#         created = datetime.now()
#         modified = datetime.now()

#         resource = Resource(
#             identifier="res:test",
#             catalog="cat:test",
#             title="Test Resource",
#             description="A test resource",
#             location="https://example.com/resource",
#             repository="repo:test",
#             content_location="https://storage.example.com/content",
#             format="markdown",
#             media_type="text/markdown",
#             theme="theme:test",
#             subject="Testing",
#             creator="user1",
#             has_purpose="purpose:test",
#             has_use=["use1", "use2"],
#             related_resources=["res:other"],
#             related_topics=["topic:test"],
#             created=created,
#             modified=modified,
#         )

#         assert resource.identifier == "res:test"
#         assert resource.catalog == "cat:test"
#         assert resource.title == "Test Resource"
#         assert resource.description == "A test resource"
#         assert resource.location == "https://example.com/resource"
#         assert resource.repository == "repo:test"
#         assert resource.content_location == "https://storage.example.com/content"
#         assert resource.format == "markdown"
#         assert resource.media_type == "text/markdown"
#         assert resource.theme == "theme:test"
#         assert resource.subject == "Testing"
#         assert resource.creator == "user1"
#         assert resource.has_purpose == "purpose:test"
#         assert resource.has_use == ["use1", "use2"]
#         assert resource.related_resources == ["res:other"]
#         assert resource.related_topics == ["topic:test"]
#         assert resource.created == created
#         assert resource.modified == modified

#     def test_resource_str(self):
#         """Test string representation."""
#         resource = Resource(
#             identifier="res:test",
#             catalog="cat:test",
#             title="Test Resource",
#             location="https://example.com/resource",
#         )
#         assert str(resource) == "Resource(Test Resource, type=Resource)"


# class TestBookmark:
#     """Tests for Bookmark domain model."""

#     def test_create_bookmark(self):
#         """Test creating a bookmark."""
#         bookmark = Bookmark(
#             identifier="bm:test",
#             catalog="cat:test",
#             title="Test Bookmark",
#             repository="repo:test",
#             location="https://example.com",
#         )

#         assert bookmark.identifier == "bm:test"
#         assert bookmark.catalog == "cat:test"
#         assert bookmark.title == "Test Bookmark"
#         assert bookmark.repository == "repo:test"
#         assert bookmark.location == "https://example.com"
#         assert bookmark.resource_type == "Bookmark"

#     def test_bookmark_str(self):
#         """Test string representation."""
#         bookmark = Bookmark(
#             identifier="bm:test",
#             catalog="cat:test",
#             title="Test Bookmark",
#             repository="repo:test",
#         )
#         assert str(bookmark) == "Bookmark(Test Bookmark)"


# class TestCollection:
#     """Tests for Collection domain model."""

#     def test_create_collection(self):
#         """Test creating a collection."""
#         resources = ["res:1", "res:2", "res:3"]
#         collection = Collection(
#             identifier="col:test",
#             catalog="cat:test",
#             title="Test Collection",
#             repository="repo:test",
#             has_resources=resources,
#         )

#         assert collection.identifier == "col:test"
#         assert collection.catalog == "cat:test"
#         assert collection.title == "Test Collection"
#         assert collection.repository == "repo:test"
#         assert collection.has_resources == resources
#         assert collection.resource_type == "Collection"

#     def test_collection_str(self):
#         """Test string representation."""
#         resources = ["res:1", "res:2", "res:3"]
#         collection = Collection(
#             identifier="col:test",
#             catalog="cat:test",
#             title="Test Collection",
#             repository="repo:test",
#             has_resources=resources,
#         )
#         assert str(collection) == "Collection(Test Collection, 3 resources)"


# class TestDocument:
#     """Tests for Document domain model."""

#     def test_create_document(self):
#         """Test creating a document."""
#         document = Document(
#             identifier="doc:test",
#             catalog="cat:test",
#             title="Test Document",
#             repository="repo:test",
#             document_type="Journal",
#         )

#         assert document.identifier == "doc:test"
#         assert document.catalog == "cat:test"
#         assert document.title == "Test Document"
#         assert document.repository == "repo:test"
#         assert document.document_type == "Journal"
#         assert document.resource_type == "Document"

#     def test_document_str(self):
#         """Test string representation."""
#         document = Document(
#             identifier="doc:test",
#             catalog="cat:test",
#             title="Test Document",
#             repository="repo:test",
#             document_type="Journal",
#         )
#         assert str(document) == "Document(Test Document, type=Journal)"


# class TestNote:
#     """Tests for Note domain model."""

#     def test_create_note(self):
#         """Test creating a note."""
#         note = Note(
#             identifier="note:test",
#             catalog="cat:test",
#             title="Test Note",
#             repository="repo:test",
#             note_type="Idea",
#         )

#         assert note.identifier == "note:test"
#         assert note.catalog == "cat:test"
#         assert note.title == "Test Note"
#         assert note.repository == "repo:test"
#         assert note.note_type == "Idea"
#         assert note.resource_type == "Note"

#     def test_note_str(self):
#         """Test string representation."""
#         note = Note(
#             identifier="note:test",
#             catalog="cat:test",
#             title="Test Note",
#             repository="repo:test",
#             note_type="Idea",
#         )
#         assert str(note) == "Note(Test Note, type=Idea)"
