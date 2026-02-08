"""Tests for catalog.transform.embedding module."""

import pytest
from llama_index.core.schema import TextNode

from catalog.transform.embedding import EmbeddingPrefixTransform


class TestEmbeddingPrefixTransform:
    """Tests for EmbeddingPrefixTransform class."""

    def test_prefix_applied_to_node_text(self) -> None:
        """Prefix is correctly applied to node text."""
        transform = EmbeddingPrefixTransform(prefix_template="prefix: ")
        node = TextNode(text="Hello world", metadata={})

        result = transform([node])

        assert len(result) == 1
        assert result[0].get_content() == "prefix: Hello world"

    def test_original_text_preserved_in_metadata(self) -> None:
        """Original text is preserved in metadata."""
        transform = EmbeddingPrefixTransform(prefix_template="prefix: ")
        node = TextNode(text="Hello world", metadata={})

        result = transform([node])

        assert result[0].metadata["original_text"] == "Hello world"

    def test_title_substitution_works(self) -> None:
        """Title substitution works in prefix template."""
        transform = EmbeddingPrefixTransform(
            prefix_template="title: {title} | text: "
        )
        node = TextNode(text="Content here", metadata={"title": "My Document"})

        result = transform([node])

        assert result[0].get_content() == "title: My Document | text: Content here"

    def test_empty_title_handling(self) -> None:
        """Empty title is handled gracefully."""
        transform = EmbeddingPrefixTransform(
            prefix_template="title: {title} | text: "
        )
        node = TextNode(text="Content here", metadata={})

        result = transform([node])

        assert result[0].get_content() == "title:  | text: Content here"

    def test_custom_prefix_template_support(self) -> None:
        """Custom prefix template is supported."""
        custom_template = "document: {title} >>> "
        transform = EmbeddingPrefixTransform(prefix_template=custom_template)
        node = TextNode(text="Some text", metadata={"title": "Test"})

        result = transform([node])

        assert result[0].get_content() == "document: Test >>> Some text"

    def test_default_prefix_from_settings(self) -> None:
        """Default prefix template is read from settings."""
        # When no prefix_template is provided, it should use settings default
        transform = EmbeddingPrefixTransform()

        # The default from RAGSettings is "title: {title} | text: "
        assert transform.prefix_template == "title: {title} | text: "

    def test_multiple_nodes_processed(self) -> None:
        """Multiple nodes are all processed correctly."""
        transform = EmbeddingPrefixTransform(prefix_template=">> ")
        nodes = [
            TextNode(text="First", metadata={"title": "A"}),
            TextNode(text="Second", metadata={"title": "B"}),
            TextNode(text="Third", metadata={}),
        ]

        result = transform(nodes)

        assert len(result) == 3
        assert result[0].get_content() == ">> First"
        assert result[1].get_content() == ">> Second"
        assert result[2].get_content() == ">> Third"
        assert result[0].metadata["original_text"] == "First"
        assert result[1].metadata["original_text"] == "Second"
        assert result[2].metadata["original_text"] == "Third"

    def test_existing_metadata_preserved(self) -> None:
        """Existing metadata is preserved when adding original_text."""
        transform = EmbeddingPrefixTransform(prefix_template="prefix: ")
        node = TextNode(
            text="Hello",
            metadata={"title": "Test", "custom_key": "custom_value"}
        )

        result = transform([node])

        assert result[0].metadata["title"] == "Test"
        assert result[0].metadata["custom_key"] == "custom_value"
        assert result[0].metadata["original_text"] == "Hello"

    def test_empty_prefix_template(self) -> None:
        """Empty prefix template works (no prefix added)."""
        transform = EmbeddingPrefixTransform(prefix_template="")
        node = TextNode(text="Content", metadata={})

        result = transform([node])

        assert result[0].get_content() == "Content"
        assert result[0].metadata["original_text"] == "Content"

    def test_returns_same_node_objects(self) -> None:
        """Transform returns the same node objects (mutates in place)."""
        transform = EmbeddingPrefixTransform(prefix_template="prefix: ")
        node = TextNode(text="Hello", metadata={})
        original_id = id(node)

        result = transform([node])

        assert id(result[0]) == original_id

    def test_empty_nodes_list(self) -> None:
        """Empty nodes list returns empty list."""
        transform = EmbeddingPrefixTransform(prefix_template="prefix: ")

        result = transform([])

        assert result == []
