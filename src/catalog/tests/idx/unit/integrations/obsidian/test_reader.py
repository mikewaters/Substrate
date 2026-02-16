"""Tests for ObsidianMarkdownReader, including duplicate-title normalization."""

from pathlib import Path

import pytest

from catalog.integrations.obsidian.reader import ObsidianMarkdownReader


class TestGetEffectiveTitle:
    """Tests for _get_effective_title derivation from metadata."""

    def test_from_note_name(self) -> None:
        reader = ObsidianMarkdownReader(split_on_headers=False)
        meta = {"note_name": "My Note", "file_name": "My Note.md"}
        assert reader._get_effective_title(meta) == "My Note"

    def test_from_file_name_stem(self) -> None:
        reader = ObsidianMarkdownReader(split_on_headers=False)
        meta = {"file_name": "Some File.md"}
        assert reader._get_effective_title(meta) == "Some File"

    def test_frontmatter_title_overrides_note_name(self) -> None:
        reader = ObsidianMarkdownReader(split_on_headers=False)
        meta = {
            "frontmatter": {"title": "Frontmatter Title"},
            "note_name": "File Name",
            "file_name": "File Name.md",
        }
        assert reader._get_effective_title(meta) == "Frontmatter Title"

    def test_first_alias_when_no_title(self) -> None:
        reader = ObsidianMarkdownReader(split_on_headers=False)
        meta = {"frontmatter": {"aliases": ["Alias One", "Alias Two"]}, "file_name": "x.md"}
        assert reader._get_effective_title(meta) == "Alias One"

    def test_none_when_empty_metadata(self) -> None:
        reader = ObsidianMarkdownReader(split_on_headers=False)
        assert reader._get_effective_title({}) is None


class TestStripDuplicateTitle:
    """Tests for _strip_duplicate_title: first line H1 matching effective title is removed."""

    def test_strips_when_first_line_matches_note_name(self) -> None:
        reader = ObsidianMarkdownReader(split_on_headers=False)
        meta = {"note_name": "THIS.md (Heptabase)", "file_name": "THIS.md (Heptabase).md"}
        content = "# THIS.md (Heptabase)\n\nBody paragraph."
        result = reader._strip_duplicate_title(content, meta)
        assert result == "Body paragraph."
        assert not result.startswith("# THIS.md (Heptabase)")

    def test_strips_when_first_line_matches_frontmatter_title(self) -> None:
        reader = ObsidianMarkdownReader(split_on_headers=False)
        meta = {"frontmatter": {"title": "Title Only"}, "note_name": "other", "file_name": "other.md"}
        content = "# Title Only\n\nRest of doc."
        result = reader._strip_duplicate_title(content, meta)
        assert result == "Rest of doc."

    def test_does_not_strip_when_first_line_differs_from_title(self) -> None:
        reader = ObsidianMarkdownReader(split_on_headers=False)
        meta = {"note_name": "My Note", "file_name": "My Note.md"}
        content = "# Different Heading\n\nBody."
        result = reader._strip_duplicate_title(content, meta)
        assert result == content

    def test_does_not_strip_when_no_effective_title(self) -> None:
        reader = ObsidianMarkdownReader(split_on_headers=False)
        meta = {}
        content = "# Some H1\n\nBody."
        result = reader._strip_duplicate_title(content, meta)
        assert result == content

    def test_does_not_strip_when_first_line_is_not_h1(self) -> None:
        reader = ObsidianMarkdownReader(split_on_headers=False)
        meta = {"note_name": "My Note", "file_name": "My Note.md"}
        content = "Plain first line.\n\n# My Note"
        result = reader._strip_duplicate_title(content, meta)
        assert result == content

    def test_strips_only_first_line_with_trailing_newline(self) -> None:
        reader = ObsidianMarkdownReader(split_on_headers=False)
        meta = {"note_name": "Title", "file_name": "Title.md"}
        content = "# Title\n\n\nSecond paragraph."
        result = reader._strip_duplicate_title(content, meta)
        assert result == "Second paragraph."

    def test_returns_empty_when_content_was_only_duplicate_h1(self) -> None:
        reader = ObsidianMarkdownReader(split_on_headers=False)
        meta = {"note_name": "Solo", "file_name": "Solo.md"}
        content = "# Solo\n"
        result = reader._strip_duplicate_title(content, meta)
        assert result == ""


class TestLoadDataDuplicateTitleNormalization:
    """Integration of duplicate-title stripping in load_data: stored body does not duplicate title."""

    def test_heptabase_style_file_body_does_not_start_with_duplicate_h1(self, tmp_path: Path) -> None:
        """File with stem X and first line '# X' produces body that does not start with '# X'."""
        md_file = tmp_path / "THIS.md (Heptabase).md"
        md_file.write_text(
            "# THIS.md (Heptabase)\n\nWhiteboards and boards.",
            encoding="utf-8",
        )
        reader = ObsidianMarkdownReader(split_on_headers=False)
        # Simulate metadata the vault reader would attach (note_name from filename stem).
        extra_info = {
            "note_name": "THIS.md (Heptabase)",
            "file_name": "THIS.md (Heptabase).md",
        }
        docs = reader.load_data(md_file, extra_info=extra_info)
        assert len(docs) == 1
        body = docs[0].text
        assert not body.startswith("# THIS.md (Heptabase)"), "body should not duplicate title"
        assert "Whiteboards and boards" in body

    def test_first_line_unchanged_when_not_matching_title(self, tmp_path: Path) -> None:
        """When first line is not the title, body is left unchanged."""
        md_file = tmp_path / "My Note.md"
        md_file.write_text(
            "# Actual Heading\n\nContent here.",
            encoding="utf-8",
        )
        reader = ObsidianMarkdownReader(split_on_headers=False)
        extra_info = {"note_name": "My Note", "file_name": "My Note.md"}
        docs = reader.load_data(md_file, extra_info=extra_info)
        assert len(docs) == 1
        assert docs[0].text.strip().startswith("# Actual Heading")
