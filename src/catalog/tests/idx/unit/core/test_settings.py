"""Tests for catalog.core.settings, specifically RAGv2Settings."""

import os
from unittest import mock

import pytest

from catalog.core.settings import RAGv2Settings, Settings, get_settings


class TestRAGv2Settings:
    """Tests for RAGv2Settings configuration class."""

    def test_default_values(self) -> None:
        """RAGv2Settings loads with default values matching QMD system."""
        settings = RAGv2Settings()

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
        """RAGv2Settings can be overridden via environment variables."""
        env_vars = {
            "IDX_RAG_V2__CHUNK_SIZE": "1000",
            "IDX_RAG_V2__CHUNK_OVERLAP": "150",
            "IDX_RAG_V2__RRF_K": "80",
            "IDX_RAG_V2__EXPANSION_ENABLED": "false",
            "IDX_RAG_V2__RERANK_TOP_N": "5",
        }

        with mock.patch.dict(os.environ, env_vars, clear=False):
            settings = RAGv2Settings()

            assert settings.chunk_size == 1000
            assert settings.chunk_overlap == 150
            assert settings.rrf_k == 80
            assert settings.expansion_enabled is False
            assert settings.rerank_top_n == 5

    def test_validation_constraints(self) -> None:
        """RAGv2Settings validates field constraints."""
        # chunk_size must be >= 100
        with pytest.raises(ValueError):
            RAGv2Settings(chunk_size=50)

        # chunk_overlap must be >= 0
        with pytest.raises(ValueError):
            RAGv2Settings(chunk_overlap=-1)

        # expansion_max_lex must be <= 5
        with pytest.raises(ValueError):
            RAGv2Settings(expansion_max_lex=10)

        # rrf_k must be >= 1
        with pytest.raises(ValueError):
            RAGv2Settings(rrf_k=0)

    def test_nested_in_settings(self) -> None:
        """RAGv2Settings is accessible via Settings.rag_v2."""
        settings = Settings()
        assert hasattr(settings, "rag_v2")
        assert isinstance(settings.rag_v2, RAGv2Settings)
        assert settings.rag_v2.chunk_size == 800

    def test_nested_environment_override(self) -> None:
        """RAGv2Settings can be overridden via nested env vars in main Settings."""
        env_vars = {
            "IDX_RAG_V2__CHUNK_SIZE": "900",
            "IDX_RAG_V2__CACHE_TTL_HOURS": "48",
        }

        with mock.patch.dict(os.environ, env_vars, clear=False):
            settings = Settings()
            assert settings.rag_v2.chunk_size == 900
            assert settings.rag_v2.cache_ttl_hours == 48


class TestGetSettings:
    """Tests for get_settings() function."""

    def test_get_settings_returns_settings_instance(self) -> None:
        """get_settings() returns a Settings instance."""
        # Clear cache to ensure fresh settings
        get_settings.cache_clear()
        settings = get_settings()
        assert isinstance(settings, Settings)
        assert hasattr(settings, "rag_v2")

    def test_get_settings_caches_result(self) -> None:
        """get_settings() returns the same cached instance."""
        get_settings.cache_clear()
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2
