"""catalog.core.settings - Library configuration via pydantic-settings.

Supports environment variables first; config-file support is deferred.

All settings use the IDX_ prefix for environment variables.

Example usage:
    from catalog.core.settings import get_settings

    settings = get_settings()
    print(settings.database_path)

Environment variables:
    IDX_DATABASE_PATH - Path to SQLite database
    IDX_VECTOR_STORE_PATH - LlamaIndex persist directory (rebuildable cache)
    IDX_EMBEDDING_MODEL - Name/path of embedding model
    IDX_LLM_MODEL_NAME - Name/path of generative LLM for reranking/expansion
    IDX_LOG_LEVEL - Logging level (default: INFO)
    IDX_BATCH_SIZE - Default batch size for processing
    IDX_CONCURRENCY - Default concurrency level
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = [
    "DatabasesSettings",
    "LLMSettings",
    "QdrantSettings",
    "RAGSettings",
    "Settings",
    "get_settings",
]


LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class LangfuseSettings(BaseSettings):
    """Langfuse observability settings (placeholder for future implementation).

    These settings will be used to configure Langfuse integration for
    observability and tracing of LLM calls.
    """

    model_config = SettingsConfigDict(
        env_prefix="IDX_LANGFUSE_",
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


class EmbeddingSettings(BaseSettings):
    """Embedding configuration for vector generation.

    Controls which embedding backend to use and model configuration.
    Supports MLX (Apple Silicon) and HuggingFace backends.
    """

    model_config = SettingsConfigDict(
        env_prefix="IDX_EMBEDDING_",
        extra="ignore",
    )

    backend: Literal["mlx", "huggingface"] = Field(
        default="mlx",
        description="Embedding backend: 'mlx' for Apple Silicon, 'huggingface' for general",
    )
    model_name: str = Field(
        default="mlx-community/all-MiniLM-L6-v2-bf16",
        description="Name or path of the embedding model",
    )
    batch_size: int = Field(
        default=32,
        ge=1,
        description="Batch size for embedding generation",
    )
    embedding_dim: int = Field(
        default=384,
        ge=1,
        description="Embedding vector dimension (384 for MiniLM-L6-v2)",
    )


class LLMSettings(BaseSettings):
    """LLM configuration for generative tasks (reranking, query expansion).

    Controls the local generative model used by MLXProvider. Must be an
    autoregressive model supported by mlx-lm (not BERT/cross-encoder).
    """

    model_config = SettingsConfigDict(
        env_prefix="IDX_LLM_",
        extra="ignore",
    )

    backend: Literal["mlx"] = Field(
        default="mlx",
        description="LLM backend: 'mlx' for Apple Silicon local inference",
    )
    model_name: str = Field(
        default="mlx-community/Llama-3.2-1B-Instruct-4bit",
        description="Name or path of the generative LLM (must be autoregressive, not BERT)",
    )


class PerformanceSettings(BaseSettings):
    """Default performance settings for batch processing and concurrency."""

    model_config = SettingsConfigDict(
        env_prefix="IDX_",
        extra="ignore",
    )

    batch_size: int = Field(
        default=100,
        ge=1,
        description="Default batch size for document processing",
    )
    concurrency: int = Field(
        default=4,
        ge=1,
        description="Default concurrency level for parallel operations",
    )
    embedding_batch_size: int = Field(
        default=32,
        ge=1,
        description="Batch size for embedding generation (deprecated: use embedding.batch_size)",
    )
    chunk_max_bytes: int = Field(
        default=2048,
        ge=256,
        description="Maximum bytes per chunk for embedding",
    )
    chunk_min_bytes: int = Field(
        default=128,
        ge=1,
        description="Minimum bytes per chunk (fragments smaller than this are merged)",
    )


class QdrantSettings(BaseSettings):
    """Qdrant vector store configuration.

    Controls the Qdrant collection settings for vector storage.
    Uses local persistent mode by default (path from Settings.vector_store_path).
    """

    model_config = SettingsConfigDict(
        env_prefix="IDX_QDRANT_",
        extra="ignore",
    )

    collection_name: str = Field(
        default="catalog_vectors",
        description="Qdrant collection name for vector storage",
    )


class DatabasesSettings(BaseSettings):
    """Multi-database configuration for separate catalog and content storage.

    The catalog database stores metadata, FTS indexes, and resource hierarchy.
    The content database stores document bodies and large text content.
    """

    model_config = SettingsConfigDict(
        env_prefix="IDX_DATABASES_",
        extra="ignore",
    )

    catalog_path: Path = Field(
        default=Path("~/.idx/catalog.db").expanduser(),
        description="Path to the catalog SQLite database (metadata, FTS, resources)",
    )
    content_path: Path = Field(
        default=Path("~/.idx/content.db").expanduser(),
        description="Path to the content SQLite database (document bodies)",
    )


class RAGSettings(BaseSettings):
    """RAG configuration with environment variable support.

    Controls all RAG behavior including chunking, embedding, query expansion,
    RRF fusion, reranking, and caching. All settings can be overridden via
    environment variables with the IDX_RAG__ prefix.

    Example:
        IDX_RAG__CHUNK_SIZE=1000
        IDX_RAG__RRF_K=80
    """

    model_config = SettingsConfigDict(
        env_prefix="IDX_RAG__",
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


class Settings(BaseSettings):
    """Main configuration settings for the idx library.

    Configuration is loaded from environment variables with the IDX_ prefix.
    Config-file support is deferred for the MVP.

    Attributes:
        database_path: Path to the SQLite database file (deprecated, use databases.catalog_path).
        databases: Multi-database configuration (catalog and content paths).
        vector_store_path: Path to the LlamaIndex persist directory (rebuildable cache).
        embedding_model: Name or path of the embedding model (deprecated).
        log_level: Logging level for the library.
        embedding: Embedding model configuration (backend, model_name, batch_size).
        llm: LLM model configuration for generative tasks (reranking, query expansion).
        langfuse: Langfuse observability settings (placeholder).
        performance: Default performance settings for batch processing.
    """

    model_config = SettingsConfigDict(
        env_prefix="IDX_",
        env_nested_delimiter="__",
        extra="ignore",
        validate_default=True,
    )

    # Multi-database configuration
    databases: DatabasesSettings = Field(
        default_factory=DatabasesSettings,
        description="Multi-database paths for catalog and content separation",
    )

    # # Legacy single database path (deprecated, use databases.catalog_path)
    # database_path: Path = Field(
    #     default=Path("~/.idx/catalog.db").expanduser(),
    #     description="Path to the SQLite database file (deprecated: use databases.catalog_path)",
    # )
    vector_store_path: Path = Field(
        default=Path("~/.idx/vector_store").expanduser(),
        description="Path to LlamaIndex persist directory (rebuildable cache)",
    )
    cache_path: Path = Field(
        default=Path("~/.idx/cache").expanduser(),
        description="Path to cache directory for temporary files",
    )
    job_config_path: Path = Field(
        default=Path("~/.idx/jobs").expanduser(),
        description="Path to job configuration files",
    )

    # Model configuration
    embedding_model: str = Field(
        default="BAAI/bge-small-en-v1.5",
        description="Name or path of the embedding model",
    )

    # Logging
    log_level: LogLevel = Field(
        default="INFO",
        description="Logging level for the library",
    )

    # Nested settings
    embedding: EmbeddingSettings = Field(
        default_factory=EmbeddingSettings,
        description="Embedding model configuration",
    )
    llm: LLMSettings = Field(
        default_factory=LLMSettings,
        description="LLM model configuration for generative tasks (reranking, query expansion)",
    )
    langfuse: LangfuseSettings = Field(
        default_factory=LangfuseSettings,
        description="Langfuse observability settings (placeholder)",
    )
    performance: PerformanceSettings = Field(
        default_factory=PerformanceSettings,
        description="Default performance settings",
    )
    qdrant: QdrantSettings = Field(
        default_factory=QdrantSettings,
        description="Qdrant vector store settings",
    )
    rag: RAGSettings = Field(
        default_factory=RAGSettings,
        description="RAG configuration (chunking, expansion, reranking, caching)",
    )

    def ensure_directories(self) -> None:
        """Ensure that required directories exist.

        Creates the parent directories for database paths and vector_store_path
        if they do not already exist.
        """
        self.databases.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        self.databases.content_path.parent.mkdir(parents=True, exist_ok=True)
        self.vector_store_path.mkdir(parents=True, exist_ok=True)
        self.cache_path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get the singleton Settings instance.

    Returns a cached Settings instance, creating it on first call.
    The settings are loaded from environment variables.

    Returns:
        The singleton Settings instance.

    Example:
        settings = get_settings()
        print(settings.database_path)
    """
    settings = Settings()
    settings.ensure_directories()
    return settings
