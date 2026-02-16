"""Tests for extract_heading_body in catalog.store.fts_chunk."""

import pytest

from catalog.store.fts_chunk import extract_heading_body


class TestExtractHeadingBody:
    """Tests for the heading/body text splitter."""

    def test_plain_body_no_headings(self) -> None:
        """Text without headings returns empty heading_text and full body."""
        text = "This is plain body content.\nWith multiple lines."
        heading, body = extract_heading_body(text)
        assert heading == ""
        assert body == "This is plain body content.\nWith multiple lines."

    def test_single_heading(self) -> None:
        """Single heading is extracted, body has heading removed."""
        text = "# My Title\nBody content here."
        heading, body = extract_heading_body(text)
        assert heading == "My Title"
        assert body == "Body content here."

    def test_heading_only_no_body(self) -> None:
        """Text with only heading returns heading and empty body."""
        text = "# Just a Heading"
        heading, body = extract_heading_body(text)
        assert heading == "Just a Heading"
        assert body == ""

    def test_mixed_headings_and_body(self) -> None:
        """Multiple headings mixed with body content."""
        text = "# Title\nSome intro text.\n## Section One\nSection content.\n### Subsection\nMore content."
        heading, body = extract_heading_body(text)
        assert "Title" in heading
        assert "Section One" in heading
        assert "Subsection" in heading
        # Body should not contain heading lines
        assert "# Title" not in body
        assert "## Section One" not in body
        assert "### Subsection" not in body
        assert "Some intro text." in body
        assert "Section content." in body
        assert "More content." in body

    def test_nested_headings_all_levels(self) -> None:
        """All heading levels (h1-h6) are extracted."""
        text = "# H1\n## H2\n### H3\n#### H4\n##### H5\n###### H6\nBody."
        heading, body = extract_heading_body(text)
        for level in ["H1", "H2", "H3", "H4", "H5", "H6"]:
            assert level in heading
        assert body == "Body."

    def test_frontmatter_plus_headings(self) -> None:
        """YAML frontmatter title is combined with markdown headings."""
        text = "---\ntitle: FM Title\n---\n# Heading One\nBody text."
        heading, body = extract_heading_body(text)
        assert "FM Title" in heading
        assert "Heading One" in heading
        assert "Body text." in body

    def test_frontmatter_only_no_headings(self) -> None:
        """YAML frontmatter title only, no markdown headings."""
        text = "---\ntitle: Document Title\n---\nJust body content."
        heading, body = extract_heading_body(text)
        assert heading == "Document Title"
        assert body == "Just body content."

    def test_non_heading_hash_symbols(self) -> None:
        """Hash symbols not at line start are not treated as headings."""
        text = "This has a #hashtag and C# language mention.\nAnd foo#bar."
        heading, body = extract_heading_body(text)
        assert heading == ""
        assert "#hashtag" in body
        assert "C#" in body

    def test_empty_text(self) -> None:
        """Empty string returns empty heading and body."""
        heading, body = extract_heading_body("")
        assert heading == ""
        assert body == ""

    def test_heading_without_space_after_hash(self) -> None:
        """Lines like '#NoSpace' are NOT headings (no space after #)."""
        text = "#NoSpace\nBody content."
        heading, body = extract_heading_body(text)
        # The regex requires space after #, so this is not a heading
        assert heading == ""
        assert "#NoSpace" in body

    def test_multiple_headings_joined_by_newline(self) -> None:
        """Multiple extracted headings are joined by newline."""
        text = "# First\n## Second\n### Third"
        heading, body = extract_heading_body(text)
        parts = heading.split("\n")
        assert len(parts) == 3
        assert parts[0] == "First"
        assert parts[1] == "Second"
        assert parts[2] == "Third"
