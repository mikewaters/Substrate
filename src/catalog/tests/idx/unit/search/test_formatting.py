"""Tests for catalog.search.formatting module.

Tests for Snippet dataclass and extract_snippet function for RAG v2.
"""

from unittest.mock import patch

import pytest

from catalog.search.formatting import Snippet, extract_snippet


class TestSnippet:
    """Tests for Snippet dataclass."""

    def test_snippet_creation(self) -> None:
        """Test Snippet can be created with all required fields."""
        snippet = Snippet(
            text="def hello():\n    print('world')",
            start_line=10,
            end_line=11,
            header="@@ -10,2 +10,2 @@ path/to/file.py",
        )

        assert snippet.text == "def hello():\n    print('world')"
        assert snippet.start_line == 10
        assert snippet.end_line == 11
        assert snippet.header == "@@ -10,2 +10,2 @@ path/to/file.py"

    def test_snippet_is_dataclass(self) -> None:
        """Test Snippet is a proper dataclass with all features."""
        snippet1 = Snippet(
            text="content",
            start_line=1,
            end_line=1,
            header="@@ -1,1 +1,1 @@ file.md",
        )
        snippet2 = Snippet(
            text="content",
            start_line=1,
            end_line=1,
            header="@@ -1,1 +1,1 @@ file.md",
        )

        # Dataclass should support equality
        assert snippet1 == snippet2


