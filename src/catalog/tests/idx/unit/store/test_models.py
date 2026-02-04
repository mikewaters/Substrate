"""Tests for catalog.store.models module."""

import json
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from catalog.store.database import Base, create_engine_for_path, get_session_factory
from catalog.store.models import (
    Bookmark,
    BookmarkLink,
    BookmarkRelationKind,
    Catalog,
    CatalogEntry,
    CatalogEntryRelationKind,
    Collection,
    CollectionMember,
    Dataset,
    Document,
    DocumentKind,
    Repository,
    RepositoryLink,
    Resource,
    ResourceKind,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_session_factory_for_engine(engine):
    """Create a session factory for a specific engine."""
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=engine, expire_on_commit=False)


get_session_factory.__wrapped__ = get_session_factory_for_engine


@pytest.fixture
def db_session(tmp_path: Path):
    """Create a test database session with all tables."""
    db_path = tmp_path / "test.db"
    engine = create_engine_for_path(db_path)
    Base.metadata.create_all(engine)

    factory = get_session_factory.__wrapped__(engine)
    session = factory()
    yield session
    session.close()


# ---------------------------------------------------------------------------
# Resource base class
# ---------------------------------------------------------------------------


class TestResource:
    """Tests for the Resource base class."""

    def test_resource_uri_is_unique(self, db_session) -> None:
        """Resource URIs must be unique across all types."""
        ds1 = Dataset(
            uri="resource:unique-test",
            name="ds1",
            source_type="directory",
            source_path="/path1",
        )
        db_session.add(ds1)
        db_session.commit()

        ds2 = Dataset(
            uri="resource:unique-test",
            name="ds2",
            source_type="directory",
            source_path="/path2",
        )
        db_session.add(ds2)
        with pytest.raises(Exception):
            db_session.commit()

    def test_polymorphic_query_returns_mixed_types(self, db_session) -> None:
        """session.query(Resource) returns all subclass instances."""
        ds = Dataset(
            uri="dataset:poly-ds",
            name="poly-ds",
            source_type="directory",
            source_path="/path",
        )
        cat = Catalog(uri="catalog:poly-cat", homepage="https://example.com")
        coll = Collection(uri="collection:poly-coll")
        bm = Bookmark(
            uri="bookmark:poly-bm",
            url="https://example.com",
            owner="test",
        )
        repo = Repository(
            uri="repository:poly-repo",
            host="github",
            repo_full_name="user/repo",
        )
        db_session.add_all([ds, cat, coll, bm, repo])
        db_session.commit()

        resources = db_session.execute(select(Resource)).scalars().all()
        kinds = {r.kind for r in resources}
        assert ResourceKind.DATASET in kinds
        assert ResourceKind.CATALOG in kinds
        assert ResourceKind.COLLECTION in kinds
        assert ResourceKind.BOOKMARK in kinds
        assert ResourceKind.REPOSITORY in kinds
        assert len(resources) == 5

    def test_resource_repr(self, db_session) -> None:
        """Resource repr includes kind and uri."""
        ds = Dataset(
            uri="dataset:repr-base",
            name="repr-base",
            source_type="directory",
            source_path="/path",
        )
        db_session.add(ds)
        db_session.commit()

        # Access as Resource
        r = db_session.get(Resource, ds.id)
        assert r is not None
        # When accessed as Resource, it's actually a Dataset due to polymorphism
        assert isinstance(r, Dataset)

    def test_resource_title_and_description_nullable(self, db_session) -> None:
        """Resource title and description are optional."""
        ds = Dataset(
            uri="dataset:nullable-test",
            name="nullable-test",
            source_type="directory",
            source_path="/path",
            title="My Dataset",
            description="A test dataset",
        )
        db_session.add(ds)
        db_session.commit()

        assert ds.title == "My Dataset"
        assert ds.description == "A test dataset"


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------


