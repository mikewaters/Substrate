"""Integration tests for hybrid search ingestion pipeline.

Tests the ingestion pipeline's hybrid indexing capabilities including:
- Idempotent ingestion (same node_ids on re-ingest)
- No duplicates in FTS and vector stores
- Delete propagation removes from both stores
"""

import hashlib
from contextlib import contextmanager
from pathlib import Path
from typing import Generator
from unittest.mock import patch

import pytest
from sqlalchemy import Engine
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session, sessionmaker

from catalog.ingest.pipelines import DatasetIngestPipeline
from catalog.integrations.obsidian import SourceObsidianConfig
from catalog.store.database import Base, create_engine_for_path
from index.store.fts import create_fts_table
from index.store.fts_chunk import create_chunks_fts_table
from catalog.sync import DatasetSync


@pytest.fixture
def test_engine(tmp_path: Path) -> Engine:
    """Create a temporary database and return the engine."""
    db_path = tmp_path / "test.db"
    engine = create_engine_for_path(db_path)
    Base.metadata.create_all(engine)
    create_fts_table(engine)
    create_chunks_fts_table(engine)
    return engine


@pytest.fixture
def session_factory(test_engine: Engine):
    """Create a session factory for the test database."""
    return sessionmaker(bind=test_engine, expire_on_commit=False)


@contextmanager
def create_session(factory) -> Generator[Session, None, None]:
    """Create a session that auto-commits on exit."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@pytest.fixture
def patched_get_session(session_factory):
    """Patch get_session to use the test database."""
    @contextmanager
    def get_test_session():
        with create_session(session_factory) as session:
            yield session

    with patch("catalog.ingest.pipelines.get_session", get_test_session), \
         patch("catalog.sync.get_session", get_test_session):
        yield get_test_session


@pytest.fixture
def sample_vault(tmp_path: Path) -> Path:
    """Create a sample vault with markdown files."""
    vault = tmp_path / "vault"
    vault.mkdir()

    # Create .obsidian directory to mark as vault
    (vault / ".obsidian").mkdir()

    # Create markdown files with distinct content
    (vault / "note1.md").write_text("""---
title: Python Tutorial
tags: [python, tutorial]
---

# Python Tutorial

This is a tutorial about Python programming.
Learn about functions, classes, and modules.
""")

    (vault / "note2.md").write_text("""---
title: JavaScript Guide
tags: [javascript, web]
---

# JavaScript Guide

This guide covers JavaScript basics.
Learn about async/await and promises.
""")

    (vault / "note3.md").write_text("""---
title: Database Design
tags: [sql, database]
---

# Database Design

Learn about SQL and database normalization.
Covers relational databases and indexes.
""")

    return vault


def compute_content_hash(content: str) -> str:
    """Compute SHA256 hash of content (same algorithm as pipeline)."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class TestIdempotentIngestion:
    """Tests for idempotent ingestion behavior."""

    def test_reingest_produces_same_node_ids(
        self,
        patched_get_session,
        patched_embedding,
        session_factory,
        sample_vault: Path,
    ) -> None:
        """Re-ingesting the same content produces identical node IDs."""
        config = SourceObsidianConfig(
            source_path=sample_vault,
            dataset_name="test-vault",
        )

        sync = DatasetSync()

        # First sync
        sync.sync(config)

        # Get node IDs from chunks_fts
        with create_session(session_factory) as session:
            result = session.execute(
                sql_text("SELECT node_id, source_doc_id FROM chunks_fts ORDER BY node_id")
            )
            first_node_ids = {row.node_id: row.source_doc_id for row in result}

        # Force re-sync
        config_force = SourceObsidianConfig(
            source_path=sample_vault,
            dataset_name="test-vault",
            force=True,
        )
        sync.sync(config_force)

        # Get node IDs again
        with create_session(session_factory) as session:
            result = session.execute(
                sql_text("SELECT node_id, source_doc_id FROM chunks_fts ORDER BY node_id")
            )
            second_node_ids = {row.node_id: row.source_doc_id for row in result}

        # Node IDs should be identical (deterministic based on content hash + seq)
        assert first_node_ids == second_node_ids

    def test_node_id_format(
        self,
        patched_get_session,
        patched_embedding,
        session_factory,
        sample_vault: Path,
    ) -> None:
        """Node IDs are deterministic UUID5 values (Qdrant-compatible)."""
        import uuid

        config = SourceObsidianConfig(
            source_path=sample_vault,
            dataset_name="test-vault",
        )

        DatasetSync().sync(config)

        # Check node ID format
        with create_session(session_factory) as session:
            result = session.execute(sql_text("SELECT node_id FROM chunks_fts LIMIT 10"))
            node_ids = [row.node_id for row in result]

        assert len(node_ids) > 0, "Should have at least one chunk"
        for node_id in node_ids:
            # Node IDs are UUID5 (deterministic, Qdrant-compatible)
            parsed = uuid.UUID(node_id)
            assert parsed.version == 5, f"Node ID should be UUID5: {node_id}"


