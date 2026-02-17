"""Tests for catalog.config.schema module."""

from pathlib import Path

from catalog.config.schema import (
    AppConfig,
    DatabasesConfig,
    EmbeddingConfig,
    LangfuseConfig,
    PerformanceConfig,
    QdrantConfig,
    RAGConfig,
)


class TestLangfuseConfig:
    """Tests for LangfuseConfig model."""

    def test_defaults(self) -> None:
        """LangfuseConfig defaults match LangfuseSettings."""
        cfg = LangfuseConfig()
        assert cfg.enabled is False
        assert cfg.public_key is None
        assert cfg.secret_key is None
        assert cfg.host is None


class TestEmbeddingConfig:
    """Tests for EmbeddingConfig model."""

    def test_defaults(self) -> None:
        """EmbeddingConfig defaults match EmbeddingSettings."""
        cfg = EmbeddingConfig()
        assert cfg.backend == "mlx"
        assert cfg.model_name == "mlx-community/all-MiniLM-L6-v2-bf16"
        assert cfg.batch_size == 32
        assert cfg.embedding_dim == 384

    def test_custom_values(self) -> None:
        """EmbeddingConfig accepts custom values."""
        cfg = EmbeddingConfig(
            backend="huggingface",
            model_name="BAAI/bge-small-en-v1.5",
            batch_size=64,
            embedding_dim=768,
        )
        assert cfg.backend == "huggingface"
        assert cfg.batch_size == 64


class TestPerformanceConfig:
    """Tests for PerformanceConfig model."""

    def test_defaults(self) -> None:
        """PerformanceConfig defaults match PerformanceSettings."""
        cfg = PerformanceConfig()
        assert cfg.batch_size == 100
        assert cfg.concurrency == 4
        assert cfg.embedding_batch_size == 32
        assert cfg.chunk_max_bytes == 2048
        assert cfg.chunk_min_bytes == 128


class TestQdrantConfig:
    """Tests for QdrantConfig model."""

    def test_defaults(self) -> None:
        """QdrantConfig defaults match QdrantSettings."""
        cfg = QdrantConfig()
        assert cfg.collection_name == "catalog_vectors"


class TestDatabasesConfig:
    """Tests for DatabasesConfig model."""

    def test_defaults(self) -> None:
        """DatabasesConfig defaults produce expanded home paths."""
        cfg = DatabasesConfig()
        assert cfg.catalog_path == Path("~/.idx/catalog.db").expanduser()
        assert cfg.content_path == Path("~/.idx/content.db").expanduser()


class TestRAGConfig:
    """Tests for RAGConfig model."""

    def test_defaults(self) -> None:
        """RAGConfig defaults match RAGSettings."""
        cfg = RAGConfig()
        assert cfg.chunk_size == 800
        assert cfg.chunk_overlap == 120
        assert cfg.rrf_k == 60
        assert cfg.expansion_enabled is True
        assert cfg.rerank_top_n == 10
        assert cfg.cache_ttl_hours == 168
        assert cfg.vector_top_k == 20
        assert cfg.snippet_max_lines == 10

    def test_custom_values(self) -> None:
        """RAGConfig accepts custom values."""
        cfg = RAGConfig(chunk_size=1000, rrf_k=80, expansion_enabled=False)
        assert cfg.chunk_size == 1000
        assert cfg.rrf_k == 80
        assert cfg.expansion_enabled is False


class TestAppConfig:
    """Tests for AppConfig model."""

    def test_defaults(self) -> None:
        """AppConfig defaults match Settings defaults."""
        cfg = AppConfig()
        assert cfg.log_level == "INFO"
        assert cfg.embedding_model == "BAAI/bge-small-en-v1.5"
        assert cfg.transformers_model == "cross-encoder/ms-marco-MiniLM-L-6-v2"
        assert isinstance(cfg.databases, DatabasesConfig)
        assert isinstance(cfg.rag, RAGConfig)
        assert isinstance(cfg.embedding, EmbeddingConfig)

    def test_from_partial_dict(self) -> None:
        """AppConfig can be constructed from a partial dict (missing keys use defaults)."""
        cfg = AppConfig.model_validate({
            "log_level": "DEBUG",
            "rag": {"chunk_size": 1000},
        })
        assert cfg.log_level == "DEBUG"
        assert cfg.rag.chunk_size == 1000
        # Other RAG fields retain defaults
        assert cfg.rag.rrf_k == 60
        # Top-level defaults retained
        assert cfg.embedding_model == "BAAI/bge-small-en-v1.5"

    def test_to_settings_dict(self) -> None:
        """to_settings_dict produces a dict with all keys."""
        cfg = AppConfig()
        d = cfg.to_settings_dict()
        assert "log_level" in d
        assert "databases" in d
        assert "rag" in d
        assert "embedding" in d
        assert "performance" in d
        assert "qdrant" in d
        assert "langfuse" in d
        # Path fields are converted to strings
        assert isinstance(d["database_path"], str)
        assert isinstance(d["vector_store_path"], str)
        assert isinstance(d["cache_path"], str)

    def test_to_settings_dict_preserves_values(self) -> None:
        """to_settings_dict preserves custom values through round-trip."""
        cfg = AppConfig.model_validate({
            "log_level": "DEBUG",
            "rag": {"chunk_size": 999},
            "performance": {"batch_size": 50},
        })
        d = cfg.to_settings_dict()
        assert d["log_level"] == "DEBUG"
        assert d["rag"]["chunk_size"] == 999
        assert d["performance"]["batch_size"] == 50