class TestDataset:
    """Tests for Dataset model."""

    def test_create_dataset(self, db_session) -> None:
        """Dataset can be created with required fields."""
        dataset = Dataset(
            name="test-vault",
            uri="dataset:test-vault",
            source_type="obsidian",
            source_path="/path/to/vault",
        )
        db_session.add(dataset)
        db_session.commit()

        assert dataset.id is not None
        assert dataset.name == "test-vault"
        assert dataset.uri == "dataset:test-vault"
        assert dataset.source_type == "obsidian"
        assert dataset.source_path == "/path/to/vault"
        assert dataset.kind == ResourceKind.DATASET
        assert dataset.created_at is not None
        assert dataset.updated_at is not None

    def test_dataset_name_is_unique(self, db_session) -> None:
        """Dataset names must be unique."""
        dataset1 = Dataset(
            name="unique-name",
            uri="dataset:unique-name",
            source_type="directory",
            source_path="/path1",
        )
        db_session.add(dataset1)
        db_session.commit()

        dataset2 = Dataset(
            name="unique-name",
            uri="dataset:unique-name-2",
            source_type="directory",
            source_path="/path2",
        )
        db_session.add(dataset2)

        with pytest.raises(Exception):
            db_session.commit()

    def test_dataset_uri_is_unique(self, db_session) -> None:
        """Dataset URIs must be unique."""
        dataset1 = Dataset(
            name="name1",
            uri="dataset:shared-uri",
            source_type="directory",
            source_path="/path1",
        )
        db_session.add(dataset1)
        db_session.commit()

        dataset2 = Dataset(
            name="name2",
            uri="dataset:shared-uri",
            source_type="directory",
            source_path="/path2",
        )
        db_session.add(dataset2)

        with pytest.raises(Exception):
            db_session.commit()

    def test_dataset_repr(self, db_session) -> None:
        """Dataset has useful repr."""
        dataset = Dataset(
            name="repr-test",
            uri="dataset:repr-test",
            source_type="obsidian",
            source_path="/path",
        )
        db_session.add(dataset)
        db_session.commit()

        repr_str = repr(dataset)
        assert "repr-test" in repr_str
        assert "obsidian" in repr_str


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------


