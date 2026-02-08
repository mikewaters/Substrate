"""Pydantic schemas for pipeline input/output.

Defines the models used for configuring and reporting pipeline results.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class DocumentStats(BaseModel):
    """Statistics for a single document ingestion.

    Attributes:
        path: Document path.
        action: What happened (created, updated, skipped).
        content_hash: SHA256 hash of the content.
    """

    path: str
    action: str  # "created", "updated", "skipped"
    content_hash: str


class IngestResult(BaseModel):
    """Result of an ingestion operation.

    Attributes:
        dataset_id: ID of the dataset.
        dataset_name: Normalized name of the dataset.
        documents_read: Total number of documents read.
        documents_created: Number of new documents created.
        documents_updated: Number of documents updated.
        documents_skipped: Number of unchanged documents skipped (filtered by docstore).
        documents_deactivated: Number of documents deactivated (removed from source).
        documents_failed: Number of documents that failed to process.
        chunks_created: Number of chunks indexed in FTS.
        vectors_inserted: Number of vectors inserted into vector store.
        started_at: When the ingestion started.
        completed_at: When the ingestion completed.
        errors: List of error messages if any.
    """

    dataset_id: int
    dataset_name: str
    documents_read: int = 0
    documents_created: int = 0
    documents_updated: int = 0
    documents_skipped: int = 0
    documents_deactivated: int = 0
    documents_failed: int = 0
    chunks_created: int = 0
    vectors_inserted: int = 0
    started_at: datetime
    completed_at: datetime | None = None
    errors: list[str] = Field(default_factory=list)

    @property
    def total_processed(self) -> int:
        """Total documents processed successfully."""
        return self.documents_created + self.documents_updated + self.documents_skipped

    @property
    def success(self) -> bool:
        """Whether the ingestion completed without errors."""
        return self.documents_failed == 0 and len(self.errors) == 0


__all__ = [
    "DocumentStats",
    "IngestResult",
]
