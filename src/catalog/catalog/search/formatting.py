"""Snippet formatting for RAG v2 search results.

Provides utilities for extracting and formatting code/text snippets from
search results with diff-style headers for provenance tracking.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "Snippet",
    "extract_snippet",
]


@dataclass
class Snippet:
    """A formatted snippet from a document chunk.

    Contains the snippet text with line number information and a diff-style
    header for display in search results.

    Attributes:
        text: The snippet text content (possibly truncated to max_lines).
        start_line: 1-based line number where the snippet starts in the document.
        end_line: 1-based line number where the snippet ends in the document.
        header: Diff-style header (e.g., "@@ -15,10 +15,10 @@ path/to/file.md").
    """

    text: str
    start_line: int
    end_line: int
    header: str


def extract_snippet(
    chunk_text: str,
    chunk_pos: int,
    doc_content: str,
    doc_path: str,
    max_lines: int | None = None,
) -> Snippet:
    """Extract a formatted snippet from a document chunk.

    Calculates line numbers from the character position and builds a diff-style
    header for provenance display. The snippet is limited to max_lines.

    Args:
        chunk_text: The text content of the chunk.
        chunk_pos: Byte/character offset of the chunk in the original document.
        doc_content: The full document content (used for line number calculation).
        doc_path: Path to the document (used in the header).
        max_lines: Maximum number of lines to include in the snippet.
            Defaults to settings.rag_v2.snippet_max_lines.

    Returns:
        A Snippet with the formatted text, line numbers, and diff-style header.
    """
    if max_lines is None:
        from catalog.core.settings import get_settings

        max_lines = get_settings().rag_v2.snippet_max_lines

    # Calculate line number from character position
    # Count newlines in content before the chunk position
    lines_before = doc_content[:chunk_pos].count("\n")
    start_line = lines_before + 1

    # Extract chunk lines and limit to max_lines
    chunk_lines = chunk_text.split("\n")[:max_lines]
    num_lines = len(chunk_lines)
    end_line = start_line + num_lines - 1

    # Build diff-style header
    header = f"@@ -{start_line},{num_lines} +{start_line},{num_lines} @@ {doc_path}"

    return Snippet(
        text="\n".join(chunk_lines),
        start_line=start_line,
        end_line=end_line,
        header=header,
    )