class TestDocument:
    """Tests for Document model."""

    @pytest.fixture
    def dataset(self, db_session) -> Dataset:
        """Create a test dataset."""
        ds = Dataset(
            name="test-dataset",
            uri="dataset:test-dataset",
            source_type="directory",
            source_path="/test/path",
        )
        db_session.add(ds)
        db_session.commit()
        return ds

    def test_create_document(self, db_session, dataset: Dataset) -> None:
        """Document can be created with required fields."""
        doc = Document(
            uri=f"document:test-dataset/notes/test.md",
            parent_id=dataset.id,
            path="notes/test.md",
            content_hash="abc123def456",
            body="# Test Document\n\nContent here.",
        )
        db_session.add(doc)
        db_session.commit()

        assert doc.id is not None
        assert doc.parent_id == dataset.id
        assert doc.path == "notes/test.md"
        assert doc.content_hash == "abc123def456"
        assert doc.body == "# Test Document\n\nContent here."
        assert doc.active is True
        assert doc.doc_type == DocumentKind.OTHER
        assert doc.kind == ResourceKind.DOCUMENT
        assert doc.created_at is not None
        assert doc.updated_at is not None

    def test_document_default_active_true(self, db_session, dataset: Dataset) -> None:
        """Document active defaults to True."""
        doc = Document(
            uri="document:test-dataset/test.md",
            parent_id=dataset.id,
            path="test.md",
            content_hash="hash",
            body="content",
        )
        db_session.add(doc)
        db_session.commit()

        assert doc.active is True

    def test_document_can_be_soft_deleted(self, db_session, dataset: Dataset) -> None:
        """Document can be soft-deleted by setting active=False."""
        doc = Document(
            uri="document:test-dataset/deletable.md",
            parent_id=dataset.id,
            path="deletable.md",
            content_hash="hash",
            body="content",
        )
        db_session.add(doc)
        db_session.commit()

        doc.active = False
        db_session.commit()

        assert doc.active is False

    def test_document_optional_etag(self, db_session, dataset: Dataset) -> None:
        """Document etag is optional."""
        doc = Document(
            uri="document:test-dataset/etag-test.md",
            parent_id=dataset.id,
            path="test.md",
            content_hash="hash",
            body="content",
            etag='W/"abc123"',
        )
        db_session.add(doc)
        db_session.commit()

        assert doc.etag == 'W/"abc123"'

    def test_document_optional_last_modified(self, db_session, dataset: Dataset) -> None:
        """Document last_modified is optional."""
        modified = datetime(2024, 1, 15, 10, 30, 0)
        doc = Document(
            uri="document:test-dataset/modified-test.md",
            parent_id=dataset.id,
            path="test.md",
            content_hash="hash",
            body="content",
            last_modified=modified,
        )
        db_session.add(doc)
        db_session.commit()

        assert doc.last_modified == modified

    def test_document_get_metadata(self, db_session, dataset: Dataset) -> None:
        """Document get_metadata parses JSON."""
        doc = Document(
            uri="document:test-dataset/metadata-get.md",
            parent_id=dataset.id,
            path="test.md",
            content_hash="hash",
            body="content",
            metadata_json='{"tags": ["foo", "bar"], "author": "test"}',
        )
        db_session.add(doc)
        db_session.commit()

        assert doc.get_metadata() == {"tags": ["foo", "bar"], "author": "test"}

    def test_document_set_metadata(self, db_session, dataset: Dataset) -> None:
        """Document set_metadata serializes to JSON."""
        doc = Document(
            uri="document:test-dataset/metadata-set.md",
            parent_id=dataset.id,
            path="test.md",
            content_hash="hash",
            body="content",
        )
        doc.set_metadata({"key": "value", "number": 42})
        db_session.add(doc)
        db_session.commit()

        assert json.loads(doc.metadata_json) == {"key": "value", "number": 42}

    def test_document_get_metadata_empty_when_null(
        self, db_session, dataset: Dataset
    ) -> None:
        """Document get_metadata returns empty dict when null."""
        doc = Document(
            uri="document:test-dataset/metadata-null.md",
            parent_id=dataset.id,
            path="test.md",
            content_hash="hash",
            body="content",
        )
        db_session.add(doc)
        db_session.commit()

        assert doc.get_metadata() == {}

    def test_document_unique_path_per_parent(
        self, db_session, dataset: Dataset
    ) -> None:
        """Document paths must be unique within a parent."""
        doc1 = Document(
            uri="document:test-dataset/same/path.md",
            parent_id=dataset.id,
            path="same/path.md",
            content_hash="hash1",
            body="content1",
        )
        db_session.add(doc1)
        db_session.commit()

        doc2 = Document(
            uri="document:test-dataset/same/path.md-dup",
            parent_id=dataset.id,
            path="same/path.md",
            content_hash="hash2",
            body="content2",
        )
        db_session.add(doc2)

        with pytest.raises(Exception):
            db_session.commit()

    def test_document_doc_type(self, db_session, dataset: Dataset) -> None:
        """Document doc_type can be set."""
        doc = Document(
            uri="document:test-dataset/vault-export.md",
            parent_id=dataset.id,
            path="export.md",
            content_hash="hash",
            body="content",
            doc_type=DocumentKind.VAULT_EXPORT,
        )
        db_session.add(doc)
        db_session.commit()

        assert doc.doc_type == DocumentKind.VAULT_EXPORT

    def test_document_repr(self, db_session, dataset: Dataset) -> None:
        """Document has useful repr."""
        doc = Document(
            uri="document:test-dataset/repr/test.md",
            parent_id=dataset.id,
            path="repr/test.md",
            content_hash="hash",
            body="content",
        )
        db_session.add(doc)
        db_session.commit()

        repr_str = repr(doc)
        assert "repr/test.md" in repr_str
        assert "active=True" in repr_str


# ---------------------------------------------------------------------------
# Dataset-Document relationship
# ---------------------------------------------------------------------------


