"""catalog.embedding - Embedding models for vector generation.

Provides embedding model implementations for generating vector representations
of text. Currently supports MLX-based embeddings for efficient inference on
Apple Silicon devices.

Example usage:
    from catalog.embedding import MLXEmbedding

    embed_model = MLXEmbedding()
    embedding = embed_model.get_text_embedding("Hello world")
"""
from agentlayer.logging import get_logger
from catalog.core.settings import get_settings
from llama_index.core.embeddings import BaseEmbedding

from catalog.embedding.mlx import MLXEmbedding

logger = get_logger(__name__)

def get_embed_model() -> "BaseEmbedding":
    """Get the embedding model based on settings.

    Returns:
        BaseEmbedding instance configured from settings.
    """
    settings = get_settings()
    embed_settings = settings.embedding

    if embed_settings.backend == "mlx":
        from catalog.embedding.mlx import MLXEmbedding

        logger.debug(f"Loading MLX embedding model: {embed_settings.model_name}")
        embed_model = MLXEmbedding(
            model_name=embed_settings.model_name,
            embed_batch_size=embed_settings.batch_size,
        )
        logger.info(f"MLX embedding model loaded: {embed_settings.model_name}")
    else:
        from llama_index.embeddings.huggingface import HuggingFaceEmbedding

        logger.debug(f"Loading HuggingFace embedding model: {embed_settings.model_name}")
        embed_model = HuggingFaceEmbedding(
            model_name=embed_settings.model_name,
            embed_batch_size=embed_settings.batch_size,
        )
        logger.info(f"HuggingFace embedding model loaded: {embed_settings.model_name}")

    return embed_model

__all__ = ["MLXEmbedding", "get_embed_model"]
