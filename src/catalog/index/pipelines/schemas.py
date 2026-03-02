"""Pydantic schemas for index pipeline input/output."""

from datetime import datetime

from pydantic import BaseModel, Field


class IndexResult(BaseModel):
    """Result of an indexing operation.

    Attributes:
        dataset_id: ID of the dataset.
        dataset_name: Normalized name of the dataset.
        chunks_created: Number of chunks indexed in FTS.
        vectors_inserted: Number of vectors inserted into vector store.
        fts_documents_indexed: Number of documents indexed in document-level FTS.
        started_at: When the indexing started.
        completed_at: When the indexing completed.
        errors: List of error messages if any.
    """

    dataset_id: int
    dataset_name: str
    chunks_created: int = 0
    vectors_inserted: int = 0
    fts_documents_indexed: int = 0
    started_at: datetime
    completed_at: datetime | None = None
    errors: list[str] = Field(default_factory=list)

    @property
    def success(self) -> bool:
        """Whether the indexing completed without errors."""
        return len(self.errors) == 0


__all__ = [
    "IndexResult",
]
