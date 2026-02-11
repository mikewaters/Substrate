"""Tests for PersistenceTransform create/update behavior.

Change detection is handled upstream by LlamaIndex's docstore; the
PersistenceTransform always creates or updates every node it receives.
"""

from pathlib import Path

import pytest
from llama_index.core.schema import Document as LlamaDocument
from sqlalchemy.orm import sessionmaker

from catalog.store.database import Base, create_engine_for_path
from catalog.store.fts import create_fts_table
from catalog.store.fts_chunk import create_chunks_fts_table
from catalog.store.models import Dataset
from catalog.store.repositories import DocumentRepository
from catalog.store.session_context import use_session
from catalog.transform.llama import PersistenceTransform, _compute_content_hash


@pytest.fixture
def db_session(tmp_path: Path):
    """Create a test database session with FTS tables."""
    db_path = tmp_path / "test.db"
    engine = create_engine_for_path(db_path)
    Base.metadata.create_all(engine)
    create_fts_table(engine)
    create_chunks_fts_table(engine)

    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    yield session
    session.close()


@pytest.fixture
def dataset(db_session) -> Dataset:
    """Create a sample dataset."""
    ds = Dataset(
        name="test-ds",
        uri="dataset:test-ds",
        source_type="directory",
        source_path="/test",
    )
    db_session.add(ds)
    db_session.flush()
    return ds


def _make_docs(
    contents: dict[str, str],
    metadata: dict[str, dict] | None = None,
) -> list[LlamaDocument]:
    """Build LlamaIndex documents from path->content mapping.

    Args:
        contents: Mapping of path -> body text.
        metadata: Optional mapping of path -> extra metadata dict.
    """
    docs = []
    for path, body in contents.items():
        doc = LlamaDocument(text=body, id_=path)
        doc.metadata = {"relative_path": path}
        if metadata and path in metadata:
            doc.metadata.update(metadata[path])
        docs.append(doc)
    return docs


class TestPersistenceTransform:
    """PersistenceTransform always creates or updates -- no skip logic."""

    def test_first_ingest_returns_all_nodes(self, db_session, dataset):
        """First ingestion returns all nodes (all created)."""
        transform = PersistenceTransform(dataset_id=dataset.id, dataset_name=dataset.name)
        docs = _make_docs({"a.md": "AAA", "b.md": "BBB", "c.md": "CCC"})

        with use_session(db_session):
            result = transform(docs)

        assert len(result) == 3
        assert transform.stats.created == 3

    def test_reingest_same_content_updates_all(self, db_session, dataset):
        """Re-ingestion of same docs updates all (no skip logic)."""
        transform = PersistenceTransform(dataset_id=dataset.id, dataset_name=dataset.name)
        docs = _make_docs({"a.md": "AAA", "b.md": "BBB", "c.md": "CCC"})

        with use_session(db_session):
            transform(docs)

        # Second pass with same content -- all should be updated
        transform2 = PersistenceTransform(dataset_id=dataset.id, dataset_name=dataset.name)
        docs2 = _make_docs({"a.md": "AAA", "b.md": "BBB", "c.md": "CCC"})

        with use_session(db_session):
            result2 = transform2(docs2)

        assert len(result2) == 3
        assert transform2.stats.updated == 3
        assert transform2.stats.created == 0

    def test_changed_docs_are_updated(self, db_session, dataset):
        """Re-ingestion with changed content updates those documents."""
        transform = PersistenceTransform(dataset_id=dataset.id, dataset_name=dataset.name)
        docs = _make_docs({"a.md": "AAA", "b.md": "BBB", "c.md": "CCC"})

        with use_session(db_session):
            transform(docs)

        # Change one document, re-ingest all
        transform2 = PersistenceTransform(dataset_id=dataset.id, dataset_name=dataset.name)
        docs2 = _make_docs({"a.md": "AAA", "b.md": "CHANGED", "c.md": "CCC"})

        with use_session(db_session):
            result2 = transform2(docs2)

        assert len(result2) == 3
        assert transform2.stats.updated == 3
        assert transform2.stats.created == 0

    def test_all_nodes_always_pass_through(self, db_session, dataset):
        """All nodes pass downstream regardless of content changes."""
        transform = PersistenceTransform(dataset_id=dataset.id, dataset_name=dataset.name)
        docs = _make_docs({"a.md": "AAA", "b.md": "BBB"})

        with use_session(db_session):
            transform(docs)

        # Re-ingest same content
        transform2 = PersistenceTransform(dataset_id=dataset.id, dataset_name=dataset.name)
        docs2 = _make_docs({"a.md": "AAA", "b.md": "BBB"})

        with use_session(db_session):
            result2 = transform2(docs2)

        assert len(result2) == 2
        assert transform2.stats.updated == 2

    def test_metadata_change_produces_different_hash(self, db_session, dataset):
        """Metadata-only changes produce a different content_hash in the DB."""
        transform = PersistenceTransform(dataset_id=dataset.id, dataset_name=dataset.name)
        docs = _make_docs(
            {"a.md": "Hello"},
            metadata={"a.md": {"_ontology_meta": {"tags": ["foo"]}}},
        )

        with use_session(db_session):
            transform(docs)
            repo = DocumentRepository()
            doc1 = repo.get_by_path(dataset.id, "a.md")
            hash1 = doc1.content_hash

        # Same body, different metadata
        transform2 = PersistenceTransform(dataset_id=dataset.id, dataset_name=dataset.name)
        docs2 = _make_docs(
            {"a.md": "Hello"},
            metadata={"a.md": {"_ontology_meta": {"tags": ["foo", "bar"]}}},
        )

        with use_session(db_session):
            transform2(docs2)
            repo2 = DocumentRepository()
            doc2 = repo2.get_by_path(dataset.id, "a.md")
            hash2 = doc2.content_hash

        assert hash1 != hash2, "Metadata change must produce different content_hash"