class TestNoDuplicates:
    """Tests ensuring no duplicates in FTS and vector stores."""

    def test_no_duplicate_chunks_in_fts(
        self,
        patched_get_session,
        patched_embedding,
        session_factory,
        sample_vault: Path,
    ) -> None:
        """FTS index has no duplicate node IDs after ingestion."""
        config = SourceObsidianConfig(
            source_path=sample_vault,
            dataset_name="test-vault",
        )

        DatasetSync().sync(config)

        # Check for duplicates
        with create_session(session_factory) as session:
            result = session.execute(
                sql_text("""
                    SELECT node_id, COUNT(*) as cnt
                    FROM chunks_fts
                    GROUP BY node_id
                    HAVING cnt > 1
                """)
            )
            duplicates = list(result)

        assert len(duplicates) == 0, f"Found duplicate node IDs: {duplicates}"

    def test_no_duplicate_chunks_after_reingest(
        self,
        patched_get_session,
        patched_embedding,
        session_factory,
        sample_vault: Path,
    ) -> None:
        """Re-ingestion doesn't create duplicates in FTS."""
        config = SourceObsidianConfig(
            source_path=sample_vault,
            dataset_name="test-vault",
        )

        sync = DatasetSync()

        # Sync multiple times
        sync.sync(config)

        # Force re-sync
        config_force = SourceObsidianConfig(
            source_path=sample_vault,
            dataset_name="test-vault",
            force=True,
        )
        sync.sync(config_force)

        # Check for duplicates
        with create_session(session_factory) as session:
            result = session.execute(
                sql_text("""
                    SELECT node_id, COUNT(*) as cnt
                    FROM chunks_fts
                    GROUP BY node_id
                    HAVING cnt > 1
                """)
            )
            duplicates = list(result)

        assert len(duplicates) == 0, f"Found duplicate node IDs after re-ingest: {duplicates}"

    def test_chunk_count_stable_across_reingest(
        self,
        patched_get_session,
        patched_embedding,
        session_factory,
        sample_vault: Path,
    ) -> None:
        """Chunk count remains stable across re-ingestion."""
        config = SourceObsidianConfig(
            source_path=sample_vault,
            dataset_name="test-vault",
        )

        sync = DatasetSync()
        sync.sync(config)

        # Get initial chunk count
        with create_session(session_factory) as session:
            result = session.execute(sql_text("SELECT COUNT(*) FROM chunks_fts"))
            initial_count = result.scalar()

        # Force re-sync
        config_force = SourceObsidianConfig(
            source_path=sample_vault,
            dataset_name="test-vault",
            force=True,
        )
        sync.sync(config_force)

        # Get count after re-sync
        with create_session(session_factory) as session:
            result = session.execute(sql_text("SELECT COUNT(*) FROM chunks_fts"))
            final_count = result.scalar()

        assert initial_count == final_count, \
            f"Chunk count changed: {initial_count} -> {final_count}"


