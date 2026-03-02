"""index.store.cleanup - Cleanup hooks for derived indexes.

Provides cleanup functionality for FTS and vector indexes when
documents are soft-deleted or removed.

Example usage:
    from index.store.cleanup import IndexCleanup

    cleanup = IndexCleanup(session)
    cleanup.reconcile_inactive_documents(parent_id, dataset_name, vector_manager)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from agentlayer.logging import get_logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from catalog.ingest.directory import DirectorySource
from index.store.fts import FTSManager
from index.store.fts_chunk import FTSChunkManager
from catalog.store.repositories import DocumentRepository

if TYPE_CHECKING:
    from index.store.vector import VectorStoreManager

__all__ = [
    "IndexCleanup",
    "ReconciliationStats",
    "cleanup_fts_for_document",
    "cleanup_fts_for_inactive_documents",
    "cleanup_stale_documents",
]

logger = get_logger(__name__)


@dataclass
class ReconciliationStats:
    """Aggregate counts from reconciling inactive documents.

    Attributes:
        documents_reconciled: Number of inactive documents processed.
        document_fts_deleted: Document-level FTS rows removed.
        chunk_fts_deleted: Chunk-level FTS rows removed.
        vector_docs_deleted: Number of source documents removed from vector store.
    """

    documents_reconciled: int
    document_fts_deleted: int
    chunk_fts_deleted: int
    vector_docs_deleted: int


class IndexCleanup:
    """Manages cleanup of derived indexes (FTS, vector) for documents.

    Provides methods to clean up FTS entries and vector nodes when
    documents are soft-deleted or removed.
    """

    def __init__(self, session: Session) -> None:
        """Initialize the cleanup manager.

        Args:
            session: SQLAlchemy session for database operations.
        """
        self._session = session
        self._fts = FTSManager(session)
        self._fts_chunk = FTSChunkManager(session)

    def reconcile_inactive_documents(
        self,
        parent_id: int,
        dataset_name: str,
        vector_manager: VectorStoreManager | None = None,
    ) -> ReconciliationStats:
        """Remove all index artifacts for inactive documents in the dataset.

        Queries documents where active=0 for the given parent_id, then for each
        removes document FTS, chunk FTS, and (if vector_manager provided) vector
        entries. Uses source_doc_id = f"{dataset_name}:{path}" as the canonical
        per-document key. Safe to run repeatedly; idempotent once artifacts are gone.

        Args:
            parent_id: Dataset (parent) ID to reconcile.
            dataset_name: Dataset name for building source_doc_id.
            vector_manager: Optional; when provided, deletes vectors per source_doc_id.

        Returns:
            ReconciliationStats with aggregate counts.
        """
        result = self._session.execute(
            text("""
                SELECT id, path
                FROM documents
                WHERE parent_id = :parent_id AND active = 0
            """),
            {"parent_id": parent_id},
        )
        rows = list(result)
        doc_fts_deleted = 0
        chunk_fts_deleted = 0
        vector_docs_deleted = 0

        for (doc_id, path) in rows:
            source_doc_id = f"{dataset_name}:{path}"
            try:
                doc_fts_deleted += self._fts.delete(doc_id)
            except Exception as e:
                logger.warning(f"Failed to delete document FTS for doc_id={doc_id}: {e}")
            try:
                chunk_fts_deleted += self._fts_chunk.delete_by_source_doc_id(source_doc_id)
            except Exception as e:
                logger.warning(
                    f"Failed to delete chunk FTS for source_doc_id={source_doc_id!r}: {e}"
                )
            if vector_manager is not None:
                try:
                    vector_manager.delete_source_doc(source_doc_id)
                    vector_docs_deleted += 1
                except Exception as e:
                    logger.warning(
                        f"Failed to delete vectors for source_doc_id={source_doc_id!r}: {e}"
                    )

        stats = ReconciliationStats(
            documents_reconciled=len(rows),
            document_fts_deleted=doc_fts_deleted,
            chunk_fts_deleted=chunk_fts_deleted,
            vector_docs_deleted=vector_docs_deleted,
        )
        if rows:
            logger.info(
                f"Reconciled {stats.documents_reconciled} inactive documents: "
                f"doc_fts={stats.document_fts_deleted} "
                f"chunk_fts={stats.chunk_fts_deleted} vectors={stats.vector_docs_deleted}"
            )
        return stats

    def cleanup_fts_for_document(self, doc_id: int) -> None:
        """Remove FTS entry for a single document.

        Args:
            doc_id: Document ID to remove from FTS.
        """
        self._fts.delete(doc_id)
        logger.debug(f"Cleaned up FTS for document {doc_id}")

    def cleanup_fts_for_documents(self, doc_ids: list[int]) -> int:
        """Remove FTS entries for multiple documents.

        Args:
            doc_ids: List of document IDs to remove from FTS.

        Returns:
            Number of FTS entries removed.
        """
        if not doc_ids:
            return 0
        count = self._fts.delete_many(doc_ids)
        logger.info(f"Cleaned up FTS for {count} documents")
        return count

    def cleanup_fts_for_inactive(self, parent_id: int | None = None) -> int:
        """Remove FTS entries for all inactive documents.

        Args:
            parent_id: Optional parent ID to limit cleanup scope.

        Returns:
            Number of FTS entries removed.
        """
        # Find inactive documents that still have FTS entries
        if parent_id is not None:
            result = self._session.execute(
                text("""
                    SELECT d.id
                    FROM documents d
                    WHERE d.active = 0
                    AND d.parent_id = :parent_id
                    AND EXISTS (
                        SELECT 1 FROM documents_fts f WHERE f.rowid = d.id
                    )
                """),
                {"parent_id": parent_id},
            )
        else:
            result = self._session.execute(
                text("""
                    SELECT d.id
                    FROM documents d
                    WHERE d.active = 0
                    AND EXISTS (
                        SELECT 1 FROM documents_fts f WHERE f.rowid = d.id
                    )
                """)
            )

        doc_ids = [row[0] for row in result]
        if doc_ids:
            return self.cleanup_fts_for_documents(doc_ids)
        return 0

    def cleanup_fts_for_parent(self, parent_id: int) -> int:
        """Remove all FTS entries for a parent.

        Used when deleting an entire parent and its documents.

        Args:
            parent_id: Parent ID to clean up.

        Returns:
            Number of FTS entries removed.
        """
        result = self._session.execute(
            text("""
                SELECT d.id
                FROM documents d
                WHERE d.parent_id = :parent_id
            """),
            {"parent_id": parent_id},
        )
        doc_ids = [row[0] for row in result]
        if doc_ids:
            return self.cleanup_fts_for_documents(doc_ids)
        return 0

    def delete_stale_documents(
        self,
        parent_id: int,
        stale_paths: set[str],
    ) -> int:
        """Hard-delete stale documents and their FTS entries.

        Removes documents from both the FTS index and the documents table.
        This is a destructive operation that cannot be undone.

        Args:
            parent_id: Parent ID containing the stale documents.
            stale_paths: Set of relative paths to delete.

        Returns:
            Number of documents deleted.
        """
        if not stale_paths:
            return 0

        # Get doc IDs for the stale paths
        paths_list = list(stale_paths)
        placeholders = ",".join([f":p{i}" for i in range(len(paths_list))])
        params = {f"p{i}": path for i, path in enumerate(paths_list)}
        params["parent_id"] = parent_id

        result = self._session.execute(
            text(f"""
                SELECT id
                FROM documents
                WHERE parent_id = :parent_id
                AND path IN ({placeholders})
            """),
            params,
        )
        doc_ids = [row[0] for row in result]

        if not doc_ids:
            return 0

        # Clean up FTS entries first
        self.cleanup_fts_for_documents(doc_ids)

        # Hard-delete the documents
        doc_repo = DocumentRepository(self._session)
        deleted_count = doc_repo.hard_delete_by_paths(parent_id, stale_paths)

        logger.info(
            f"Deleted {deleted_count} stale documents from parent {parent_id}"
        )
        return deleted_count

    # Vector cleanup methods (placeholder for future implementation)

    def cleanup_vectors_for_document(self, doc_id: int, content_hash: str) -> int:
        """Remove vector nodes for a document.

        Placeholder for vector store cleanup. Will be implemented
        when vector store is added.

        Args:
            doc_id: Document ID.
            content_hash: Content hash to identify vector nodes.

        Returns:
            Number of vector nodes removed.
        """
        # TODO: Implement vector store cleanup
        logger.debug(f"Vector cleanup placeholder for doc {doc_id}")
        return 0

    def cleanup_vectors_for_inactive(self, parent_id: int | None = None) -> int:
        """Remove vector nodes for all inactive documents.

        Placeholder for vector store cleanup.

        Args:
            parent_id: Optional parent ID to limit cleanup scope.

        Returns:
            Number of vector nodes removed.
        """
        # TODO: Implement vector store cleanup
        logger.debug("Vector cleanup placeholder for inactive documents")
        return 0


# Convenience functions

def cleanup_fts_for_document(session: Session, doc_id: int) -> None:
    """Remove FTS entry for a single document.

    Args:
        session: SQLAlchemy session.
        doc_id: Document ID to remove from FTS.
    """
    cleanup = IndexCleanup(session)
    cleanup.cleanup_fts_for_document(doc_id)


def cleanup_fts_for_inactive_documents(
    session: Session,
    parent_id: int | None = None,
) -> int:
    """Remove FTS entries for all inactive documents.

    Args:
        session: SQLAlchemy session.
        parent_id: Optional parent ID to limit cleanup scope.

    Returns:
        Number of FTS entries removed.
    """
    cleanup = IndexCleanup(session)
    return cleanup.cleanup_fts_for_inactive(parent_id)


def cleanup_stale_documents(
    session: Session,
    parent_id: int,
    source_path: Path,
    patterns: list[str] | None = None,
    dry_run: bool = False,
) -> int:
    """Find and remove documents that no longer exist in the source.

    Compares the current source directory contents against indexed documents
    and removes any documents that are no longer present in the source.

    Args:
        session: SQLAlchemy session for database operations.
        parent_id: Parent ID to check for stale documents.
        source_path: Path to the source directory.
        patterns: Glob patterns for file matching. Defaults to ["**/*.md"].
        dry_run: If True, only log stale paths without deleting.

    Returns:
        Number of stale documents found (dry_run) or deleted.
    """
    # Enumerate source paths
    source = DirectorySource(source_path, patterns=patterns)
    source_paths: set[str] = set()
    for doc in source.documents:
        source_paths.add(doc.metadata["relative_path"])

    # Get indexed paths from database
    doc_repo = DocumentRepository(session)
    indexed_paths = doc_repo.list_paths_by_parent(parent_id, active_only=False)

    # Find stale paths (in DB but not in source)
    stale_paths = indexed_paths - source_paths

    if not stale_paths:
        logger.debug(f"No stale documents found for parent {parent_id}")
        return 0

    if dry_run:
        logger.info(
            f"[DRY RUN] Found {len(stale_paths)} stale documents for parent "
            f"{parent_id}: {sorted(stale_paths)}"
        )
        return len(stale_paths)

    # Delete stale documents
    cleanup = IndexCleanup(session)
    return cleanup.delete_stale_documents(parent_id, stale_paths)
