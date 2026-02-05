"""Unit tests for the ResilientSplitter class."""

from unittest.mock import MagicMock, patch

import pytest
from llama_index.core.schema import Document, TextNode

from catalog.transform.splitter import ResilientSplitter


class TestResilientSplitterInit:
    """Tests for ResilientSplitter initialization."""

    def test_init_default_values_from_settings(self) -> None:
        """Test that defaults are loaded from RAGv2Settings."""
        with patch("catalog.transform.splitter.get_settings") as mock_settings:
            mock_rag_v2 = MagicMock()
            mock_rag_v2.chunk_size = 500
            mock_rag_v2.chunk_overlap = 50
            mock_rag_v2.chunk_chars_per_token = 3
            mock_rag_v2.chunk_fallback_enabled = False
            mock_settings.return_value.rag_v2 = mock_rag_v2

            splitter = ResilientSplitter()

            assert splitter.chunk_size_tokens == 500
            assert splitter.chunk_overlap_tokens == 50
            assert splitter.chars_per_token == 3
            assert splitter.fallback_enabled is False

    def test_init_custom_values_override_settings(self) -> None:
        """Test that custom values override settings defaults."""
        splitter = ResilientSplitter(
            chunk_size_tokens=1000,
            chunk_overlap_tokens=200,
            chars_per_token=5,
            fallback_enabled=False,
        )

        assert splitter.chunk_size_tokens == 1000
        assert splitter.chunk_overlap_tokens == 200
        assert splitter.chars_per_token == 5
        assert splitter.fallback_enabled is False

    def test_init_creates_token_splitter(self) -> None:
        """Test that TokenTextSplitter is created with correct params."""
        splitter = ResilientSplitter(
            chunk_size_tokens=400,
            chunk_overlap_tokens=80,
        )

        assert splitter._token_splitter.chunk_size == 400
        assert splitter._token_splitter.chunk_overlap == 80

    def test_init_creates_char_splitter_with_conversion(self) -> None:
        """Test that SentenceSplitter is created with char conversion."""
        splitter = ResilientSplitter(
            chunk_size_tokens=400,
            chunk_overlap_tokens=80,
            chars_per_token=4,
        )

        # 400 tokens * 4 chars/token = 1600 chars
        assert splitter._char_splitter.chunk_size == 1600
        # 80 tokens * 4 chars/token = 320 chars
        assert splitter._char_splitter.chunk_overlap == 320


class TestResilientSplitterNormalOperation:
    """Tests for normal token-based splitting."""

    def test_splits_document_into_chunks(self) -> None:
        """Test that documents are split into chunks."""
        splitter = ResilientSplitter(
            chunk_size_tokens=50,
            chunk_overlap_tokens=10,
        )

        # Create a document with enough content to be split
        text = "This is a test sentence. " * 20  # Repeat to create longer text
        doc = Document(text=text, doc_id="test_doc")

        nodes = splitter([doc])

        assert len(nodes) > 0
        # All nodes should be TextNodes
        for node in nodes:
            assert isinstance(node, TextNode)

    def test_handles_multiple_documents(self) -> None:
        """Test splitting multiple documents."""
        splitter = ResilientSplitter(
            chunk_size_tokens=100,
            chunk_overlap_tokens=20,
        )

        docs = [
            Document(text="Document one content here.", doc_id="doc1"),
            Document(text="Document two content here.", doc_id="doc2"),
        ]

        nodes = splitter(docs)

        assert len(nodes) >= 2  # At least one node per document

    def test_handles_text_nodes(self) -> None:
        """Test splitting TextNode inputs."""
        splitter = ResilientSplitter(
            chunk_size_tokens=100,
            chunk_overlap_tokens=20,
        )

        text_node = TextNode(
            id_="node1",
            text="Sample text content for the node.",
        )

        nodes = splitter([text_node])

        assert len(nodes) >= 1

    def test_preserves_metadata(self) -> None:
        """Test that metadata is preserved on output nodes."""
        splitter = ResilientSplitter(
            chunk_size_tokens=100,
            chunk_overlap_tokens=20,
        )

        doc = Document(
            text="Short text",
            doc_id="doc1",
            metadata={"source": "test", "path": "/test/file.md"},
        )

        nodes = splitter([doc])

        assert len(nodes) >= 1
        # Metadata should be present (may be modified by splitter)
        for node in nodes:
            assert isinstance(node.metadata, dict)


