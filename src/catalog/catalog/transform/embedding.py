"""catalog.transform.embedding - Embedding prefix transform for RAG v2.

Provides a LlamaIndex TransformComponent that applies prefix formatting to node
text before embedding. This enables Nomic-style prefixing for improved
retrieval quality.

Example usage:
    from catalog.transform.embedding import EmbeddingPrefixTransform
    from llama_index.core.ingestion import IngestionPipeline

    pipeline = IngestionPipeline(
        transformations=[EmbeddingPrefixTransform()]
    )
    nodes = pipeline.run(documents=documents)
"""

from typing import Any

from llama_index.core.schema import BaseNode, TransformComponent

from catalog.core.settings import get_settings

__all__ = [
    "EmbeddingPrefixTransform",
]


class EmbeddingPrefixTransform(TransformComponent):
    """Apply prefix formatting to node text before embedding.

    This transform prepends a formatted prefix to each node's text content,
    following Nomic-style embedding prefixes. The original text is preserved
    in node metadata for reference.

    The prefix template supports {title} substitution from node metadata.
    If no title is found in metadata, an empty string is used.

    Attributes:
        prefix_template: Template string with optional {title} placeholder.
            Defaults to the value from settings.rag_v2.embed_prefix_doc.
    """

    prefix_template: str = ""

    def __init__(
        self,
        prefix_template: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the embedding prefix transform.

        Args:
            prefix_template: Template string with optional {title} placeholder.
                If not provided, uses settings.rag_v2.embed_prefix_doc.
            **kwargs: Additional arguments passed to TransformComponent.
        """
        super().__init__(**kwargs)
        if prefix_template is None:
            self.prefix_template = get_settings().rag_v2.embed_prefix_doc
        else:
            self.prefix_template = prefix_template

    def __call__(
        self,
        nodes: list[BaseNode],
        **kwargs: Any,
    ) -> list[BaseNode]:
        """Apply prefix formatting to each node's text.

        For each node:
        1. Extracts title from metadata (defaults to empty string)
        2. Formats the prefix template with the title
        3. Stores original text in metadata["original_text"]
        4. Prepends the formatted prefix to node text

        Args:
            nodes: List of nodes to transform.
            **kwargs: Additional arguments (unused).

        Returns:
            The same nodes with prefixed text and original_text in metadata.
        """
        for node in nodes:
            # Extract title from metadata
            title = ""
            if node.metadata:
                title = node.metadata.get("title", "")

            # Format the prefix
            prefix = self.prefix_template.format(title=title)

            # Preserve original text in metadata
            original_text = node.get_content()
            node.metadata["original_text"] = original_text

            # Apply prefix to text
            node.set_content(prefix + original_text)

        return nodes
