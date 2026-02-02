"""Tests for catalog.ingest.job module."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from catalog.ingest.job import (
    DatasetJob,
    EmbeddingConfig,
    PipelineConfig,
    SourceConfig,
    _import_class,
)


class TestImportClass:
    """Tests for _import_class utility."""

    def test_import_known_class(self):
        """Imports a real class from the project."""
        cls = _import_class("catalog.ingest.job.DatasetJob")
        assert cls is DatasetJob

    def test_import_stdlib_class(self):
        """Imports a stdlib class."""
        cls = _import_class("pathlib.Path")
        assert cls is Path

    def test_invalid_path_raises(self):
        """Dotted path with no module portion raises ImportError."""
        with pytest.raises(ImportError, match="no module"):
            _import_class("NoModule")

    def test_missing_module_raises(self):
        """Non-existent module raises ImportError."""
        with pytest.raises((ImportError, ModuleNotFoundError)):
            _import_class("nonexistent.module.Foo")

    def test_missing_attr_raises(self):
        """Non-existent attribute raises AttributeError."""
        with pytest.raises(AttributeError):
            _import_class("catalog.ingest.job.NonExistentClass")


class TestSourceConfig:
    """Tests for SourceConfig model."""

    def test_minimal(self, tmp_path: Path):
        """Minimal source config with just source_path."""
        cfg = SourceConfig(source_path=tmp_path)
        assert cfg.type == "obsidian"
        assert cfg.source_path == tmp_path
        assert cfg.dataset_name is None
        assert cfg.vault_schema is None
        assert cfg.force is False

    def test_full(self, tmp_path: Path):
        """Full source config with all fields."""
        cfg = SourceConfig(
            type="obsidian",
            source_path=tmp_path,
            dataset_name="my-vault",
            vault_schema="catalog.integrations.obsidian.vault_schema.VaultSchema",
            force=True,
        )
        assert cfg.dataset_name == "my-vault"
        assert cfg.force is True

    def test_resolve_vault_schema_none(self, tmp_path: Path):
        """Resolving vault_schema when not set returns None."""
        cfg = SourceConfig(source_path=tmp_path)
        assert cfg.resolve_vault_schema() is None

    def test_resolve_vault_schema(self, tmp_path: Path):
        """Resolving vault_schema returns the imported class."""
        cfg = SourceConfig(
            source_path=tmp_path,
            vault_schema="pathlib.Path",
        )
        assert cfg.resolve_vault_schema() is Path


class TestEmbeddingConfig:
    """Tests for EmbeddingConfig model."""

    def test_defaults(self):
        """Default embedding config uses mlx."""
        cfg = EmbeddingConfig()
        assert cfg.backend == "mlx"
        assert cfg.model_name == "mlx-community/all-MiniLM-L6-v2-bf16"
        assert cfg.batch_size == 32

    def test_huggingface(self):
        """Can specify huggingface backend."""
        cfg = EmbeddingConfig(
            backend="huggingface",
            model_name="BAAI/bge-small-en-v1.5",
            batch_size=64,
        )
        assert cfg.backend == "huggingface"
        assert cfg.batch_size == 64


class TestPipelineConfig:
    """Tests for PipelineConfig model."""

    def test_defaults(self):
        """Default pipeline config has caching enabled with upserts."""
        cfg = PipelineConfig()
        assert cfg.cache_enabled is True
        assert cfg.docstore_strategy == "upserts"

    def test_disabled_cache(self):
        """Cache can be disabled."""
        cfg = PipelineConfig(cache_enabled=False)
        assert cfg.cache_enabled is False

    def test_strategy_options(self):
        """All strategy options are accepted."""
        for strategy in ("upserts", "duplicates_only", "upserts_and_delete"):
            cfg = PipelineConfig(docstore_strategy=strategy)
            assert cfg.docstore_strategy == strategy


class TestDatasetJob:
    """Tests for DatasetJob model."""

    def test_from_dict_minimal(self, tmp_path: Path):
        """Create DatasetJob from a minimal dict."""
        job = DatasetJob.model_validate({
            "source": {"source_path": str(tmp_path)},
        })
        assert job.source.source_path == tmp_path
        assert job.embedding is None
        assert job.pipeline.cache_enabled is True

    def test_from_dict_full(self, tmp_path: Path):
        """Create DatasetJob from a full dict."""
        job = DatasetJob.model_validate({
            "source": {
                "type": "obsidian",
                "source_path": str(tmp_path),
                "dataset_name": "test-vault",
                "vault_schema": "pathlib.Path",
                "force": True,
            },
            "embedding": {
                "backend": "huggingface",
                "model_name": "BAAI/bge-small-en-v1.5",
                "batch_size": 64,
            },
            "pipeline": {
                "cache_enabled": False,
                "docstore_strategy": "upserts_and_delete",
            },
        })
        assert job.source.dataset_name == "test-vault"
        assert job.source.force is True
        assert job.embedding.backend == "huggingface"
        assert job.pipeline.cache_enabled is False
        assert job.pipeline.docstore_strategy == "upserts_and_delete"

    def test_to_ingest_config(self, tmp_path: Path):
        """to_ingest_config produces an IngestObsidianConfig."""
        vault_dir = tmp_path / "MyVault"
        vault_dir.mkdir()
        (vault_dir / ".obsidian").mkdir()

        job = DatasetJob.model_validate({
            "source": {
                "source_path": str(vault_dir),
                "dataset_name": "my-vault",
            },
        })
        config = job.to_ingest_config()

        from catalog.integrations.obsidian import IngestObsidianConfig
        assert isinstance(config, IngestObsidianConfig)
        assert config.source_path == vault_dir
        assert config.dataset_name == "my-vault"
        assert config.force is False
        assert config.vault_schema is None

    def test_to_ingest_config_derives_name(self, tmp_path: Path):
        """dataset_name is derived from source_path folder name."""
        vault_dir = tmp_path / "MyVault"
        vault_dir.mkdir()
        (vault_dir / ".obsidian").mkdir()

        job = DatasetJob.model_validate({
            "source": {"source_path": str(vault_dir)},
        })
        config = job.to_ingest_config()
        assert config.dataset_name == "MyVault"

    def test_to_ingest_config_with_vault_schema(self, tmp_path: Path):
        """vault_schema dotted path is resolved to a class."""
        vault_dir = tmp_path / "MyVault"
        vault_dir.mkdir()
        (vault_dir / ".obsidian").mkdir()

        job = DatasetJob.model_validate({
            "source": {
                "source_path": str(vault_dir),
                "vault_schema": "pathlib.Path",
            },
        })
        config = job.to_ingest_config()
        assert config.vault_schema is Path

    def test_create_embed_model_falls_back_to_app_settings(self, tmp_path: Path):
        """create_embed_model delegates to get_embed_model() when embedding is omitted."""
        job = DatasetJob.model_validate({
            "source": {"source_path": str(tmp_path)},
        })
        assert job.embedding is None
        with patch("catalog.embedding.get_embed_model") as mock_get:
            mock_instance = MagicMock()
            mock_get.return_value = mock_instance
            result = job.create_embed_model()
            mock_get.assert_called_once()
            assert result is mock_instance

    def test_create_embed_model_mlx(self, tmp_path: Path):
        """create_embed_model with mlx backend returns MLXEmbedding."""
        job = DatasetJob.model_validate({
            "source": {"source_path": str(tmp_path)},
            "embedding": {"backend": "mlx", "model_name": "test-model"},
        })
        with patch("catalog.embedding.mlx.MLXEmbedding") as MockMLX:
            mock_instance = MagicMock()
            MockMLX.return_value = mock_instance
            result = job.create_embed_model()
            MockMLX.assert_called_once_with(model_name="test-model", embed_batch_size=32)
            assert result is mock_instance

    def test_create_embed_model_huggingface(self, tmp_path: Path):
        """create_embed_model with huggingface backend returns HuggingFaceEmbedding."""
        job = DatasetJob.model_validate({
            "source": {"source_path": str(tmp_path)},
            "embedding": {"backend": "huggingface", "model_name": "test-model", "batch_size": 16},
        })
        with patch("llama_index.embeddings.huggingface.HuggingFaceEmbedding") as MockHF:
            mock_instance = MagicMock()
            MockHF.return_value = mock_instance
            result = job.create_embed_model()
            MockHF.assert_called_once_with(model_name="test-model", embed_batch_size=16)
            assert result is mock_instance


class TestDatasetJobFromYaml:
    """Tests for DatasetJob.from_yaml()."""

    def test_load_minimal_yaml(self, tmp_path: Path):
        """Load a minimal YAML config."""
        yaml_content = f"""\
