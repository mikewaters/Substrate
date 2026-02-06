"""Tests for Heptabase source registration and creation."""

from pathlib import Path

import pytest

from catalog.integrations.heptabase.schemas import IngestHeptabaseConfig
from catalog.integrations.heptabase.reader import HeptabaseVaultSource
from catalog.ingest.sources import create_ingest_config, create_source


class TestHeptabaseSourceRegistration:
    """Tests for Heptabase source factory registration."""

    def test_create_ingest_config_heptabase(self, tmp_path: Path):
        """create_ingest_config dispatches 'heptabase' type correctly."""
        from catalog.ingest.job import SourceConfig

        (tmp_path / "note.md").write_text("# Hello")
        source_config = SourceConfig(
            type="heptabase",
            source_path=tmp_path,
            dataset_name="test-export",
        )
        config = create_ingest_config(source_config)
        assert isinstance(config, IngestHeptabaseConfig)
        assert config.type_name == "heptabase"
        assert config.dataset_name == "test-export"

    def test_create_source_dispatches_to_heptabase(self, tmp_path: Path):
        """create_source with IngestHeptabaseConfig returns HeptabaseVaultSource."""
        (tmp_path / "note.md").write_text("# Hello")
        config = IngestHeptabaseConfig(
            source_path=tmp_path,
            dataset_name="test-export",
        )
        source = create_source(config)
        assert isinstance(source, HeptabaseVaultSource)
        assert source.type_name == "heptabase"

    def test_create_ingest_config_with_vault_schema(self, tmp_path: Path):
        """vault_schema option resolves to the class."""
        from catalog.ingest.job import SourceConfig

        (tmp_path / "note.md").write_text("# Hello")
        source_config = SourceConfig(
            type="heptabase",
            source_path=tmp_path,
            dataset_name="test-export",
            options={
                "vault_schema": "catalog.integrations.heptabase.vault_schema.HeptabaseVaultSchema",
            },
        )
        config = create_ingest_config(source_config)
        assert isinstance(config, IngestHeptabaseConfig)

        from catalog.integrations.heptabase.vault_schema import HeptabaseVaultSchema
        assert config.vault_schema is HeptabaseVaultSchema
