"""Tests for catalog.core.settings, specifically RAGSettings."""

import os
from unittest import mock

import pytest

from catalog.core.settings import RAGSettings, Settings, get_settings


class TestRAGSettings:
    """Tests for RAGSettings configuration class."""

    def test_default_values(self) -> None:
        """RAGSettings loads with default values matching QMD system."""
        settings = RAGSettings()

        # Chunking defaults
        assert settings.chunk_size == 800
        assert settings.chunk_overlap == 120
        assert settings.chunk_fallback_enabled is True
        assert settings.chunk_chars_per_token == 4

        # Embedding defaults
        assert settings.embed_batch_size == 32
        assert settings.embed_fallback_enabled is True
        assert settings.embed_prefix_query == "task: search result | query: "
        assert settings.embed_prefix_doc == "title: {title} | text: "

        # Query expansion defaults
        assert settings.expansion_enabled is True
        assert settings.expansion_max_lex == 3
        assert settings.expansion_max_vec == 3
        assert settings.expansion_include_hyde is True

        # RRF fusion defaults
        assert settings.rrf_k == 60
        assert settings.rrf_original_weight == 2.0
        assert settings.rrf_expansion_weight == 1.0
        assert settings.rrf_rank1_bonus == 0.05
        assert settings.rrf_rank23_bonus == 0.02

        # Reranking defaults
        assert settings.rerank_top_n == 10
        assert settings.rerank_candidates == 40
        assert settings.rerank_cache_enabled is True

        # Caching defaults
        assert settings.cache_ttl_hours == 168  # 1 week

        # Retrieval defaults
        assert settings.vector_top_k == 20
        assert settings.fts_top_k == 20
        assert settings.fusion_top_k == 30

        # Snippet defaults
        assert settings.snippet_max_lines == 10
        assert settings.snippet_context_lines == 2

    def test_environment_variable_override(self) -> None:
        """RAGSettings can be overridden via environment variables."""
        env_vars = {
            "IDX_RAG__CHUNK_SIZE": "1000",
            "IDX_RAG__CHUNK_OVERLAP": "150",
            "IDX_RAG__RRF_K": "80",
            "IDX_RAG__EXPANSION_ENABLED": "false",
            "IDX_RAG__RERANK_TOP_N": "5",
        }

        with mock.patch.dict(os.environ, env_vars, clear=False):
            settings = RAGSettings()

            assert settings.chunk_size == 1000
            assert settings.chunk_overlap == 150
            assert settings.rrf_k == 80
            assert settings.expansion_enabled is False
            assert settings.rerank_top_n == 5

    def test_validation_constraints(self) -> None:
        """RAGSettings validates field constraints."""
        # chunk_size must be >= 100
        with pytest.raises(ValueError):
            RAGSettings(chunk_size=50)

        # chunk_overlap must be >= 0
        with pytest.raises(ValueError):
            RAGSettings(chunk_overlap=-1)

        # expansion_max_lex must be <= 5
        with pytest.raises(ValueError):
            RAGSettings(expansion_max_lex=10)

        # rrf_k must be >= 1
        with pytest.raises(ValueError):
            RAGSettings(rrf_k=0)

    def test_nested_in_settings(self) -> None:
        """RAGSettings is accessible via Settings.rag."""
        settings = Settings()
        assert hasattr(settings, "rag")
        assert isinstance(settings.rag, RAGSettings)
        assert settings.rag.chunk_size == 800

    def test_nested_environment_override(self) -> None:
        """RAGSettings can be overridden via nested env vars in main Settings."""
        env_vars = {
            "IDX_RAG__CHUNK_SIZE": "900",
            "IDX_RAG__CACHE_TTL_HOURS": "48",
        }

        with mock.patch.dict(os.environ, env_vars, clear=False):
            settings = Settings()
            assert settings.rag.chunk_size == 900
            assert settings.rag.cache_ttl_hours == 48


class TestGetSettings:
    """Tests for get_settings() function."""

    def test_get_settings_returns_settings_instance(self) -> None:
        """get_settings() returns a Settings instance."""
        # Clear cache to ensure fresh settings
        get_settings.cache_clear()
        settings = get_settings()
        assert isinstance(settings, Settings)
        assert hasattr(settings, "rag")

    def test_get_settings_caches_result(self) -> None:
        """get_settings() returns the same cached instance."""
        get_settings.cache_clear()
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2


class TestVectorDBSettings:
    """Tests for vector backend selection settings."""

    def test_defaults_to_qdrant_backend(self) -> None:
        """Vector DB defaults keep Qdrant as runtime backend."""
        settings = Settings()

        assert settings.vector_db.backend == "qdrant"
        assert settings.vector_db.enable_experimental_zvec is False

    def test_allows_zvec_backend_env_override(self) -> None:
        """Vector backend can be set to Zvec via nested environment variables."""
        env_vars = {
            "IDX_VECTOR_DB__BACKEND": "zvec",
            "IDX_VECTOR_DB__ENABLE_EXPERIMENTAL_ZVEC": "true",
            "IDX_ZVEC__ENDPOINT": "http://zvec.internal:8000",
        }

        with mock.patch.dict(os.environ, env_vars, clear=False):
            settings = Settings()

            assert settings.vector_db.backend == "zvec"
            assert settings.vector_db.enable_experimental_zvec is True
            assert settings.zvec.endpoint == "http://zvec.internal:8000"