class TestContentHash:
    """Tests for the _compute_content_hash function."""

    def test_body_only(self):
        """Hash of body only is deterministic."""
        h1 = _compute_content_hash("hello")
        h2 = _compute_content_hash("hello")
        assert h1 == h2

    def test_different_body(self):
        """Different body produces different hash."""
        h1 = _compute_content_hash("hello")
        h2 = _compute_content_hash("world")
        assert h1 != h2

    def test_metadata_included(self):
        """Adding metadata changes the hash."""
        h1 = _compute_content_hash("hello")
        h2 = _compute_content_hash("hello", '{"tags": ["foo"]}')
        assert h1 != h2

    def test_different_metadata(self):
        """Different metadata produces different hash."""
        h1 = _compute_content_hash("hello", '{"tags": ["foo"]}')
        h2 = _compute_content_hash("hello", '{"tags": ["bar"]}')
        assert h1 != h2

    def test_none_metadata_same_as_no_metadata(self):
        """None metadata produces same hash as no metadata."""
        h1 = _compute_content_hash("hello")
        h2 = _compute_content_hash("hello", None)
        assert h1 == h2


class TestDeactivateMissing:
    """Tests for DocumentRepository.deactivate_missing."""

    def test_deactivates_missing_paths(self, db_session, dataset):
        """Documents not in active_paths are deactivated."""
        transform = PersistenceTransform(dataset_id=dataset.id, dataset_name=dataset.name)
        docs = _make_docs({"a.md": "AAA", "b.md": "BBB", "c.md": "CCC"})

        with use_session(db_session):
            transform(docs)

            repo = DocumentRepository()
            # Only a.md and c.md are in the new batch
            deactivated = repo.deactivate_missing(dataset.id, {"a.md", "c.md"})

        assert deactivated == 1  # b.md was deactivated

        with use_session(db_session):
            repo = DocumentRepository()
            doc_b = repo.get_by_path(dataset.id, "b.md")
            assert doc_b.active is False

            doc_a = repo.get_by_path(dataset.id, "a.md")
            assert doc_a.active is True

    def test_deactivates_all_when_empty_set(self, db_session, dataset):
        """Empty active_paths deactivates all documents."""
        transform = PersistenceTransform(dataset_id=dataset.id, dataset_name=dataset.name)
        docs = _make_docs({"a.md": "AAA", "b.md": "BBB"})

        with use_session(db_session):
            transform(docs)
            repo = DocumentRepository()
            deactivated = repo.deactivate_missing(dataset.id, set())

        assert deactivated == 2

    def test_no_deactivation_when_all_present(self, db_session, dataset):
        """No deactivation when all paths are in active_paths."""
        transform = PersistenceTransform(dataset_id=dataset.id, dataset_name=dataset.name)
        docs = _make_docs({"a.md": "AAA", "b.md": "BBB"})

        with use_session(db_session):
            transform(docs)
            repo = DocumentRepository()
            deactivated = repo.deactivate_missing(
                dataset.id, {"a.md", "b.md"}
            )

        assert deactivated == 0