source:
  source_path: {tmp_path}
"""
        config_file = tmp_path / "job.yaml"
        config_file.write_text(yaml_content)

        job = DatasetJob.from_yaml(config_file)
        assert job.source.source_path == tmp_path
        assert job.embedding is None

    def test_load_full_yaml(self, tmp_path: Path):
        """Load a full YAML config."""
        yaml_content = f"""\
source:
  type: obsidian
  source_path: {tmp_path}
  dataset_name: test-vault
  force: true

embedding:
  backend: huggingface
  model_name: BAAI/bge-small-en-v1.5
  batch_size: 64

pipeline:
  cache_enabled: false
  docstore_strategy: upserts_and_delete
"""
        config_file = tmp_path / "job.yaml"
        config_file.write_text(yaml_content)

        job = DatasetJob.from_yaml(config_file)
        assert job.source.dataset_name == "test-vault"
        assert job.source.force is True
        assert job.embedding.backend == "huggingface"
        assert job.embedding.batch_size == 64
        assert job.pipeline.cache_enabled is False

    def test_missing_file_raises(self, tmp_path: Path):
        """Missing YAML file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            DatasetJob.from_yaml(tmp_path / "nonexistent.yaml")

    def test_hydra_variable_interpolation(self, tmp_path: Path):
        """Hydra variable interpolation works."""
        yaml_content = f"""\
source:
  type: obsidian
  source_path: {tmp_path}
  dataset_name: ${{source.type}}-vault

embedding:
  backend: mlx
"""
        config_file = tmp_path / "job.yaml"
        config_file.write_text(yaml_content)

        job = DatasetJob.from_yaml(config_file)
        assert job.source.dataset_name == "obsidian-vault"


class TestPipelineConfigToStrategy:
    """Tests for PipelineConfig docstore_strategy mapping."""

    def test_strategy_mapping(self):
        """docstore_strategy strings map to DocstoreStrategy enums."""
        from llama_index.core.ingestion import DocstoreStrategy

        strategy_map = {
            "upserts": DocstoreStrategy.UPSERTS,
            "duplicates_only": DocstoreStrategy.DUPLICATES_ONLY,
            "upserts_and_delete": DocstoreStrategy.UPSERTS_AND_DELETE,
        }

        for name, expected in strategy_map.items():
            cfg = PipelineConfig(docstore_strategy=name)
            assert strategy_map[cfg.docstore_strategy] == expected