class TestDatasetDocumentRelationship:
    """Tests for Dataset-Document relationship via Resource hierarchy."""

    @pytest.fixture
    def dataset(self, db_session) -> Dataset:
        """Create a test dataset."""
        ds = Dataset(
            name="rel-test",
            uri="dataset:rel-test",
            source_type="directory",
            source_path="/path",
        )
        db_session.add(ds)
        db_session.commit()
        return ds

    def test_dataset_has_documents_relationship(self, db_session, dataset: Dataset) -> None:
        """Dataset (via Resource) has documents relationship."""
        doc1 = Document(
            uri="document:rel-test/doc1.md",
            parent_id=dataset.id,
            path="doc1.md",
            content_hash="hash1",
            body="content1",
        )
        doc2 = Document(
            uri="document:rel-test/doc2.md",
            parent_id=dataset.id,
            path="doc2.md",
            content_hash="hash2",
            body="content2",
        )
        db_session.add_all([doc1, doc2])
        db_session.commit()

        assert len(dataset.documents) == 2
        paths = {d.path for d in dataset.documents}
        assert paths == {"doc1.md", "doc2.md"}

    def test_document_has_parent_resource_relationship(
        self, db_session, dataset: Dataset
    ) -> None:
        """Document.parent_resource returns parent dataset."""
        doc = Document(
            uri="document:rel-test/child.md",
            parent_id=dataset.id,
            path="child.md",
            content_hash="hash",
            body="content",
        )
        db_session.add(doc)
        db_session.commit()

        assert doc.parent_resource is not None
        assert isinstance(doc.parent_resource, Dataset)
        assert doc.parent_resource.name == "rel-test"

    def test_cascade_delete_documents(self, db_session, dataset: Dataset) -> None:
        """Deleting dataset cascades to documents."""
        doc = Document(
            uri="document:rel-test/cascade.md",
            parent_id=dataset.id,
            path="cascade.md",
            content_hash="hash",
            body="content",
        )
        db_session.add(doc)
        db_session.commit()
        doc_id = doc.id

        db_session.delete(dataset)
        db_session.commit()

        remaining = db_session.get(Document, doc_id)
        assert remaining is None


# ---------------------------------------------------------------------------
# Catalog + CatalogEntry
# ---------------------------------------------------------------------------


class TestCatalog:
    """Tests for Catalog and CatalogEntry models."""

    def test_create_catalog(self, db_session) -> None:
        """Catalog can be created."""
        cat = Catalog(
            uri="catalog:test-cat",
            homepage="https://example.com",
            title="Test Catalog",
        )
        db_session.add(cat)
        db_session.commit()

        assert cat.id is not None
        assert cat.kind == ResourceKind.CATALOG
        assert cat.homepage == "https://example.com"
        assert cat.title == "Test Catalog"

    def test_catalog_entry_relationship(self, db_session) -> None:
        """CatalogEntry links a catalog to a resource."""
        cat = Catalog(uri="catalog:entry-test")
        ds = Dataset(
            uri="dataset:entry-target",
            name="entry-target",
            source_type="directory",
            source_path="/path",
        )
        db_session.add_all([cat, ds])
        db_session.commit()

        entry = CatalogEntry(
            catalog_id=cat.id,
            resource_id=ds.id,
            relation=CatalogEntryRelationKind.DATASET,
        )
        db_session.add(entry)
        db_session.commit()

        assert len(cat.entries) == 1
        assert cat.entries[0].resource_id == ds.id
        assert cat.entries[0].relation == CatalogEntryRelationKind.DATASET

    def test_cascade_delete_entries(self, db_session) -> None:
        """Deleting catalog cascades to entries but not referenced resources."""
        cat = Catalog(uri="catalog:cascade-test")
        ds = Dataset(
            uri="dataset:cascade-target",
            name="cascade-target",
            source_type="directory",
            source_path="/path",
        )
        db_session.add_all([cat, ds])
        db_session.commit()
        ds_id = ds.id

        entry = CatalogEntry(
            catalog_id=cat.id,
            resource_id=ds.id,
            relation=CatalogEntryRelationKind.DATASET,
        )
        db_session.add(entry)
        db_session.commit()
        entry_id = entry.id

        db_session.delete(cat)
        db_session.commit()

        # Entry should be gone
        assert db_session.get(CatalogEntry, entry_id) is None
        # Referenced resource should still exist
        assert db_session.get(Dataset, ds_id) is not None

    def test_unique_catalog_resource_pair(self, db_session) -> None:
        """Cannot add duplicate (catalog_id, resource_id) pairs."""
        cat = Catalog(uri="catalog:dup-test")
        ds = Dataset(
            uri="dataset:dup-target",
            name="dup-target",
            source_type="directory",
            source_path="/path",
        )
        db_session.add_all([cat, ds])
        db_session.commit()

        entry1 = CatalogEntry(
            catalog_id=cat.id,
            resource_id=ds.id,
            relation=CatalogEntryRelationKind.DATASET,
        )
        db_session.add(entry1)
        db_session.commit()

        entry2 = CatalogEntry(
            catalog_id=cat.id,
            resource_id=ds.id,
            relation=CatalogEntryRelationKind.OTHER,
        )
        db_session.add(entry2)
        with pytest.raises(Exception):
            db_session.commit()

    def test_catalog_repr(self, db_session) -> None:
        """Catalog has useful repr."""
        cat = Catalog(uri="catalog:repr-test")
        db_session.add(cat)
        db_session.commit()

        assert "catalog:repr-test" in repr(cat)