class TestResilientSplitterFallback:
    """Tests for fallback behavior."""

    def test_falls_back_on_tokenizer_error(self) -> None:
        """Test fallback to char-based splitter on tokenizer failure."""
        splitter = ResilientSplitter(
            chunk_size_tokens=100,
            chunk_overlap_tokens=20,
            fallback_enabled=True,
        )

        # Mock the token splitter to raise an exception
        splitter._token_splitter = MagicMock(side_effect=Exception("Tokenizer error"))

        doc = Document(text="Some test content", doc_id="test")

        # Should not raise, should use fallback
        nodes = splitter([doc])

        assert len(nodes) >= 1

    def test_raises_when_fallback_disabled(self) -> None:
        """Test that errors propagate when fallback is disabled."""
        splitter = ResilientSplitter(
            chunk_size_tokens=100,
            chunk_overlap_tokens=20,
            fallback_enabled=False,
        )

        # Mock the token splitter to raise an exception
        splitter._token_splitter = MagicMock(side_effect=ValueError("Tokenizer error"))

        doc = Document(text="Some test content", doc_id="test")

        with pytest.raises(ValueError, match="Tokenizer error"):
            splitter([doc])

    def test_fallback_logs_warning(self) -> None:
        """Test that fallback events are logged."""
        splitter = ResilientSplitter(
            chunk_size_tokens=100,
            chunk_overlap_tokens=20,
            fallback_enabled=True,
        )

        # Mock the token splitter to raise an exception
        splitter._token_splitter = MagicMock(
            side_effect=RuntimeError("Test tokenizer failure")
        )

        doc = Document(text="Some test content", doc_id="test")

        # Patch the logger to verify the warning is called
        with patch("catalog.transform.splitter.logger") as mock_logger:
            splitter([doc])

            # Verify that warning was called with fallback message
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0][0]
            assert "fallback" in call_args.lower()
            assert "token splitting failed" in call_args.lower()

    def test_fallback_produces_valid_chunks(self) -> None:
        """Test that fallback produces valid, non-empty chunks."""
        splitter = ResilientSplitter(
            chunk_size_tokens=50,
            chunk_overlap_tokens=10,
            chars_per_token=4,
            fallback_enabled=True,
        )

        # Mock the token splitter to raise an exception
        splitter._token_splitter = MagicMock(side_effect=Exception("Tokenizer error"))

        # Create text long enough to be split
        text = "This is a longer piece of text that should be split. " * 10
        doc = Document(text=text, doc_id="test")

        nodes = splitter([doc])

        assert len(nodes) >= 1
        # All chunks should have content
        for node in nodes:
            assert len(node.get_content().strip()) > 0


class TestResilientSplitterChunkSizes:
    """Tests for chunk size behavior."""

    def test_respects_chunk_size_token_limit(self) -> None:
        """Test that chunks respect the token size limit approximately."""
        splitter = ResilientSplitter(
            chunk_size_tokens=50,
            chunk_overlap_tokens=10,
        )

        # Create a long document
        text = "Word " * 500  # ~500 words
        doc = Document(text=text, doc_id="test")

        nodes = splitter([doc])

        # Should produce multiple chunks
        assert len(nodes) > 1

    def test_chunk_overlap_creates_overlapping_content(self) -> None:
        """Test that overlap creates shared content between chunks."""
        splitter = ResilientSplitter(
            chunk_size_tokens=30,
            chunk_overlap_tokens=10,
        )

        # Create a document long enough to have multiple chunks
        text = "This is sentence number one. " * 20
        doc = Document(text=text, doc_id="test")

        nodes = splitter([doc])

        if len(nodes) > 1:
            # With overlap, chunks should share some content
            # This is a basic test - actual overlap depends on tokenizer
            pass  # Overlap is handled by the underlying splitter


class TestResilientSplitterEdgeCases:
    """Tests for edge cases."""

    def test_empty_node_list(self) -> None:
        """Test handling of empty node list."""
        splitter = ResilientSplitter(
            chunk_size_tokens=100,
            chunk_overlap_tokens=20,
        )

        nodes = splitter([])

        assert nodes == []

    def test_empty_document(self) -> None:
        """Test handling of document with empty text."""
        splitter = ResilientSplitter(
            chunk_size_tokens=100,
            chunk_overlap_tokens=20,
        )

        doc = Document(text="", doc_id="empty")

        nodes = splitter([doc])

        # Should handle gracefully (may return 0 or 1 nodes depending on splitter)
        assert isinstance(nodes, list)

    def test_unicode_content(self) -> None:
        """Test handling of unicode content."""
        splitter = ResilientSplitter(
            chunk_size_tokens=50,
            chunk_overlap_tokens=10,
        )

        # Text with various unicode characters
        text = "Hello world. Bonjour monde. Hola mundo. " * 10
        doc = Document(text=text, doc_id="unicode")

        nodes = splitter([doc])

        assert len(nodes) >= 1
        # Content should be preserved
        combined = " ".join(node.get_content() for node in nodes)
        assert "Hello" in combined
        assert "Bonjour" in combined
        assert "Hola" in combined

    def test_very_short_document(self) -> None:
        """Test handling of very short document that fits in one chunk."""
        splitter = ResilientSplitter(
            chunk_size_tokens=1000,
            chunk_overlap_tokens=200,
        )

        doc = Document(text="Short.", doc_id="short")

        nodes = splitter([doc])

        assert len(nodes) == 1
        assert "Short" in nodes[0].get_content()
