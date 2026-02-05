"""catalog.embedding.resilient - Resilient embedding wrapper with fallback.

Provides a wrapper around BaseEmbedding that falls back to single-item
embedding when batch embedding fails. This is useful for handling edge
cases where certain texts cause batch processing to fail.

Example usage:
    from catalog.embedding.resilient import ResilientEmbedding
    from catalog.embedding.mlx import MLXEmbedding

    base_model = MLXEmbedding()
    resilient_model = ResilientEmbedding(embed_model=base_model, batch_size=32)
    embeddings = resilient_model.get_text_embedding_batch(texts)
"""

from typing import Any

from agentlayer.logging import get_logger
from llama_index.core.bridge.pydantic import PrivateAttr
from llama_index.core.embeddings import BaseEmbedding

__all__ = ["ResilientEmbedding"]

logger = get_logger(__name__)


class ResilientEmbedding(BaseEmbedding):
    """Wrapper that falls back to single-item embedding on batch errors.

    Wraps any BaseEmbedding implementation and provides resilient batch
    embedding by falling back to individual embeddings when batch processing
    fails. This handles edge cases where specific texts cause batch failures.

    The wrapper delegates all operations to the underlying embed model,
    intercepting only batch operations to add fallback behavior.

    Attributes:
        model_name: Name of the underlying embedding model (for compatibility).

    Example:
        base_model = MLXEmbedding()
        resilient = ResilientEmbedding(embed_model=base_model)
        # Batch embedding with automatic fallback on failure
        embeddings = resilient.get_text_embedding_batch(texts)
    """

    model_name: str = "resilient-wrapper"

    # Private attributes
    _embed_model: BaseEmbedding = PrivateAttr()
    _batch_size: int = PrivateAttr()

    def __init__(
        self,
        embed_model: BaseEmbedding,
        batch_size: int = 32,
        **kwargs: Any,
    ) -> None:
        """Initialize the resilient embedding wrapper.

        Args:
            embed_model: The underlying BaseEmbedding to wrap.
            batch_size: Batch size for embedding operations. Defaults to 32.
            **kwargs: Additional arguments passed to BaseEmbedding.
        """
        # Get model_name from the wrapped model if available
        wrapped_model_name = getattr(embed_model, "model_name", "unknown")
        super().__init__(
            model_name=f"resilient:{wrapped_model_name}",
            embed_batch_size=batch_size,
            **kwargs,
        )
        self._embed_model = embed_model
        self._batch_size = batch_size
        logger.debug(
            f"Initialized ResilientEmbedding wrapping {wrapped_model_name} "
            f"with batch_size={batch_size}"
        )

    @classmethod
    def class_name(cls) -> str:
        """Return the class name for serialization."""
        return "ResilientEmbedding"

    def _get_text_embedding(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Delegates to the underlying embed model.

        Args:
            text: The text to embed.

        Returns:
            List of floats representing the text embedding.
        """
        return self._embed_model._get_text_embedding(text)

    def _get_query_embedding(self, query: str) -> list[float]:
        """Generate embedding for a query.

        Delegates to the underlying embed model.

        Args:
            query: The query text to embed.

        Returns:
            List of floats representing the query embedding.
        """
        return self._embed_model._get_query_embedding(query)

    def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts with fallback.

        Attempts batch embedding first. If batch processing fails,
        falls back to embedding texts one at a time.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embeddings, one per input text.
        """
        if not texts:
            return []

        try:
            return self._embed_model._get_text_embeddings(texts)
        except Exception as e:
            logger.warning(
                f"Batch embedding failed for {len(texts)} texts, "
                f"falling back to individual embedding: {e}"
            )
            return self._individual_embed(texts)

    def _individual_embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts one at a time.

        Used as fallback when batch embedding fails. Logs success/failure
        for each text to aid debugging.

        Args:
            texts: List of texts to embed individually.

        Returns:
            List of embeddings, one per input text.

        Raises:
            RuntimeError: If all individual embeddings fail.
        """
        embeddings: list[list[float]] = []
        failed_count = 0

        for i, text in enumerate(texts):
            try:
                embedding = self._embed_model._get_text_embedding(text)
                embeddings.append(embedding)
            except Exception as e:
                logger.error(
                    f"Individual embedding failed for text {i + 1}/{len(texts)}: {e}"
                )
                failed_count += 1
                raise

        if failed_count > 0:
            logger.warning(
                f"Individual embedding completed with {failed_count} failures "
                f"out of {len(texts)} texts"
            )
        else:
            logger.info(
                f"Individual embedding fallback completed successfully "
                f"for {len(texts)} texts"
            )

        return embeddings

    async def _aget_query_embedding(self, query: str) -> list[float]:
        """Async wrapper for query embedding generation.

        Delegates to the underlying model's async method if available,
        otherwise falls back to sync.

        Args:
            query: The query text to embed.

        Returns:
            List of floats representing the query embedding.
        """
        return await self._embed_model._aget_query_embedding(query)

    async def _aget_text_embedding(self, text: str) -> list[float]:
        """Async wrapper for single text embedding generation.

        Delegates to the underlying model's async method if available,
        otherwise falls back to sync.

        Args:
            text: The text to embed.

        Returns:
            List of floats representing the text embedding.
        """
        return await self._embed_model._aget_text_embedding(text)

    async def _aget_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Async wrapper for batch text embedding with fallback.

        Attempts batch embedding first. If batch processing fails,
        falls back to embedding texts one at a time.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embeddings, one per input text.
        """
        if not texts:
            return []

        try:
            return await self._embed_model._aget_text_embeddings(texts)
        except Exception as e:
            logger.warning(
                f"Async batch embedding failed for {len(texts)} texts, "
                f"falling back to individual embedding: {e}"
            )
            return await self._async_individual_embed(texts)

    async def _async_individual_embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts one at a time asynchronously.

        Used as fallback when async batch embedding fails.

        Args:
            texts: List of texts to embed individually.

        Returns:
            List of embeddings, one per input text.

        Raises:
            RuntimeError: If individual embedding fails.
        """
        embeddings: list[list[float]] = []

        for i, text in enumerate(texts):
            try:
                embedding = await self._embed_model._aget_text_embedding(text)
                embeddings.append(embedding)
            except Exception as e:
                logger.error(
                    f"Async individual embedding failed for text {i + 1}/{len(texts)}: {e}"
                )
                raise

        logger.info(
            f"Async individual embedding fallback completed successfully "
            f"for {len(texts)} texts"
        )

        return embeddings