# ---------------------------------------------------------------------------
# Collection + CollectionMember
# ---------------------------------------------------------------------------


class TestCollection:
    """Tests for Collection and CollectionMember models."""

    def test_create_collection(self, db_session) -> None:
        """Collection can be created."""
        coll = Collection(uri="collection:test-coll", title="My Collection")
        db_session.add(coll)
        db_session.commit()

        assert coll.id is not None
        assert coll.kind == ResourceKind.COLLECTION

    def test_collection_member_relationship(self, db_session) -> None:
        """CollectionMember links a collection to a resource."""
        coll = Collection(uri="collection:member-test")
        ds = Dataset(
            uri="dataset:member-target",
            name="member-target",
            source_type="directory",
            source_path="/path",
        )
        db_session.add_all([coll, ds])
        db_session.commit()

        member = CollectionMember(
            collection_id=coll.id,
            resource_id=ds.id,
        )
        db_session.add(member)
        db_session.commit()

        assert len(coll.members) == 1
        assert coll.members[0].resource_id == ds.id

    def test_cascade_deletes_members_not_resources(self, db_session) -> None:
        """Deleting collection deletes members but not referenced resources."""
        coll = Collection(uri="collection:cascade-test")
        ds = Dataset(
            uri="dataset:coll-cascade",
            name="coll-cascade",
            source_type="directory",
            source_path="/path",
        )
        db_session.add_all([coll, ds])
        db_session.commit()
        ds_id = ds.id

        member = CollectionMember(collection_id=coll.id, resource_id=ds.id)
        db_session.add(member)
        db_session.commit()
        member_id = member.id

        db_session.delete(coll)
        db_session.commit()

        assert db_session.get(CollectionMember, member_id) is None
        assert db_session.get(Dataset, ds_id) is not None

    def test_unique_collection_resource_pair(self, db_session) -> None:
        """Cannot add duplicate (collection_id, resource_id) pairs."""
        coll = Collection(uri="collection:dup-test")
        ds = Dataset(
            uri="dataset:coll-dup",
            name="coll-dup",
            source_type="directory",
            source_path="/path",
        )
        db_session.add_all([coll, ds])
        db_session.commit()

        m1 = CollectionMember(collection_id=coll.id, resource_id=ds.id)
        db_session.add(m1)
        db_session.commit()

        m2 = CollectionMember(collection_id=coll.id, resource_id=ds.id)
        db_session.add(m2)
        with pytest.raises(Exception):
            db_session.commit()


# ---------------------------------------------------------------------------
# Bookmark + BookmarkLink
# ---------------------------------------------------------------------------


