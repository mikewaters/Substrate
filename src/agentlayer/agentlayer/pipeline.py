"""agentlayer.pipeline - Base pipeline class for ingest and index stages.

Provides shared configuration, embedding model access, cache key generation,
and settings access used by both DatasetIngestPipeline and DatasetIndexPipeline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, Field

from agentlayer.embedding import get_embed_model

if TYPE_CHECKING:
    from llama_index.core.embeddings import BaseEmbedding

__all__ = [
    "BasePipeline",
]


class BasePipeline(BaseModel):
    """Shared base for ingest and index pipelines.

    Provides common fields and helpers that both pipeline stages need:
    dataset identity, embedding model access, cache keys, and RAG settings.
    """

    dataset_id: Optional[int] = None
    dataset_name: Optional[str] = None
    embed_model: Optional[Any] = None  # BaseEmbedding, but Any for Pydantic compat
    resilient_embedding: bool = Field(default=True)
    num_workers: int = Field(
        default=1,
        description="Reserved; pipelines run with 1 worker because persistence writes to SQLite.",
    )

    model_config = {"arbitrary_types_allowed": True}

    def _cache_key(self, dataset_name: str) -> str:
        """Generate a cache key for a dataset."""
        return f"{dataset_name}"

    def _get_embed_model(self) -> "BaseEmbedding":
        """Get embedding model, using resilient wrapper if enabled."""
        if self.embed_model is not None:
            return self.embed_model
        return get_embed_model(resilient=self.resilient_embedding)