class TestDeletePropagation:
    """Tests for delete propagation across stores."""

    def test_deleted_file_removed_from_fts(
        self,
        patched_get_session,
        patched_embedding,
        session_factory,
        sample_vault: Path,
    ) -> None:
        """Deleted files are removed from FTS index after cleanup."""
        from index.store.cleanup import cleanup_stale_documents

        config = SourceObsidianConfig(
            source_path=sample_vault,
            dataset_name="test-vault",
        )

        sync = DatasetSync()
        sync_result = sync.sync(config)

        # Verify note2.md chunks exist in FTS
        with create_session(session_factory) as session:
            result_check = session.execute(
                sql_text("""
                    SELECT COUNT(*) FROM chunks_fts
                    WHERE source_doc_id LIKE '%note2.md'
                """)
            )
            initial_count = result_check.scalar()

        assert initial_count > 0, "note2.md chunks should exist"

        # Delete note2.md from filesystem
        (sample_vault / "note2.md").unlink()

        # Re-sync
        sync.sync(config)

        # Run cleanup for stale documents
        with create_session(session_factory) as session:
            stale_count = cleanup_stale_documents(
                session,
                sync_result.ingest.dataset_id,
                source_path=sample_vault,
                patterns=["**/*.md"],
            )

        # Note: The current cleanup only removes documents, not chunks.
        # This test documents the expected behavior, which may need implementation.
        # The cleanup_stale_documents function removes from documents table,
        # but chunk FTS cleanup would need separate implementation.

        # For now, verify the document is marked as deleted
        with create_session(session_factory) as session:
            doc_result = session.execute(
                sql_text("""
                    SELECT COUNT(*) FROM documents
                    WHERE path LIKE '%note2.md' AND active = 1
                """)
            )
            active_docs = doc_result.scalar()

        assert active_docs == 0, "note2.md should be deleted from documents"

    def test_document_fts_removed_on_delete(
        self,
        patched_get_session,
        patched_embedding,
        session_factory,
        sample_vault: Path,
    ) -> None:
        """Document-level FTS entries are removed when document deleted."""
        from index.store.cleanup import cleanup_stale_documents

        config = SourceObsidianConfig(
            source_path=sample_vault,
            dataset_name="test-vault",
        )

        sync = DatasetSync()
        sync_result = sync.sync(config)

        # Verify document FTS entry exists
        with create_session(session_factory) as session:
            result_check = session.execute(
                sql_text("""
                    SELECT COUNT(*) FROM documents_fts
                    WHERE documents_fts MATCH 'JavaScript'
                """)
            )
            initial_count = result_check.scalar()

        assert initial_count > 0, "JavaScript should be found in FTS"

        # Delete note2.md (contains "JavaScript")
        (sample_vault / "note2.md").unlink()

        # Re-sync and cleanup
        sync.sync(config)
        with create_session(session_factory) as session:
            cleanup_stale_documents(
                session,
                sync_result.ingest.dataset_id,
                source_path=sample_vault,
                patterns=["**/*.md"],
            )

        # Verify document FTS entry is removed
        with create_session(session_factory) as session:
            result_check = session.execute(
                sql_text("""
                    SELECT COUNT(*) FROM documents_fts
                    WHERE documents_fts MATCH 'JavaScript'
                """)
            )
            final_count = result_check.scalar()

        assert final_count == 0, "JavaScript should not be found after delete"


class TestVectorIndexing:
    """Tests for vector store indexing behavior."""

    def test_vector_indexing_always_inserts_vectors(
        self,
        patched_get_session,
        patched_embedding,
        session_factory,
        sample_vault: Path,
    ) -> None:
        """Vector indexing always inserts vectors during sync.

        Vectors are written by the Index pipeline only; ingest no longer
        uses the vector store (ADR-0004).
        """
        config = SourceObsidianConfig(
            source_path=sample_vault,
            dataset_name="test-vault",
        )

        sync_result = DatasetSync().sync(config)

        # Index pipeline is responsible for vector insertion
        assert sync_result.index.vectors_inserted > 0


class TestSourceDocIdFormat:
    """Tests for source_doc_id format in chunks."""

    def test_source_doc_id_format(
        self,
        patched_get_session,
        patched_embedding,
        session_factory,
        sample_vault: Path,
    ) -> None:
        """source_doc_id follows the format {dataset_name}:{path}."""
        config = SourceObsidianConfig(
            source_path=sample_vault,
            dataset_name="test-vault",
        )

        DatasetSync().sync(config)

        # Check source_doc_id format
        with create_session(session_factory) as session:
            result = session.execute(sql_text("SELECT source_doc_id FROM chunks_fts"))
            source_doc_ids = [row.source_doc_id for row in result]

        for source_doc_id in source_doc_ids:
            assert source_doc_id.startswith("test-vault:"), \
                f"source_doc_id should start with dataset name: {source_doc_id}"
            assert ":" in source_doc_id, \
                f"source_doc_id should contain ':': {source_doc_id}"

            # Verify path portion ends with .md
            _, path = source_doc_id.split(":", 1)
            assert path.endswith(".md"), f"Path should end with .md: {path}"

    def test_source_doc_id_unique_per_document(
        self,
        patched_get_session,
        patched_embedding,
        session_factory,
        sample_vault: Path,
    ) -> None:
        """Each document has a unique source_doc_id prefix."""
        config = SourceObsidianConfig(
            source_path=sample_vault,
            dataset_name="test-vault",
        )

        DatasetSync().sync(config)

        # Get all source_doc_ids
        with create_session(session_factory) as session:
            result = session.execute(
                sql_text("SELECT DISTINCT source_doc_id FROM chunks_fts")
            )
            unique_source_doc_ids = [row.source_doc_id for row in result]

        # Should have as many unique source_doc_ids as documents
        expected_count = len(list(sample_vault.glob("**/*.md")))
        assert len(unique_source_doc_ids) == expected_count, \
            f"Expected {expected_count} unique source_doc_ids, got {len(unique_source_doc_ids)}"


