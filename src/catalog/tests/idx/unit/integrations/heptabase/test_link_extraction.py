"""Tests for Heptabase link extraction."""

import pytest

from catalog.integrations.heptabase.links import extract_heptabase_links


class TestExtractHeptabaseLinks:
    """Tests for extract_heptabase_links function."""

    def test_simple_link(self):
        """Extracts a simple Heptabase internal link."""
        text = "See [Note.md](./Note.md) for details."
        result = extract_heptabase_links(text)
        assert result == ["Note"]

    def test_link_with_spaces(self):
        """Extracts links with spaces in note names."""
        text = "See [My Note.md](./My Note.md) here."
        result = extract_heptabase_links(text)
        assert result == ["My Note"]

    def test_multiple_links(self):
        """Extracts multiple distinct links."""
        text = "Links to [A.md](./A.md) and [B.md](./B.md)."
        result = sorted(extract_heptabase_links(text))
        assert result == ["A", "B"]

    def test_deduplicates(self):
        """Duplicate links are deduplicated."""
        text = "[Note.md](./Note.md) and again [Note.md](./Note.md)."
        result = extract_heptabase_links(text)
        assert result == ["Note"]

    def test_ignores_external_urls(self):
        """External URLs are not matched (no ./ prefix)."""
        text = "Visit [Google](https://google.com) and [Docs](http://docs.example.com)."
        result = extract_heptabase_links(text)
        assert result == []

    def test_ignores_non_internal_relative_links(self):
        """Relative links without ./ prefix are not matched."""
        text = "See [other](other.md) for info."
        result = extract_heptabase_links(text)
        assert result == []

    def test_empty_text(self):
        """Empty text returns empty list."""
        assert extract_heptabase_links("") == []

    def test_no_links(self):
        """Text without any links returns empty list."""
        text = "This is plain text with no links at all."
        assert extract_heptabase_links(text) == []

    def test_strips_md_extension(self):
        """The .md extension is stripped from the target."""
        text = "[Project Plan.md](./Project Plan.md)"
        result = extract_heptabase_links(text)
        assert result == ["Project Plan"]

    def test_handles_subdirectory_paths(self):
        """Links with subdirectory paths extract just the filename stem."""
        text = "[Sub Note.md](./subdir/Sub Note.md)"
        result = extract_heptabase_links(text)
        assert result == ["Sub Note"]

    def test_handles_fragment_identifiers(self):
        """Fragment identifiers in targets are stripped before extracting stem."""
        text = "[Note.md](./Note.md#section-1)"
        result = extract_heptabase_links(text)
        assert result == ["Note"]

    def test_different_display_and_target(self):
        """Display text and target can differ."""
        text = "[My Custom Label](./Actual Note.md)"
        result = extract_heptabase_links(text)
        assert result == ["Actual Note"]

    def test_mixed_internal_and_external(self):
        """Only internal links are extracted from mixed content."""
        text = """
# My Note

See [External](https://example.com) for reference.
Also check [Internal.md](./Internal.md) and [Other.md](./Other.md).
And this [relative](relative.md) link is not internal.
"""
        result = sorted(extract_heptabase_links(text))
        assert result == ["Internal", "Other"]

    def test_target_without_md_extension(self):
        """Targets without .md extension still produce a stem."""
        text = "[readme](./readme)"
        result = extract_heptabase_links(text)
        assert result == ["readme"]
