"""Tests for Heptabase source registration and creation."""

import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from catalog.integrations.heptabase.source import SourceHeptabaseConfig
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
        assert isinstance(config, SourceHeptabaseConfig)
        assert config.type_name == "heptabase"
        assert config.dataset_name == "test-export"

    def test_create_source_dispatches_to_heptabase(self, tmp_path: Path):
        """create_source with IngestHeptabaseConfig returns HeptabaseVaultSource."""
        (tmp_path / "note.md").write_text("# Hello")
        config = SourceHeptabaseConfig(
            source_path=tmp_path,
            dataset_name="test-export",
        )
        source = create_source(config)
        assert isinstance(source, HeptabaseVaultSource)
        assert source.type_name == "heptabase"

    def test_create_ingest_config_with_ontology_spec(self, tmp_path: Path):
        """ontology_spec option resolves to the class."""
        from catalog.ingest.job import SourceConfig

        (tmp_path / "note.md").write_text("# Hello")
        source_config = SourceConfig(
            type="heptabase",
            source_path=tmp_path,
            dataset_name="test-export",
            options={
                "ontology_spec": "catalog.integrations.heptabase.ontology_spec.HeptabaseVaultSchema",
            },
        )
        config = create_ingest_config(source_config)
        assert isinstance(config, SourceHeptabaseConfig)

        from catalog.integrations.heptabase.ontology_spec import HeptabaseVaultSchema
        assert config.ontology_spec is HeptabaseVaultSchema


class TestHeptabaseVaultSourceModifiedSince:
    """Tests for if_modified_since filtering on HeptabaseVaultSource."""

    def test_no_filter_loads_all_files(self, tmp_path: Path):
        """Without if_modified_since, all markdown files are available."""
        (tmp_path / "a.md").write_text("# A")
        (tmp_path / "b.md").write_text("# B")

        source = HeptabaseVaultSource(tmp_path)
        assert len(source.reader.input_files) == 2

    def test_filter_excludes_old_files(self, tmp_path: Path):
        """Files older than if_modified_since are excluded."""
        old_file = tmp_path / "old.md"
        old_file.write_text("# Old")
        old_mtime = time.time() - 3600
        os.utime(old_file, (old_mtime, old_mtime))

        new_file = tmp_path / "new.md"
        new_file.write_text("# New")

        cutoff = datetime.fromtimestamp(time.time() - 60, tz=timezone.utc)
        source = HeptabaseVaultSource(tmp_path, if_modified_since=cutoff)

        input_names = {p.name for p in source.reader.input_files}
        assert "new.md" in input_names
        assert "old.md" not in input_names

    def test_filter_returns_empty_when_all_old(self, tmp_path: Path):
        """If all files are older than the cutoff, input_files is empty."""
        f = tmp_path / "ancient.md"
        f.write_text("# Ancient")
        old_mtime = time.time() - 7200
        os.utime(f, (old_mtime, old_mtime))

        cutoff = datetime.fromtimestamp(time.time(), tz=timezone.utc)
        source = HeptabaseVaultSource(tmp_path, if_modified_since=cutoff)

        assert len(source.reader.input_files) == 0

    def test_create_ingest_config_passes_if_modified_since(self, tmp_path: Path):
        """if_modified_since flows from SourceConfig through factory."""
        from catalog.ingest.job import SourceConfig

        (tmp_path / "note.md").write_text("# Hello")
        ts = datetime(2025, 6, 1, tzinfo=timezone.utc)
        source_config = SourceConfig(
            type="heptabase",
            source_path=tmp_path,
            dataset_name="test-export",
            if_modified_since=ts,
        )
        config = create_ingest_config(source_config)
        assert isinstance(config, SourceHeptabaseConfig)
        assert config.if_modified_since == ts
