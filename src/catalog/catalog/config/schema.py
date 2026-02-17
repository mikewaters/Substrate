"""catalog.config.schema - Pydantic models for YAML-based application config.

Mirrors the structure of ``catalog.core.settings`` but uses plain
``BaseModel`` instead of ``BaseSettings``. These models validate the
raw dict produced by Hydra/OmegaConf before merging with environment
variable overrides.

The ``AppConfig`` top-level model can be converted to a full
``catalog.core.settings.Settings`` instance via :meth:`AppConfig.to_settings`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

__all__ = [
    "AppConfig",
    "DatabasesConfig",
    "EmbeddingConfig",
    "LangfuseConfig",
    "PerformanceConfig",
    "QdrantConfig",
    "RAGConfig",
]


class LangfuseConfig(BaseModel):
    """Langfuse observability configuration."""

    enabled: bool = False
    public_key: str | None = None
    secret_key: str | None = None
    host: str | None = None


class EmbeddingConfig(BaseModel):
    """Embedding model configuration."""

    backend: Literal["mlx", "huggingface"] = "mlx"
    model_name: str = "mlx-community/all-MiniLM-L6-v2-bf16"
    batch_size: int = 32
    embedding_dim: int = 384


class PerformanceConfig(BaseModel):
    """Batch processing and concurrency configuration."""

    batch_size: int = 100
    concurrency: int = 4
    embedding_batch_size: int = 32
    chunk_max_bytes: int = 2048
    chunk_min_bytes: int = 128


class QdrantConfig(BaseModel):
    """Qdrant vector store configuration."""

    collection_name: str = "catalog_vectors"


class DatabasesConfig(BaseModel):
    """Multi-database path configuration."""

    catalog_path: Path = Field(default_factory=lambda: Path("~/.idx/catalog.db").expanduser())
    content_path: Path = Field(default_factory=lambda: Path("~/.idx/content.db").expanduser())


class RAGConfig(BaseModel):
    """RAG pipeline configuration."""

    # Chunking
    chunk_size: int = 800
    chunk_overlap: int = 120
    chunk_fallback_enabled: bool = True
    chunk_chars_per_token: int = 4

    # Embedding
    embed_batch_size: int = 32
    embed_fallback_enabled: bool = True
    embed_prefix_query: str = "task: search result | query: "
    embed_prefix_doc: str = "title: {title} | text: "

    # Query expansion
    expansion_enabled: bool = True
    expansion_max_lex: int = 3
    expansion_max_vec: int = 3
    expansion_include_hyde: bool = True

    # RRF fusion
    rrf_k: int = 60
    rrf_original_weight: float = 2.0
    rrf_expansion_weight: float = 1.0
    rrf_rank1_bonus: float = 0.05
    rrf_rank23_bonus: float = 0.02

    # Reranking
    rerank_top_n: int = 10
    rerank_candidates: int = 40
    rerank_cache_enabled: bool = True

    # Caching
    cache_ttl_hours: int = 168

    # Retrieval
    vector_top_k: int = 20
    fts_top_k: int = 20
    fusion_top_k: int = 30

    # Snippets
    snippet_max_lines: int = 10
    snippet_context_lines: int = 2


class AppConfig(BaseModel):
    """Top-level application configuration loaded from YAML.

    Mirrors the structure of ``catalog.core.settings.Settings`` exactly,
    allowing a 1:1 mapping between YAML keys and Settings fields.

    All fields carry the same defaults as their Settings counterparts,
    so partial YAML files work correctly: only specified keys override
    the defaults.
    """

    # Direct fields
    database_path: Path = Field(default_factory=lambda: Path("~/.idx/catalog.db").expanduser())
    vector_store_path: Path = Field(default_factory=lambda: Path("~/.idx/vector_store").expanduser())
    cache_path: Path = Field(default_factory=lambda: Path("~/.idx/cache").expanduser())
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    transformers_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # Nested configs
    databases: DatabasesConfig = Field(default_factory=DatabasesConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    langfuse: LangfuseConfig = Field(default_factory=LangfuseConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    qdrant: QdrantConfig = Field(default_factory=QdrantConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)

    def to_settings_dict(self) -> dict:
        """Convert to a dict suitable for constructing Settings.

        Serializes all fields (including nested models) to a flat dict
        that ``Settings(**d)`` can consume. Path objects are converted
        to strings for pydantic-settings compatibility.

        Returns:
            Dictionary with all config values.
        """
        data = self.model_dump()
        # Convert Path objects to strings for Settings constructor
        for key in ("database_path", "vector_store_path", "cache_path"):
            if isinstance(data.get(key), Path):
                data[key] = str(data[key])
        dbs = data.get("databases", {})
        for key in ("catalog_path", "content_path"):
            if isinstance(dbs.get(key), Path):
                dbs[key] = str(dbs[key])
        return data
