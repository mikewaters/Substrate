"""Tests for catalog.index.pipelines module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from llama_index.core.schema import Document as LlamaDocument, TextNode
from sqlalchemy.orm import sessionmaker

from index.pipelines import DatasetIndexPipeline
from index.pipelines.schemas import IndexResult
from catalog.store.database import Base, create_engine_for_path
from index.store.fts import create_fts_table
from index.store.fts_chunk import create_chunks_fts_table
from agentlayer.session import use_session
from index.store.vector import VectorStoreManager
from index.transform.llama import ChunkPersistenceTransform, DocumentFTSTransform
from index.transform.splitter import ResilientSplitter
from index.transform.embedding import EmbeddingPrefixTransform


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


def _make_nodes(contents: dict[str, str], doc_id_start: int = 1) -> list[LlamaDocument]:
    """Build LlamaIndex document nodes with doc_id in metadata."""
    nodes = []
    for i, (path, body) in enumerate(contents.items()):
        doc = LlamaDocument(text=body, id_=path)
        doc.metadata = {
            "relative_path": path,
            "doc_id": doc_id_start + i,
            "path": path,
        }
        nodes.append(doc)
    return nodes


class TestDatasetIndexPipeline:
    """Tests for DatasetIndexPipeline class."""

    @pytest.fixture(autouse=True)
    def use_mock_embedding(self, patched_embedding) -> None:
        """Use mock embedding model for all tests."""
        yield

    def test_pipeline_initialization(self) -> None:
        """Index pipeline can be initialized with required fields."""
        pipeline = DatasetIndexPipeline(
            dataset_id=1,
            dataset_name="test-ds",
        )
        assert pipeline.dataset_id == 1
        assert pipeline.dataset_name == "test-ds"

    def test_build_pipeline_has_index_transforms(self) -> None:
        """Index pipeline contains FTS, splitter, chunk persist, and embedding transforms."""
        pipeline = DatasetIndexPipeline(
            dataset_id=1,
            dataset_name="test-ds",
        )
        vector_manager = VectorStoreManager()
        ingestion_pipeline = pipeline.build_pipeline(vector_manager=vector_manager)

        transform_types = [type(t) for t in ingestion_pipeline.transformations]

        assert DocumentFTSTransform in transform_types, "DocumentFTSTransform not found"
        assert ResilientSplitter in transform_types, "ResilientSplitter not found"
        assert ChunkPersistenceTransform in transform_types, "ChunkPersistenceTransform not found"
        assert EmbeddingPrefixTransform in transform_types, "EmbeddingPrefixTransform not found"

    def test_index_returns_index_result(self, db_session) -> None:
        """index() returns an IndexResult with correct stats."""
        pipeline = DatasetIndexPipeline(
            dataset_id=1,
            dataset_name="test-ds",
        )
        nodes = _make_nodes({
            "a.md": "# Hello\n\nSome content about testing.",
            "b.md": "# World\n\nMore content here.",
        })

        with use_session(db_session):
            result = pipeline.index(nodes=nodes)

        assert isinstance(result, IndexResult)
        assert result.dataset_id == 1
        assert result.dataset_name == "test-ds"
        assert result.fts_documents_indexed == 2
        assert result.completed_at is not None

    def test_index_empty_nodes(self, db_session) -> None:
        """index() handles empty node list gracefully."""
        pipeline = DatasetIndexPipeline(
            dataset_id=1,
            dataset_name="test-ds",
        )

        with use_session(db_session):
            result = pipeline.index(nodes=[])

        assert isinstance(result, IndexResult)
        assert result.fts_documents_indexed == 0
        assert result.chunks_created == 0
        assert result.vectors_inserted == 0

    def test_index_runs_reconciliation_before_indexing(self, db_session) -> None:
        """index() runs reconciliation (inactive doc cleanup) before loading nodes."""
        from index.store.cleanup import ReconciliationStats

        pipeline = DatasetIndexPipeline(
            dataset_id=1,
            dataset_name="test-ds",
        )
        nodes = _make_nodes({"a.md": "Content"})

        with patch.object(
            pipeline,
            "_reconcile_inactive_documents",
            return_value=ReconciliationStats(
                documents_reconciled=0,
                document_fts_deleted=0,
                chunk_fts_deleted=0,
                vector_docs_deleted=0,
            ),
        ) as mock_reconcile:
            with use_session(db_session):
                result = pipeline.index(nodes=nodes)

        mock_reconcile.assert_called_once()
        assert len(mock_reconcile.call_args[0]) == 1
        assert isinstance(result, IndexResult)


class TestDocumentFTSTransform:
    """Tests for the DocumentFTSTransform component."""

    def test_transform_indexes_to_fts(self, db_session) -> None:
        """DocumentFTSTransform calls FTSManager.upsert for each node."""
        from index.store.fts import FTSManager

        nodes = _make_nodes({"a.md": "Hello world", "b.md": "Goodbye world"})

        with use_session(db_session):
            transform = DocumentFTSTransform()
            result = transform(nodes)

        # Passthrough: all nodes returned
        assert len(result) == 2

        # Verify FTS entries exist
        with use_session(db_session):
            fts = FTSManager()
            # Search should find the indexed content
            from sqlalchemy import text
            rows = db_session.execute(
                text("SELECT rowid, path FROM documents_fts WHERE documents_fts MATCH 'hello'")
            ).fetchall()
            assert len(rows) >= 1

    def test_transform_skips_nodes_without_doc_id(self, db_session) -> None:
        """Nodes without doc_id are skipped (no error)."""
        doc = LlamaDocument(text="no doc_id here", id_="orphan.md")
        doc.metadata = {"path": "orphan.md"}

        with use_session(db_session):
            transform = DocumentFTSTransform()
            result = transform([doc])

        # Should still return the node (passthrough)
        assert len(result) == 1
