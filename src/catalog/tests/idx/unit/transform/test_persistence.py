"""Tests for PersistenceTransform skip-filtering behavior."""

from pathlib import Path

import pytest
from llama_index.core.schema import Document as LlamaDocument
from sqlalchemy.orm import sessionmaker

from catalog.store.database import Base, create_engine_for_path
from catalog.store.fts import create_fts_table
from catalog.store.fts_chunk import create_chunks_fts_table
from catalog.store.models import Dataset
from catalog.store.session_context import use_session
from catalog.transform.llama import PersistenceTransform


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


def _make_docs(contents: dict[str, str]) -> list[LlamaDocument]:
    """Build LlamaIndex documents from path->content mapping."""
    docs = []
    for path, body in contents.items():
        doc = LlamaDocument(text=body, id_=path)
        doc.metadata = {"relative_path": path}
        docs.append(doc)
    return docs


class TestPersistenceTransformFiltering:
    """PersistenceTransform filters skipped nodes from output."""

    def test_first_ingest_returns_all_nodes(self, db_session, dataset):
        """First ingestion returns all nodes (all created)."""
        transform = PersistenceTransform(dataset_id=dataset.id)
        docs = _make_docs({"a.md": "AAA", "b.md": "BBB", "c.md": "CCC"})

        with use_session(db_session):
            result = transform(docs)

        assert len(result) == 3
        assert transform.stats.created == 3
        assert transform.stats.skipped == 0

    def test_unchanged_docs_filtered_from_output(self, db_session, dataset):
        """Re-ingestion of unchanged docs returns empty list."""
        transform = PersistenceTransform(dataset_id=dataset.id)
        docs = _make_docs({"a.md": "AAA", "b.md": "BBB", "c.md": "CCC"})

        with use_session(db_session):
            result1 = transform(docs)
            assert len(result1) == 3

        # Second pass with same content
        transform2 = PersistenceTransform(dataset_id=dataset.id)
        docs2 = _make_docs({"a.md": "AAA", "b.md": "BBB", "c.md": "CCC"})

        with use_session(db_session):
            result2 = transform2(docs2)

        assert len(result2) == 0
        assert transform2.stats.skipped == 3
        assert transform2.stats.created == 0
        assert transform2.stats.updated == 0

    def test_only_changed_docs_pass_through(self, db_session, dataset):
        """Re-ingestion returns only changed documents."""
        transform = PersistenceTransform(dataset_id=dataset.id)
        docs = _make_docs({"a.md": "AAA", "b.md": "BBB", "c.md": "CCC"})

        with use_session(db_session):
            transform(docs)

        # Change one document
        transform2 = PersistenceTransform(dataset_id=dataset.id)
        docs2 = _make_docs({"a.md": "AAA", "b.md": "CHANGED", "c.md": "CCC"})

        with use_session(db_session):
            result2 = transform2(docs2)

        assert len(result2) == 1
        assert transform2.stats.updated == 1
        assert transform2.stats.skipped == 2

    def test_force_mode_returns_all_nodes(self, db_session, dataset):
        """Force mode passes all nodes through even if unchanged."""
        transform = PersistenceTransform(dataset_id=dataset.id)
        docs = _make_docs({"a.md": "AAA", "b.md": "BBB"})

        with use_session(db_session):
            transform(docs)

        # Force re-ingest
        transform2 = PersistenceTransform(dataset_id=dataset.id, force=True)
        docs2 = _make_docs({"a.md": "AAA", "b.md": "BBB"})

        with use_session(db_session):
            result2 = transform2(docs2)

        assert len(result2) == 2
        assert transform2.stats.updated == 2
        assert transform2.stats.skipped == 0
