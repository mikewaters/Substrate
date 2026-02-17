"""Tests for catalog.config.loader module."""

import os
from pathlib import Path
from unittest import mock

import pytest
from catalog.config.loader import load_app_config, load_app_config_from_file
from catalog.core.settings import Settings


class TestLoadAppConfig:
    """Tests for load_app_config function."""

    def test_loads_default_config(self) -> None:
        """Loading default config produces a valid Settings instance."""
        settings = load_app_config()
        assert isinstance(settings, Settings)
        assert settings.log_level == "INFO"
        assert settings.rag.chunk_size == 800
        assert settings.embedding.backend == "mlx"

    def test_hydra_overrides(self) -> None:
        """Hydra overrides modify specific settings."""
        settings = load_app_config(overrides=["log_level=DEBUG"])
        assert settings.log_level == "DEBUG"
        # Other values unchanged
        assert settings.rag.chunk_size == 800

    def test_nested_hydra_overrides(self) -> None:
        """Hydra overrides work on nested fields."""
        settings = load_app_config(overrides=[
            "rag.chunk_size=1000",
            "performance.batch_size=50",
        ])
        assert settings.rag.chunk_size == 1000
        assert settings.performance.batch_size == 50

    def test_env_vars_override_yaml(self) -> None:
        """Environment variables take priority over YAML config values."""
        env = {"IDX_LOG_LEVEL": "ERROR"}
        with mock.patch.dict(os.environ, env, clear=False):
            settings = load_app_config()
            assert settings.log_level == "ERROR"

    def test_nested_env_vars_override_yaml(self) -> None:
        """Nested environment variables override YAML nested values."""
        env = {"IDX_RAG__CHUNK_SIZE": "999"}
        with mock.patch.dict(os.environ, env, clear=False):
            settings = load_app_config()
            assert settings.rag.chunk_size == 999

    def test_missing_config_dir_raises(self, tmp_path: Path) -> None:
        """Non-existent config directory raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Config directory not found"):
            load_app_config(config_dir=tmp_path / "nonexistent")

    def test_custom_config_dir(self, tmp_path: Path) -> None:
        """Loading from a custom config directory works."""
        yaml_content = """\
log_level: WARNING
rag:
  chunk_size: 500
"""
        config_file = tmp_path / "custom.yaml"
        config_file.write_text(yaml_content)

        settings = load_app_config(config_name="custom", config_dir=tmp_path)
        assert settings.log_level == "WARNING"
        assert settings.rag.chunk_size == 500

    def test_multiple_calls_produce_independent_settings(self) -> None:
        """Each call to load_app_config produces an independent Settings."""
        s1 = load_app_config()
        s2 = load_app_config(overrides=["log_level=DEBUG"])
        assert s1.log_level == "INFO"
        assert s2.log_level == "DEBUG"


class TestLoadAppConfigFromFile:
    """Tests for load_app_config_from_file function."""

    def test_loads_from_file_path(self, tmp_path: Path) -> None:
        """Loads settings from an explicit YAML file path."""
        yaml_content = """\
log_level: DEBUG
performance:
  batch_size: 25
  concurrency: 8
"""
        config_file = tmp_path / "myconfig.yaml"
        config_file.write_text(yaml_content)

        settings = load_app_config_from_file(config_file)
        assert settings.log_level == "DEBUG"
        assert settings.performance.batch_size == 25
        assert settings.performance.concurrency == 8

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        """Missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_app_config_from_file(tmp_path / "nope.yaml")

    def test_partial_config_uses_defaults(self, tmp_path: Path) -> None:
        """A partial YAML file fills in missing fields with defaults."""
        yaml_content = """\
log_level: ERROR
"""
        config_file = tmp_path / "partial.yaml"
        config_file.write_text(yaml_content)

        settings = load_app_config_from_file(config_file)
        assert settings.log_level == "ERROR"
        # Everything else uses Pydantic defaults
        assert settings.rag.chunk_size == 800
        assert settings.embedding.backend == "mlx"
        assert settings.performance.batch_size == 100

    def test_with_overrides(self, tmp_path: Path) -> None:
        """Hydra overrides apply on top of the file."""
        yaml_content = """\
log_level: INFO
rag:
  chunk_size: 600
"""
        config_file = tmp_path / "base.yaml"
        config_file.write_text(yaml_content)

        settings = load_app_config_from_file(
            config_file,
            overrides=["rag.chunk_size=1200"],
        )
        assert settings.rag.chunk_size == 1200

    def test_hydra_interpolation(self, tmp_path: Path) -> None:
        """Hydra variable interpolation works in file configs."""
        yaml_content = """\
log_level: DEBUG
embedding_model: BAAI/bge-small-en-v1.5
transformers_model: cross-encoder/${embedding_model}
"""
        config_file = tmp_path / "interp.yaml"
        config_file.write_text(yaml_content)

        settings = load_app_config_from_file(config_file)
        assert settings.transformers_model == "cross-encoder/BAAI/bge-small-en-v1.5"


class TestGetSettingsWithConfigPath:
    """Tests for get_settings() with CATALOG_CONFIG_PATH."""

    def test_config_path_env_loads_yaml(self, tmp_path: Path) -> None:
        """Setting CATALOG_CONFIG_PATH causes get_settings to load YAML."""
        from catalog.core.settings import get_settings

        yaml_content = """\
log_level: WARNING
rag:
  chunk_size: 750
"""
        config_file = tmp_path / "app.yaml"
        config_file.write_text(yaml_content)

        env = {"CATALOG_CONFIG_PATH": str(config_file)}
        with mock.patch.dict(os.environ, env, clear=False):
            get_settings.cache_clear()
            try:
                settings = get_settings()
                assert settings.log_level == "WARNING"
                assert settings.rag.chunk_size == 750
            finally:
                get_settings.cache_clear()

    def test_without_config_path_uses_env_vars(self) -> None:
        """Without CATALOG_CONFIG_PATH, get_settings uses env vars only."""
        from catalog.core.settings import get_settings

        # Ensure no CATALOG_CONFIG_PATH is set
        env = {k: v for k, v in os.environ.items() if k != "CATALOG_CONFIG_PATH"}
        with mock.patch.dict(os.environ, env, clear=True):
            get_settings.cache_clear()
            try:
                settings = get_settings()
                assert isinstance(settings, Settings)
                assert settings.log_level == "INFO"
            finally:
                get_settings.cache_clear()