class TestExtractSnippet:
    """Tests for extract_snippet function."""

    def test_line_number_at_start(self) -> None:
        """Test line number calculation when chunk is at document start."""
        doc_content = "line 1\nline 2\nline 3"
        chunk_text = "line 1"
        chunk_pos = 0

        snippet = extract_snippet(
            chunk_text=chunk_text,
            chunk_pos=chunk_pos,
            doc_content=doc_content,
            doc_path="test.md",
            max_lines=10,
        )

        assert snippet.start_line == 1
        assert snippet.end_line == 1

    def test_line_number_in_middle(self) -> None:
        """Test line number calculation when chunk is in middle of document."""
        doc_content = "line 1\nline 2\nline 3\nline 4\nline 5"
        # Position after "line 1\nline 2\n" = 7 + 7 = 14
        chunk_text = "line 3"
        chunk_pos = 14

        snippet = extract_snippet(
            chunk_text=chunk_text,
            chunk_pos=chunk_pos,
            doc_content=doc_content,
            doc_path="test.md",
            max_lines=10,
        )

        # Two newlines before position means we're on line 3
        assert snippet.start_line == 3
        assert snippet.end_line == 3

    def test_multiline_chunk(self) -> None:
        """Test snippet with multiple lines."""
        doc_content = "header\n\nbody line 1\nbody line 2\nbody line 3"
        # Position after "header\n\n" = 8
        chunk_text = "body line 1\nbody line 2\nbody line 3"
        chunk_pos = 8

        snippet = extract_snippet(
            chunk_text=chunk_text,
            chunk_pos=chunk_pos,
            doc_content=doc_content,
            doc_path="notes/test.md",
            max_lines=10,
        )

        assert snippet.start_line == 3
        assert snippet.end_line == 5
        assert snippet.text == "body line 1\nbody line 2\nbody line 3"

    def test_diff_style_header_format(self) -> None:
        """Test diff-style header is correctly formatted."""
        doc_content = "# Title\n\nParagraph text here"
        chunk_text = "Paragraph text here"
        chunk_pos = 9  # After "# Title\n\n"

        snippet = extract_snippet(
            chunk_text=chunk_text,
            chunk_pos=chunk_pos,
            doc_content=doc_content,
            doc_path="docs/readme.md",
            max_lines=10,
        )

        # Line 3, 1 line of content
        assert snippet.header == "@@ -3,1 +3,1 @@ docs/readme.md"

    def test_max_lines_limiting(self) -> None:
        """Test snippet is limited to max_lines."""
        doc_content = "\n".join([f"line {i}" for i in range(1, 21)])
        chunk_text = "\n".join([f"line {i}" for i in range(1, 16)])  # 15 lines
        chunk_pos = 0

        snippet = extract_snippet(
            chunk_text=chunk_text,
            chunk_pos=chunk_pos,
            doc_content=doc_content,
            doc_path="test.md",
            max_lines=5,
        )

        # Should only have 5 lines
        lines = snippet.text.split("\n")
        assert len(lines) == 5
        assert snippet.start_line == 1
        assert snippet.end_line == 5
        assert snippet.text == "line 1\nline 2\nline 3\nline 4\nline 5"

    def test_max_lines_header_reflects_actual_lines(self) -> None:
        """Test header reflects actual lines after max_lines limiting."""
        doc_content = "a\nb\nc\nd\ne\nf\ng\nh\ni\nj"
        chunk_text = "c\nd\ne\nf\ng\nh"  # 6 lines starting at line 3
        chunk_pos = 4  # After "a\nb\n"

        snippet = extract_snippet(
            chunk_text=chunk_text,
            chunk_pos=chunk_pos,
            doc_content=doc_content,
            doc_path="test.md",
            max_lines=3,
        )

        # Header should show 3 lines, not 6
        assert snippet.header == "@@ -3,3 +3,3 @@ test.md"
        assert snippet.end_line == 5  # start_line (3) + num_lines (3) - 1

    def test_single_line_chunk(self) -> None:
        """Test snippet with single line content."""
        doc_content = "first\nsecond\nthird"
        chunk_text = "second"
        chunk_pos = 6  # After "first\n"

        snippet = extract_snippet(
            chunk_text=chunk_text,
            chunk_pos=chunk_pos,
            doc_content=doc_content,
            doc_path="file.txt",
            max_lines=10,
        )

        assert snippet.start_line == 2
        assert snippet.end_line == 2
        assert snippet.header == "@@ -2,1 +2,1 @@ file.txt"

    def test_empty_chunk(self) -> None:
        """Test handling of empty chunk text."""
        doc_content = "line 1\n\nline 3"
        chunk_text = ""
        chunk_pos = 7  # At the empty line

        snippet = extract_snippet(
            chunk_text=chunk_text,
            chunk_pos=chunk_pos,
            doc_content=doc_content,
            doc_path="test.md",
            max_lines=10,
        )

        assert snippet.text == ""
        assert snippet.start_line == 2
        assert snippet.end_line == 2  # start + 1 - 1 = start

    def test_chunk_at_end_of_document(self) -> None:
        """Test snippet when chunk is at document end."""
        doc_content = "line 1\nline 2\nline 3\nline 4\nfinal line"
        chunk_text = "final line"
        chunk_pos = 28  # After "line 1\nline 2\nline 3\nline 4\n"

        snippet = extract_snippet(
            chunk_text=chunk_text,
            chunk_pos=chunk_pos,
            doc_content=doc_content,
            doc_path="doc.md",
            max_lines=10,
        )

        assert snippet.start_line == 5
        assert snippet.end_line == 5
        assert snippet.text == "final line"

    def test_uses_settings_default_max_lines(self) -> None:
        """Test that default max_lines comes from settings."""
        doc_content = "\n".join([f"line {i}" for i in range(1, 21)])
        chunk_text = "\n".join([f"line {i}" for i in range(1, 16)])
        chunk_pos = 0

        # Mock settings to return a specific value
        mock_settings = type(
            "MockSettings",
            (),
            {"rag": type("MockRag", (), {"snippet_max_lines": 7})()},
        )()

        # Patch at the source module since import happens inside the function
        with patch("catalog.core.settings.get_settings", return_value=mock_settings):
            snippet = extract_snippet(
                chunk_text=chunk_text,
                chunk_pos=chunk_pos,
                doc_content=doc_content,
                doc_path="test.md",
                # No max_lines provided - should use settings default
            )

        assert len(snippet.text.split("\n")) == 7
        assert snippet.end_line == 7

    def test_path_preserved_in_header(self) -> None:
        """Test that complex paths are preserved in header."""
        doc_content = "content"
        chunk_text = "content"
        chunk_pos = 0

        snippet = extract_snippet(
            chunk_text=chunk_text,
            chunk_pos=chunk_pos,
            doc_content=doc_content,
            doc_path="projects/work/notes/2024/january/meeting-notes.md",
            max_lines=10,
        )

        assert "projects/work/notes/2024/january/meeting-notes.md" in snippet.header
        assert snippet.header == "@@ -1,1 +1,1 @@ projects/work/notes/2024/january/meeting-notes.md"

    def test_chunk_with_trailing_newline(self) -> None:
        """Test chunk that ends with newline."""
        doc_content = "first\nsecond\nthird\n"
        chunk_text = "second\nthird\n"
        chunk_pos = 6  # After "first\n"

        snippet = extract_snippet(
            chunk_text=chunk_text,
            chunk_pos=chunk_pos,
            doc_content=doc_content,
            doc_path="test.md",
            max_lines=10,
        )

        # Trailing newline creates an empty line at the end
        lines = snippet.text.split("\n")
        assert len(lines) == 3  # "second", "third", ""
        assert snippet.start_line == 2
        assert snippet.end_line == 4
