"""Tests for Heptabase ingestion config."""

from pathlib import Path

import pytest

from catalog.integrations.heptabase.source import SourceHeptabaseConfig


class TestIngestHeptabaseConfig:
    """Tests for IngestHeptabaseConfig validation."""

    def test_valid_directory(self, tmp_path: Path):
        """Accepts a valid directory."""
        (tmp_path / "note.md").write_text("# Hello")
        config = SourceHeptabaseConfig(
            source_path=tmp_path,
            dataset_name="test",
        )
        assert config.type_name == "heptabase"
        assert config.source_path == tmp_path

    def test_rejects_nonexistent_path(self, tmp_path: Path):
        """Rejects a path that does not exist."""
        bad_path = tmp_path / "nonexistent"
        with pytest.raises(ValueError, match="does not exist"):
            SourceHeptabaseConfig(
                source_path=bad_path,
                dataset_name="test",
            )

    def test_rejects_non_directory(self, tmp_path: Path):
        """Rejects a path that is not a directory."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("not a directory")
        with pytest.raises(ValueError, match="not a directory"):
            SourceHeptabaseConfig(
                source_path=file_path,
                dataset_name="test",
            )

    def test_auto_derives_dataset_name(self, tmp_path: Path):
        """Auto-derives dataset_name from source_path.name."""
        export_dir = tmp_path / "my-heptabase-export"
        export_dir.mkdir()
        (export_dir / "note.md").write_text("# Hello")
        config = SourceHeptabaseConfig(source_path=export_dir)
        assert config.dataset_name == "my-heptabase-export"

    def test_vault_schema_default_none(self, tmp_path: Path):
        """vault_schema defaults to None."""
        (tmp_path / "note.md").write_text("# Hello")
        config = SourceHeptabaseConfig(
            source_path=tmp_path,
            dataset_name="test",
        )
        assert config.vault_schema is None
