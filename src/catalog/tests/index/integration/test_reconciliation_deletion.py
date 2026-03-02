"""Integration tests for index reconciliation of deleted (inactive) documents.

Verifies that after documents are marked inactive in the catalog, the index
pipeline's reconciliation pass removes them from document FTS and chunk FTS
so they no longer appear in search.
"""

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from agentlayer.session import use_session
from catalog.store.database import Base, create_engine_for_path
from catalog.store.models import Dataset, Document
from index.pipelines import DatasetIndexPipeline
from index.store.fts import FTSManager, create_fts_table
from index.store.fts_chunk import create_chunks_fts_table


@pytest.fixture
def db_session(tmp_path: Path):
    """Create a test database with FTS tables."""
    db_path = tmp_path / "test.db"
    engine = create_engine_for_path(db_path)
    Base.metadata.create_all(engine)
    create_fts_table(engine)
    create_chunks_fts_table(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    yield session
    session.close()


@pytest.fixture(autouse=True)
def use_mock_embedding(patched_embedding) -> None:
    """Use mock embedding for all tests in this module."""
    yield


def test_deleted_document_absent_from_fts_after_index(
    db_session,
) -> None:
    """After a doc is marked inactive, re-running index removes it from document and chunk FTS."""
    dataset = Dataset(
        name="test-ds",
        uri="dataset:test-ds",
        source_type="directory",
        source_path="/tmp/vault",
    )
    db_session.add(dataset)
    db_session.flush()

    doc1 = Document(
        parent_id=dataset.id,
        uri="document:test-ds/keep.md",
        path="keep.md",
        content_hash="h1",
        body="Content to keep",
        active=True,
    )
    doc2 = Document(
        parent_id=dataset.id,
        uri="document:test-ds/remove.md",
        path="remove.md",
        content_hash="h2",
        body="Content to remove",
        active=True,
    )
    db_session.add_all([doc1, doc2])
    db_session.flush()

    pipeline = DatasetIndexPipeline(
        dataset_id=dataset.id,
        dataset_name=dataset.name,
    )

    with use_session(db_session):
        pipeline.index()

    with use_session(db_session):
        fts = FTSManager()
        assert fts.count() == 2

    doc2.active = False
    db_session.flush()

    with use_session(db_session):
        pipeline.index()

    with use_session(db_session):
        fts = FTSManager()
        assert fts.count() == 1

    with use_session(db_session):
        result = db_session.execute(
            text("SELECT COUNT(*) FROM chunks_fts WHERE source_doc_id = :sid"),
            {"sid": f"{dataset.name}:remove.md"},
        ).fetchone()
        assert result[0] == 0