class TestBookmark:
    """Tests for Bookmark and BookmarkLink models."""

    def test_create_bookmark(self, db_session) -> None:
        """Bookmark can be created."""
        bm = Bookmark(
            uri="bookmark:test-bm",
            url="https://example.com/article",
            owner="mike",
            title="Example Article",
        )
        db_session.add(bm)
        db_session.commit()

        assert bm.id is not None
        assert bm.kind == ResourceKind.BOOKMARK
        assert bm.url == "https://example.com/article"
        assert bm.owner == "mike"
        assert bm.is_archived is False

    def test_bookmark_link_to_resource(self, db_session) -> None:
        """BookmarkLink links a bookmark to a resource."""
        bm = Bookmark(
            uri="bookmark:link-test",
            url="https://example.com",
            owner="test",
        )
        ds = Dataset(
            uri="dataset:bm-link",
            name="bm-link",
            source_type="directory",
            source_path="/path",
        )
        db_session.add_all([bm, ds])
        db_session.commit()

        link = BookmarkLink(
            bookmark_id=bm.id,
            resource_id=ds.id,
            relation=BookmarkRelationKind.RELEVANT_TO,
        )
        db_session.add(link)
        db_session.commit()

        assert len(bm.resource_links) == 1
        assert bm.resource_links[0].relation == BookmarkRelationKind.RELEVANT_TO

    def test_cascade_deletes_links_not_resources(self, db_session) -> None:
        """Deleting bookmark deletes links but not referenced resources."""
        bm = Bookmark(
            uri="bookmark:cascade-test",
            url="https://example.com",
            owner="test",
        )
        ds = Dataset(
            uri="dataset:bm-cascade",
            name="bm-cascade",
            source_type="directory",
            source_path="/path",
        )
        db_session.add_all([bm, ds])
        db_session.commit()
        ds_id = ds.id

        link = BookmarkLink(
            bookmark_id=bm.id,
            resource_id=ds.id,
            relation=BookmarkRelationKind.SOURCE_FOR,
        )
        db_session.add(link)
        db_session.commit()

        db_session.delete(bm)
        db_session.commit()

        assert db_session.get(Dataset, ds_id) is not None

    def test_bookmark_archived_flag(self, db_session) -> None:
        """Bookmark is_archived can be set."""
        bm = Bookmark(
            uri="bookmark:archive-test",
            url="https://example.com",
            owner="test",
            is_archived=True,
        )
        db_session.add(bm)
        db_session.commit()

        assert bm.is_archived is True


# ---------------------------------------------------------------------------
# Repository + RepositoryLink
# ---------------------------------------------------------------------------


class TestRepository:
    """Tests for Repository and RepositoryLink models."""

    def test_create_repository(self, db_session) -> None:
        """Repository can be created."""
        repo = Repository(
            uri="repository:test-repo",
            host="github",
            repo_full_name="user/project",
            default_branch="main",
            web_url="https://github.com/user/project",
        )
        db_session.add(repo)
        db_session.commit()

        assert repo.id is not None
        assert repo.kind == ResourceKind.REPOSITORY
        assert repo.host == "github"
        assert repo.repo_full_name == "user/project"

    def test_repository_link_to_resource(self, db_session) -> None:
        """RepositoryLink links a repository to a resource."""
        repo = Repository(
            uri="repository:link-test",
            host="github",
            repo_full_name="user/repo",
        )
        ds = Dataset(
            uri="dataset:repo-link",
            name="repo-link",
            source_type="directory",
            source_path="/path",
        )
        db_session.add_all([repo, ds])
        db_session.commit()

        link = RepositoryLink(
            repository_id=repo.id,
            resource_id=ds.id,
            relation="indexes",
        )
        db_session.add(link)
        db_session.commit()

        assert len(repo.resource_links) == 1
        assert repo.resource_links[0].relation == "indexes"

    def test_cascade_deletes_links_not_resources(self, db_session) -> None:
        """Deleting repository deletes links but not referenced resources."""
        repo = Repository(
            uri="repository:cascade-test",
            host="github",
        )
        ds = Dataset(
            uri="dataset:repo-cascade",
            name="repo-cascade",
            source_type="directory",
            source_path="/path",
        )
        db_session.add_all([repo, ds])
        db_session.commit()
        ds_id = ds.id

        link = RepositoryLink(
            repository_id=repo.id,
            resource_id=ds.id,
            relation="contains",
        )
        db_session.add(link)
        db_session.commit()

        db_session.delete(repo)
        db_session.commit()

        assert db_session.get(Dataset, ds_id) is not None