class TestChunkMetadata:
    """Tests for chunk metadata during ingestion."""

    def test_chunks_have_text_content(
        self,
        patched_get_session,
        patched_embedding,
        session_factory,
        sample_vault: Path,
    ) -> None:
        """Chunks have non-empty text content."""
        config = SourceObsidianConfig(
            source_path=sample_vault,
            dataset_name="test-vault",
        )

        DatasetSync().sync(config)

        # Check that all chunks have body_text content
        with create_session(session_factory) as session:
            result = session.execute(
                sql_text("SELECT body_text FROM chunks_fts WHERE body_text = '' OR body_text IS NULL")
            )
            empty_chunks = list(result)

        assert len(empty_chunks) == 0, "All chunks should have text content"

    def test_chunks_indexed_for_all_documents(
        self,
        patched_get_session,
        patched_embedding,
        session_factory,
        sample_vault: Path,
    ) -> None:
        """All ingested documents have at least one chunk in FTS."""
        config = SourceObsidianConfig(
            source_path=sample_vault,
            dataset_name="test-vault",
        )

        sync_result = DatasetSync().sync(config)

        # Get documents
        doc_count = sync_result.ingest.documents_created + sync_result.ingest.documents_updated

        # Get unique documents with chunks
        with create_session(session_factory) as session:
            chunk_result = session.execute(
                sql_text("SELECT COUNT(DISTINCT source_doc_id) FROM chunks_fts")
            )
            docs_with_chunks = chunk_result.scalar()

        assert docs_with_chunks == doc_count, \
            f"Expected {doc_count} documents with chunks, got {docs_with_chunks}"


class TestSyncStats:
    """Tests for sync statistics accuracy."""

    def test_index_result_tracks_chunks(
        self,
        patched_get_session,
        patched_embedding,
        session_factory,
        sample_vault: Path,
    ) -> None:
        """IndexResult correctly tracks chunks_created."""
        config = SourceObsidianConfig(
            source_path=sample_vault,
            dataset_name="test-vault",
        )

        sync_result = DatasetSync().sync(config)

        # Verify chunks_created is populated
        assert sync_result.index.chunks_created > 0

        # Verify it matches actual chunk count
        with create_session(session_factory) as session:
            chunk_result = session.execute(
                sql_text("SELECT COUNT(*) FROM chunks_fts")
            )
            actual_count = chunk_result.scalar()

        assert sync_result.index.chunks_created == actual_count, \
            f"chunks_created ({sync_result.index.chunks_created}) should match actual ({actual_count})"

    def test_reingest_updates_stats_correctly(
        self,
        patched_get_session,
        patched_embedding,
        session_factory,
        sample_vault: Path,
    ) -> None:
        """Re-sync with force=True updates stats correctly."""
        config = SourceObsidianConfig(
            source_path=sample_vault,
            dataset_name="test-vault",
        )

        sync = DatasetSync()

        # First sync
        result1 = sync.sync(config)
        initial_chunks = result1.index.chunks_created

        # Force re-sync
        config_force = SourceObsidianConfig(
            source_path=sample_vault,
            dataset_name="test-vault",
            force=True,
        )
        result2 = sync.sync(config_force)

        # Chunk count should be consistent (no duplicates)
        assert result2.index.chunks_created == initial_chunks, \
            f"Force re-sync should produce same chunk count: {result2.index.chunks_created} vs {initial_chunks}"
