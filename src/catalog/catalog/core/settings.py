"""catalog.core.settings - Library configuration via pydantic-settings.

Extends agentlayer.settings.SubstrateSettings with catalog-specific fields
(embedding, LLM, langfuse, qdrant, vector_db, zvec, rag).

All settings use the SUBSTRATE_ prefix for environment variables.

Example usage:
    from catalog.core.settings import get_settings

    settings = get_settings()
    print(settings.config_root)
    print(settings.databases.catalog_path)

Environment variables:
    SUBSTRATE_ENVIRONMENT - Application environment: dev (default), prod, staging, test
    SUBSTRATE_CONFIG_ROOT - Override config root for current environment
    SUBSTRATE_CONFIG_ROOT_DEV, SUBSTRATE_CONFIG_ROOT_PROD, etc. - Per-environment config root
    SUBSTRATE_VECTOR_STORE_PATH - LlamaIndex persist directory (override)
    SUBSTRATE_EMBEDDING_MODEL - Name/path of embedding model
    SUBSTRATE_LLM_MODEL_NAME - Name/path of generative LLM for reranking/expansion
    SUBSTRATE_LOG_LEVEL - Logging level (default: INFO)
    SUBSTRATE_BATCH_SIZE - Default batch size for processing
    SUBSTRATE_CONCURRENCY - Default concurrency level
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Re-export base types from agentlayer so existing imports still work
from agentlayer.settings import (  # noqa: F401
    DEFAULT_CONFIG_ROOTS,
    DatabasesSettings,
    EmbeddingSettings,
    Environment,
    LLMSettings,
    LogLevel,
    PerformanceSettings,
    SubstrateSettings,
    _resolve_config_root_from_env,
)

__all__ = [
    "DEFAULT_CONFIG_ROOTS",
    "DatabasesSettings",
    "EmbeddingSettings",
    "Environment",
    "LLMSettings",
    "QdrantSettings",
    "RAGSettings",
    "Settings",
    "VectorDBSettings",
    "ZvecSettings",
    "get_settings",
]


class LangfuseSettings(BaseSettings):
    """Langfuse observability settings (placeholder for future implementation).

    These settings will be used to configure Langfuse integration for
    observability and tracing of LLM calls.
    """

    model_config = SettingsConfigDict(
        env_prefix="SUBSTRATE_LANGFUSE_",
        extra="ignore",
    )

    enabled: bool = Field(
        default=False,
        description="Enable Langfuse observability integration",
    )
    public_key: str | None = Field(
        default=None,
        description="Langfuse public key",
    )
    secret_key: str | None = Field(
        default=None,
        description="Langfuse secret key",
    )
    host: str | None = Field(
        default=None,
        description="Langfuse host URL (for self-hosted instances)",
    )


class QdrantSettings(BaseSettings):
    """Qdrant vector store configuration.

    Controls the Qdrant collection settings for vector storage.
    Uses local persistent mode by default (path from Settings.vector_store_path).
    """

    model_config = SettingsConfigDict(
        env_prefix="SUBSTRATE_QDRANT_",
        extra="ignore",
    )

    collection_name: str = Field(
        default="catalog_vectors",
        description="Qdrant collection name for vector storage",
    )


class ZvecSettings(BaseSettings):
    """Zvec vector store configuration.

    Zvec is the primary vector backend, using LlamaIndex SimpleVectorStore
    with a local JSON index file.
    """

    model_config = SettingsConfigDict(
        env_prefix="SUBSTRATE_ZVEC_",
        extra="ignore",
    )

    index_path: Path | None = Field(
        default=None,
        description="Path to local JSON file used for Zvec semantic queries (default: config_root / 'zvec' / 'index.json')",
    )
    collection_name: str = Field(
        default="catalog_vectors",
        description="Zvec collection name for vector storage",
    )


class VectorDBSettings(BaseSettings):
    """Vector database backend selection and feature gates."""

    model_config = SettingsConfigDict(
        env_prefix="SUBSTRATE_VECTOR_DB_",
        extra="ignore",
    )

    backend: Literal["qdrant", "zvec"] = Field(
        default="zvec",
        description="Vector backend used by VectorStoreManager",
    )


class RAGSettings(BaseSettings):
    """RAG configuration with environment variable support.

    Controls all RAG behavior including chunking, embedding, query expansion,
    RRF fusion, reranking, and caching. All settings can be overridden via
    environment variables with the SUBSTRATE_RAG__ prefix.

    Example:
        SUBSTRATE_RAG__CHUNK_SIZE=1000
        SUBSTRATE_RAG__RRF_K=80
    """

    model_config = SettingsConfigDict(
        env_prefix="SUBSTRATE_RAG__",
        extra="ignore",
    )

    tracing: bool = Field(
        default=False,
        description="Enable detailed tracing of RAG pipeline (for debugging, may impact performance)",
    )

    # Chunking
    chunk_size: int = Field(
        default=800,
        ge=100,
        description="Target chunk size in tokens",
    )
    chunk_overlap: int = Field(
        default=120,
        ge=0,
        description="Token overlap between chunks",
    )
    chunk_fallback_enabled: bool = Field(
        default=True,
        description="Enable char-based fallback when tokenizer fails",
    )
    chunk_chars_per_token: int = Field(
        default=4,
        ge=1,
        description="Estimated chars per token for fallback calculation",
    )

    # Embedding
    embed_batch_size: int = Field(
        default=32,
        ge=1,
        description="Batch size for embedding generation",
    )
    embed_fallback_enabled: bool = Field(
        default=True,
        description="Enable single-item fallback on batch embedding failure",
    )
    embed_prefix_query: str = Field(
        default="task: search result | query: ",
        description="Prefix for query embeddings (Nomic-style)",
    )
    embed_prefix_doc: str = Field(
        default="title: {title} | text: ",
        description="Prefix template for document embeddings (Nomic-style)",
    )

    # Query expansion
    expansion_enabled: bool = Field(
        default=True,
        description="Enable LLM-powered query expansion",
    )
    expansion_max_lex: int = Field(
        default=3,
        ge=0,
        le=5,
        description="Maximum lexical (BM25) query expansions",
    )
    expansion_max_vec: int = Field(
        default=3,
        ge=0,
        le=5,
        description="Maximum semantic (vector) query expansions",
    )
    expansion_include_hyde: bool = Field(
        default=True,
        description="Include HyDE (hypothetical document) in expansion",
    )

    # RRF fusion
    rrf_k: int = Field(
        default=60,
        ge=1,
        description="RRF constant k (higher = more weight to lower ranks)",
    )
    rrf_original_weight: float = Field(
        default=2.0,
        ge=0.0,
        description="Weight multiplier for original query results",
    )
    rrf_expansion_weight: float = Field(
        default=1.0,
        ge=0.0,
        description="Weight multiplier for expansion query results",
    )
    rrf_rank1_bonus: float = Field(
        default=0.05,
        ge=0.0,
        description="Score bonus for rank 1 results",
    )
    rrf_rank23_bonus: float = Field(
        default=0.02,
        ge=0.0,
        description="Score bonus for rank 2-3 results",
    )

    # Heading bias mitigation
    bm25_heading_weight_informational: float = Field(
        default=0.25,
        ge=0.0,
        description="BM25 weight for heading_text column on informational queries",
    )
    bm25_heading_weight_navigational: float = Field(
        default=0.80,
        ge=0.0,
        description="BM25 weight for heading_text column on navigational queries",
    )
    rrf_fts_weight_informational: float = Field(
        default=1.5,
        ge=0.0,
        description="RRF weight for FTS retriever on informational queries",
    )
    rrf_vector_weight_informational: float = Field(
        default=2.0,
        ge=0.0,
        description="RRF weight for vector retriever on informational queries",
    )
    rrf_fts_weight_navigational: float = Field(
        default=2.5,
        ge=0.0,
        description="RRF weight for FTS retriever on navigational queries",
    )
    rrf_vector_weight_navigational: float = Field(
        default=1.0,
        ge=0.0,
        description="RRF weight for vector retriever on navigational queries",
    )
    hybrid_dedupe_enabled: bool = Field(
        default=True,
        description="Enable per-document deduplication in hybrid retrieval",
    )

    # Reranking
    rerank_top_n: int = Field(
        default=10,
        ge=1,
        description="Number of results to return after reranking",
    )
    rerank_candidates: int = Field(
        default=40,
        ge=1,
        description="Number of candidates to consider for reranking",
    )
    rerank_provider: str = Field(
        default="mlx",
        description="LLM provider for reranking: 'mlx' (local) or 'openai'",
    )
    rerank_cache_enabled: bool = Field(
        default=True,
        description="Enable caching of rerank scores",
    )

    # Caching
    cache_ttl_hours: int = Field(
        default=168,
        ge=1,
        description="Cache TTL in hours (default 1 week)",
    )

    # Retrieval
    vector_top_k: int = Field(
        default=20,
        ge=1,
        description="Number of results from vector retriever",
    )
    fts_top_k: int = Field(
        default=20,
        ge=1,
        description="Number of results from FTS retriever",
    )
    fusion_top_k: int = Field(
        default=30,
        ge=1,
        description="Number of results after RRF fusion",
    )

    # Snippets
    snippet_max_lines: int = Field(
        default=10,
        ge=1,
        description="Maximum lines in snippet output",
    )
    snippet_context_lines: int = Field(
        default=2,
        ge=0,
        description="Context lines around snippet",
    )


class Settings(SubstrateSettings):
    """Main configuration settings for the catalog library.

    Extends SubstrateSettings with catalog-specific fields for embedding,
    LLM, langfuse, qdrant, vector_db, zvec, and rag configuration.

    Configuration is loaded from environment variables with the SUBSTRATE_ prefix.
    All config/data paths derive from config_root, which is set by environment
    (or SUBSTRATE_CONFIG_ROOT / SUBSTRATE_CONFIG_ROOT_<ENV>).
    """

    _toml_dir: ClassVar[Path | None] = Path(__file__).resolve().parent

    # Nested catalog-specific settings (embedding and llm inherited from SubstrateSettings)
    langfuse: LangfuseSettings = Field(
        default_factory=LangfuseSettings,
        description="Langfuse observability settings (placeholder)",
    )
    qdrant: QdrantSettings = Field(
        default_factory=QdrantSettings,
        description="Qdrant vector store settings",
    )
    vector_db: VectorDBSettings = Field(
        default_factory=VectorDBSettings,
        description="Vector backend selection and feature gates",
    )
    zvec: ZvecSettings = Field(
        default_factory=ZvecSettings,
        description="Zvec vector store settings",
    )
    rag: RAGSettings = Field(
        default_factory=RAGSettings,
        description="RAG configuration (chunking, expansion, reranking, caching)",
    )

    # # Legacy single database path (deprecated, use databases.catalog_path)
    # database_path: Path = Field(
    #     default=Path("~/.idx/catalog.db").expanduser(),
    #     description="Path to the SQLite database file (deprecated: use databases.catalog_path)",
    # )

    # # Model configuration
    # embedding_model: str = Field(
    #     default="BAAI/bge-small-en-v1.5",
    #     description="Name or path of the embedding model",
    # )

    @model_validator(mode="after")
    def _resolve_config_root_and_derived_paths(self) -> Settings:
        """Resolve config_root and derived paths, including zvec.index_path."""
        # Call parent resolver for base paths
        super()._resolve_config_root_and_derived_paths()

        # Resolve zvec-specific path
        assert self.config_root is not None
        if self.zvec.index_path is None:
            self.zvec.index_path = self.config_root / "zvec" / "index.json"
        else:
            self.zvec.index_path = Path(self.zvec.index_path).expanduser().resolve()

        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get the singleton Settings instance.

    Returns a cached Settings instance, creating it on first call.
    The settings are loaded from environment variables.

    Returns:
        The singleton Settings instance.

    Example:
        settings = get_settings()
        print(settings.databases.catalog_path)
    """
    settings = Settings()
    settings.ensure_directories()
    return settings
