"""Tests for ObsidianVaultSource if_modified_since filtering."""

import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from catalog.integrations.obsidian.source import ObsidianVaultSource, SourceObsidianConfig
from catalog.ingest.sources import create_ingest_config


def _make_vault(tmp_path: Path) -> Path:
    """Create a minimal Obsidian vault directory."""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".obsidian").mkdir()
    return vault


class TestObsidianVaultSourceModifiedSince:
    """Tests for if_modified_since filtering on ObsidianVaultSource."""

    def test_no_filter_loads_all_files(self, tmp_path: Path):
        """Without if_modified_since, all markdown files are available."""
        vault = _make_vault(tmp_path)
        (vault / "a.md").write_text("# A")
        (vault / "b.md").write_text("# B")

        source = ObsidianVaultSource(vault)
        # Reader should have discovered both files
        assert len(source.reader.input_files) == 2

    def test_filter_excludes_old_files(self, tmp_path: Path):
        """Files older than if_modified_since are excluded."""
        vault = _make_vault(tmp_path)

        old_file = vault / "old.md"
        old_file.write_text("# Old")
        # Backdate the mtime
        old_mtime = time.time() - 3600
        os.utime(old_file, (old_mtime, old_mtime))

        new_file = vault / "new.md"
        new_file.write_text("# New")

        cutoff = datetime.fromtimestamp(time.time() - 60, tz=timezone.utc)
        source = ObsidianVaultSource(vault, if_modified_since=cutoff)

        input_names = {p.name for p in source.reader.input_files}
        assert "new.md" in input_names
        assert "old.md" not in input_names

    def test_filter_includes_exact_boundary(self, tmp_path: Path):
        """A file whose mtime equals the cutoff timestamp is included."""
        vault = _make_vault(tmp_path)

        f = vault / "exact.md"
        f.write_text("# Exact")
        # Set a known integer mtime to avoid float precision issues
        known_ts = int(time.time()) - 100
        os.utime(f, (known_ts, known_ts))

        cutoff = datetime.fromtimestamp(known_ts, tz=timezone.utc)
        source = ObsidianVaultSource(vault, if_modified_since=cutoff)

        input_names = {p.name for p in source.reader.input_files}
        assert "exact.md" in input_names

    def test_filter_returns_empty_when_all_old(self, tmp_path: Path):
        """If all files are older than the cutoff, input_files is empty."""
        vault = _make_vault(tmp_path)
        f = vault / "ancient.md"
        f.write_text("# Ancient")
        old_mtime = time.time() - 7200
        os.utime(f, (old_mtime, old_mtime))

        cutoff = datetime.fromtimestamp(time.time(), tz=timezone.utc)
        source = ObsidianVaultSource(vault, if_modified_since=cutoff)

        assert len(source.reader.input_files) == 0

    def test_filter_recurses_subdirectories(self, tmp_path: Path):
        """Files in subdirectories are also filtered by mtime."""
        vault = _make_vault(tmp_path)
        subdir = vault / "notes"
        subdir.mkdir()

        old_file = subdir / "old.md"
        old_file.write_text("# Old nested")
        old_mtime = time.time() - 3600
        os.utime(old_file, (old_mtime, old_mtime))

        new_file = subdir / "new.md"
        new_file.write_text("# New nested")

        cutoff = datetime.fromtimestamp(time.time() - 60, tz=timezone.utc)
        source = ObsidianVaultSource(vault, if_modified_since=cutoff)

        input_names = {p.name for p in source.reader.input_files}
        assert "new.md" in input_names
        assert "old.md" not in input_names

    def test_create_ingest_config_passes_if_modified_since(self, tmp_path: Path):
        """if_modified_since flows from SourceConfig through the obsidian factory."""
        from catalog.ingest.job import SourceConfig

        vault = _make_vault(tmp_path)
        ts = datetime(2025, 6, 1, tzinfo=timezone.utc)
        source_config = SourceConfig(
            type="obsidian",
            source_path=vault,
            dataset_name="test-vault",
            if_modified_since=ts,
        )
        config = create_ingest_config(source_config)
        assert isinstance(config, SourceObsidianConfig)
        assert config.if_modified_since == ts
