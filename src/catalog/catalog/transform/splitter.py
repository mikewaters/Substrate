"""catalog.transform.splitter - Chunk splitting transforms for RAG pipelines.

Provides LlamaIndex TransformComponent classes for text chunking:
- SizeAwareChunkSplitter: Conditionally splits oversized nodes
- ResilientSplitter: Token-based primary with char-based fallback

Example usage:
    from llama_index.core.ingestion import IngestionPipeline
    from llama_index.core.node_parser import MarkdownNodeParser
    from catalog.transform.splitter import ResilientSplitter, SizeAwareChunkSplitter

    # ResilientSplitter for token-based chunking with fallback
    pipeline = IngestionPipeline(
        transformations=[
            MarkdownNodeParser(),
            ResilientSplitter(),  # Uses RAGSettings defaults
        ]
    )
    nodes = pipeline.run(documents=documents)
"""

from typing import Any

from agentlayer.logging import get_logger
from llama_index.core.node_parser import SentenceSplitter, TokenTextSplitter
from llama_index.core.schema import BaseNode, TransformComponent

from catalog.core.settings import get_settings

__all__ = ["ResilientSplitter", "SizeAwareChunkSplitter"]

logger = get_logger(__name__)


class ResilientSplitter(TransformComponent):
    """Token-based text splitter with character-based fallback.

    This TransformComponent uses TokenTextSplitter as the primary chunking
    strategy, with SentenceSplitter as a fallback when tokenization fails.
    This provides resilient chunking that handles edge cases like malformed
    text or tokenizer errors gracefully.

    The splitter reads defaults from RAGSettings and logs fallback events
    for monitoring purposes.

    Attributes:
        chunk_size_tokens: Target chunk size in tokens for primary splitter.
        chunk_overlap_tokens: Token overlap between chunks.
        chars_per_token: Estimated characters per token for fallback calculation.
        fallback_enabled: Whether to use char-based fallback on tokenizer errors.
    """

    chunk_size_tokens: int = 800
    chunk_overlap_tokens: int = 120
    chars_per_token: int = 4
    fallback_enabled: bool = True

    def __init__(
        self,
        chunk_size_tokens: int | None = None,
        chunk_overlap_tokens: int | None = None,
        chars_per_token: int | None = None,
        fallback_enabled: bool | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the resilient splitter.

        Args:
            chunk_size_tokens: Target chunk size in tokens. If None, reads from
                settings.rag.chunk_size.
            chunk_overlap_tokens: Token overlap between chunks. If None, reads
                from settings.rag.chunk_overlap.
            chars_per_token: Estimated characters per token for fallback
                calculation. If None, reads from settings.rag.chunk_chars_per_token.
            fallback_enabled: Whether to use char-based fallback on tokenizer
                errors. If None, reads from settings.rag.chunk_fallback_enabled.
            **kwargs: Additional arguments passed to TransformComponent.
        """
        super().__init__(**kwargs)

        # Load defaults from settings if not provided
        settings = get_settings()
        rag = settings.rag

        self.chunk_size_tokens = (
            chunk_size_tokens if chunk_size_tokens is not None else rag.chunk_size
        )
        self.chunk_overlap_tokens = (
            chunk_overlap_tokens
            if chunk_overlap_tokens is not None
            else rag.chunk_overlap
        )
        self.chars_per_token = (
            chars_per_token
            if chars_per_token is not None
            else rag.chunk_chars_per_token
        )
        self.fallback_enabled = (
            fallback_enabled
            if fallback_enabled is not None
            else rag.chunk_fallback_enabled
        )

        # Initialize primary token-based splitter
        self._token_splitter = TokenTextSplitter(
            chunk_size=self.chunk_size_tokens,
            chunk_overlap=self.chunk_overlap_tokens,
        )

        # Initialize fallback char-based splitter
        fallback_chunk_size = self.chunk_size_tokens * self.chars_per_token
        fallback_overlap = self.chunk_overlap_tokens * self.chars_per_token
        self._char_splitter = SentenceSplitter(
            chunk_size=fallback_chunk_size,
            chunk_overlap=fallback_overlap,
        )

    def __call__(
        self,
        nodes: list[BaseNode],
        **kwargs: Any,
    ) -> list[BaseNode]:
        """Process nodes through token-based splitting with fallback.

        Attempts to split nodes using TokenTextSplitter. If tokenization fails
        and fallback is enabled, uses SentenceSplitter as a character-based
        fallback. Logs all fallback events for monitoring.

        Args:
            nodes: List of nodes to split.
            **kwargs: Additional arguments (unused).

        Returns:
            List of split nodes.

        Raises:
            Exception: Re-raises tokenizer exceptions if fallback is disabled.
        """
        logger.info(f"ResilientSplitter: processing {len(nodes)} nodes")

        try:
            result = self._token_splitter(nodes, **kwargs)
            logger.debug(
                f"ResilientSplitter: token splitting succeeded, "
                f"produced {len(result)} chunks"
            )
            return result
        except Exception as e:
            if not self.fallback_enabled:
                logger.error(
                    f"ResilientSplitter: token splitting failed and fallback disabled: {e}"
                )
                raise

            logger.warning(
                f"ResilientSplitter: token splitting failed, using char-based fallback. "
                f"Error: {type(e).__name__}: {e}"
            )

            result = self._char_splitter(nodes, **kwargs)
            logger.info(
                f"ResilientSplitter: char-based fallback succeeded, "
                f"produced {len(result)} chunks"
            )
            return result


class SizeAwareChunkSplitter(TransformComponent):
    """LlamaIndex TransformComponent that splits oversized nodes.

    This transform conditionally splits nodes that exceed a character threshold
    using LlamaIndex's SentenceSplitter. Nodes within the size limit pass
    through unchanged, preserving their original structure.

    Useful as a post-processing step after MarkdownNodeParser to handle
    sections that are too large for embedding models while preserving
    the semantic structure of smaller chunks.

    Attributes:
        max_chars: Maximum character count before triggering split.
        fallback_chunk_size: Target chunk size for SentenceSplitter.
        fallback_chunk_overlap: Overlap between chunks for SentenceSplitter.
    """

    max_chars: int = 2000
    fallback_chunk_size: int = 512
    fallback_chunk_overlap: int = 50

    def __init__(
        self,
        *,
        max_chars: int = 2000,
        fallback_chunk_size: int = 512,
        fallback_chunk_overlap: int = 50,
        **kwargs: Any,
    ) -> None:
        """Initialize the size-aware chunk splitter.

        Args:
            max_chars: Maximum character count before triggering fallback split.
                Nodes with content exceeding this threshold will be split.
            fallback_chunk_size: Target chunk size in characters for
                SentenceSplitter when splitting oversized nodes.
            fallback_chunk_overlap: Number of overlapping characters between
                chunks when using SentenceSplitter.
            **kwargs: Additional arguments passed to TransformComponent.
        """
        super().__init__(**kwargs)
        self.max_chars = max_chars
        self.fallback_chunk_size = fallback_chunk_size
        self.fallback_chunk_overlap = fallback_chunk_overlap

    def __call__(
        self,
        nodes: list[BaseNode],
        **kwargs: Any,
    ) -> list[BaseNode]:
        """Process nodes, splitting those that exceed the size threshold.

        Nodes within the max_chars limit pass through unchanged. Oversized
        nodes are split using SentenceSplitter with the configured parameters.
        Metadata from the original node is preserved on all resulting chunks.

        Args:
            nodes: List of nodes to process.
            **kwargs: Additional arguments (unused).

        Returns:
            List of nodes with oversized ones split into smaller chunks.
        """
        logger.info(f"SizeAwareChunkSplitter: processing {len(nodes)} nodes")

        result: list[BaseNode] = []
        split_count = 0
        pass_through_count = 0

        # Create splitter instance for oversized nodes
        splitter = SentenceSplitter(
            chunk_size=self.fallback_chunk_size,
            chunk_overlap=self.fallback_chunk_overlap,
        )

        for node in nodes:
            content = node.get_content()
            content_len = len(content)

            if content_len <= self.max_chars:
                # Node is within size limit - pass through unchanged
                result.append(node)
                pass_through_count += 1
            else:
                # Node exceeds threshold - split using SentenceSplitter
                logger.debug(
                    f"Splitting oversized node ({content_len} chars > {self.max_chars}): "
                    f"{node.node_id[:50]}..."
                )

                # SentenceSplitter.get_nodes_from_documents expects nodes
                split_nodes = splitter.get_nodes_from_documents([node])

                # Preserve original metadata on all split chunks
                original_metadata = node.metadata.copy() if node.metadata else {}
                for i, split_node in enumerate(split_nodes):
                    # Merge original metadata (split_node may have its own metadata)
                    merged_metadata = original_metadata.copy()
                    if split_node.metadata:
                        merged_metadata.update(split_node.metadata)
                    split_node.metadata = merged_metadata

                    # Track that this came from a split
                    split_node.metadata["_split_from"] = node.node_id
                    split_node.metadata["_split_index"] = i
                    split_node.metadata["_split_total"] = len(split_nodes)

                result.extend(split_nodes)
                split_count += 1

                logger.debug(
                    f"Split node into {len(split_nodes)} chunks"
                )

        if split_count > 0:
            logger.info(
                f"SizeAwareChunkSplitter complete: {pass_through_count} passed through, "
                f"{split_count} split -> {len(result)} total nodes"
            )
        else:
            logger.info(
                f"SizeAwareChunkSplitter complete: {len(result)} nodes (no splitting needed)"
            )

        return result
