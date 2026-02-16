"""Tests for catalog.core.settings, specifically RAGSettings."""

import os
from pathlib import Path
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
            "SUBSTRATE_RAG__CHUNK_SIZE": "1000",
            "SUBSTRATE_RAG__CHUNK_OVERLAP": "150",
            "SUBSTRATE_RAG__RRF_K": "80",
            "SUBSTRATE_RAG__EXPANSION_ENABLED": "false",
            "SUBSTRATE_RAG__RERANK_TOP_N": "5",
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
            "SUBSTRATE_RAG__CHUNK_SIZE": "900",
            "SUBSTRATE_RAG__CACHE_TTL_HOURS": "48",
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

    def test_defaults_to_zvec_backend(self) -> None:
        """Vector DB defaults to Zvec as the primary backend."""
        settings = Settings()

        assert settings.vector_db.backend == "zvec"

    def test_allows_qdrant_backend_env_override(self) -> None:
        """Vector backend can be set to Qdrant via nested environment variables."""
        env_vars = {
            "SUBSTRATE_VECTOR_DB__BACKEND": "qdrant",
        }

        with mock.patch.dict(os.environ, env_vars, clear=False):
            settings = Settings()

            assert settings.vector_db.backend == "qdrant"

    def test_allows_zvec_index_path_env_override(self) -> None:
        """Zvec index path can be configured via environment variables."""
        env_vars = {
            "SUBSTRATE_ZVEC__INDEX_PATH": "/tmp/zvec-index.json",
        }

        with mock.patch.dict(os.environ, env_vars, clear=False):
            settings = Settings()

            assert settings.vector_db.backend == "zvec"
            assert settings.zvec.index_path is not None
            assert settings.zvec.index_path.resolve() == Path("/tmp/zvec-index.json").resolve()


class TestConfigRoot:
    """Tests for config_root and environment-based path derivation."""

    def test_config_root_defaults_by_environment(self) -> None:
        """Config root is chosen from environment when SUBSTRATE_CONFIG_ROOT unset."""
        saved = os.environ.pop("SUBSTRATE_CONFIG_ROOT", None)
        try:
            with mock.patch.dict(os.environ, {"SUBSTRATE_ENVIRONMENT": "prod"}, clear=False):
                settings = Settings()
                assert settings.config_root is not None
                assert settings.config_root.is_absolute()
                assert "substrate" in str(settings.config_root).lower()
        finally:
            if saved is not None:
                os.environ["SUBSTRATE_CONFIG_ROOT"] = saved

    def test_config_root_override_derives_all_paths(self, tmp_path: Path) -> None:
        """When SUBSTRATE_CONFIG_ROOT is set, all paths derive from it."""
        root = tmp_path / "idx-root"
        env_vars = {
            "SUBSTRATE_CONFIG_ROOT": str(root),
            "SUBSTRATE_ENVIRONMENT": "dev",
        }
        with mock.patch.dict(os.environ, env_vars, clear=False):
            get_settings.cache_clear()
            try:
                settings = get_settings()
                assert settings.config_root is not None
                assert settings.config_root.resolve() == root.resolve()
                assert settings.databases.catalog_path == root / "catalog.db"
                assert settings.databases.content_path == root / "content.db"
                assert settings.vector_store_path == root / "vector_store"
                assert settings.cache_path == root / "cache"
                assert settings.job_config_path == root / "jobs"
                assert settings.env_config_path == root / "environments"
                assert settings.zvec.index_path == root / "zvec" / "index.json"
            finally:
                get_settings.cache_clear()


class TestEnvironmentTomlDefaults:
    """Tests for environment-named TOML from catalog.core package (env vars still take precedence)."""

    def test_toml_overrides_defaults_when_present(self) -> None:
        """Bundled catalog.core/{environment}.toml overrides Pydantic defaults."""
        with mock.patch.dict(os.environ, {"SUBSTRATE_ENVIRONMENT": "dev"}, clear=False):
            get_settings.cache_clear()
            try:
                settings = get_settings()
                assert settings.log_level == "DEBUG"
            finally:
                get_settings.cache_clear()

    def test_env_var_overrides_toml(self) -> None:
        """Environment variables take precedence over bundled environment TOML."""
        env_vars = {
            "SUBSTRATE_ENVIRONMENT": "dev",
            "SUBSTRATE_LOG_LEVEL": "WARNING",
        }
        with mock.patch.dict(os.environ, env_vars, clear=False):
            get_settings.cache_clear()
            try:
                settings = get_settings()
                assert settings.log_level == "WARNING"
            finally:
                get_settings.cache_clear()

    def test_nested_toml_section_overrides_defaults(self) -> None:
        """Nested [rag] (and similar) sections in bundled TOML override nested defaults."""
        with mock.patch.dict(os.environ, {"SUBSTRATE_ENVIRONMENT": "dev"}, clear=False):
            get_settings.cache_clear()
            try:
                settings = get_settings()
                assert settings.rag.chunk_size == 1000
                assert settings.rag.rrf_k == 80
            finally:
                get_settings.cache_clear()
