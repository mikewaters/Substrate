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

from catalog.embedding.identity import (
    EMBEDDING_BACKEND_METADATA_KEY,
    EMBEDDING_MODEL_METADATA_KEY,
    EMBEDDING_PROFILE_METADATA_KEY,
    EmbeddingIdentity,
    resolve_embedding_identity,
)
from catalog.embedding.mlx import MLXEmbedding
from catalog.embedding.resilient import ResilientEmbedding

logger = get_logger(__name__)


def build_embed_model(backend: str, model_name: str, batch_size: int) -> "BaseEmbedding":
    """Build an embedding model for the given backend and configuration.

    Single source of truth for backend dispatch and constructor arguments.
    Used by get_embed_model (from settings) and by cached callers (e.g. vector store).

    Args:
        backend: Embedding backend name (e.g. ``mlx`` or ``huggingface``).
        model_name: Embedding model identifier.
        batch_size: Embedding batch size.

    Returns:
        Configured BaseEmbedding instance.
    """
    if backend == "mlx":
        logger.debug(f"Loading MLX embedding model: {model_name}")
        embed_model = MLXEmbedding(
            model_name=model_name,
            embed_batch_size=batch_size,
        )
        logger.info(f"MLX embedding model loaded: {model_name}")
        return embed_model

    from llama_index.embeddings.huggingface import HuggingFaceEmbedding

    logger.debug(f"Loading HuggingFace embedding model: {model_name}")
    embed_model = HuggingFaceEmbedding(
        model_name=model_name,
        embed_batch_size=batch_size,
    )
    logger.info(f"HuggingFace embedding model loaded: {model_name}")
    return embed_model


def get_embed_model(resilient: bool = False) -> "BaseEmbedding":
    """Get the embedding model based on settings.

    Args:
        resilient: If True, wrap the model in ResilientEmbedding for
            automatic fallback to single-item embedding on batch failures.
            Defaults to False.

    Returns:
        BaseEmbedding instance configured from settings. When resilient=True,
        returns a ResilientEmbedding wrapper around the base model.
    """
    settings = get_settings()
    embed_settings = settings.embedding
    embed_model = build_embed_model(
        backend=embed_settings.backend,
        model_name=embed_settings.model_name,
        batch_size=embed_settings.batch_size,
    )

    if resilient:
        batch_size = settings.rag.embed_batch_size
        logger.debug(
            f"Wrapping embedding model in ResilientEmbedding with batch_size={batch_size}"
        )
        embed_model = ResilientEmbedding(
            embed_model=embed_model,
            batch_size=batch_size,
        )
        logger.info("ResilientEmbedding wrapper enabled")

    return embed_model


__all__ = [
    "EMBEDDING_BACKEND_METADATA_KEY",
    "EMBEDDING_MODEL_METADATA_KEY",
    "EMBEDDING_PROFILE_METADATA_KEY",
    "EmbeddingIdentity",
    "MLXEmbedding",
    "ResilientEmbedding",
    "build_embed_model",
    "get_embed_model",
    "resolve_embedding_identity",
]
