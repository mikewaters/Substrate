"""Tests for catalog.embedding.identity module."""

from catalog.embedding.identity import (
    EMBEDDING_BACKEND_METADATA_KEY,
    EMBEDDING_MODEL_METADATA_KEY,
    EMBEDDING_PROFILE_METADATA_KEY,
    EmbeddingIdentity,
    resolve_embedding_identity,
)


class _MockMLXEmbedding:
    """Simple MLX-like embedding test double."""

    model_name = "mlx-community/all-MiniLM-L6-v2-bf16"


class _WrappedEmbedding:
    """Wrapper test double that mimics ResilientEmbedding."""

    def __init__(self, inner) -> None:
        self._embed_model = inner


class TestEmbeddingIdentity:
    """Tests for EmbeddingIdentity dataclass helpers."""

    def test_to_metadata(self) -> None:
        """to_metadata serializes all identity fields."""
        identity = EmbeddingIdentity(
            backend="mlx",
            model_name="test-model",
        )

        metadata = identity.to_metadata()

        assert metadata[EMBEDDING_BACKEND_METADATA_KEY] == "mlx"
        assert metadata[EMBEDDING_MODEL_METADATA_KEY] == "test-model"
        assert metadata[EMBEDDING_PROFILE_METADATA_KEY] == "mlx:test-model"

    def test_from_metadata_uses_profile(self) -> None:
        """from_metadata parses combined profile field."""
        identity = EmbeddingIdentity.from_metadata(
            {EMBEDDING_PROFILE_METADATA_KEY: "huggingface:all-MiniLM-L6-v2"}
        )

        assert identity == EmbeddingIdentity(
            backend="huggingface",
            model_name="all-MiniLM-L6-v2",
        )

    def test_from_metadata_uses_backend_and_model(self) -> None:
        """from_metadata parses explicit backend/model fields."""
        identity = EmbeddingIdentity.from_metadata(
            {
                EMBEDDING_BACKEND_METADATA_KEY: "mlx",
                EMBEDDING_MODEL_METADATA_KEY: "model-a",
            }
        )

        assert identity == EmbeddingIdentity(
            backend="mlx",
            model_name="model-a",
        )


class TestResolveEmbeddingIdentity:
    """Tests for embedding identity resolution from model instances."""

    def test_resolve_embedding_identity_prefers_model_attributes(self) -> None:
        """Model-specific identity overrides fallback values."""
        fallback = EmbeddingIdentity(
            backend="huggingface",
            model_name="fallback-model",
        )

        resolved = resolve_embedding_identity(_MockMLXEmbedding(), fallback=fallback)

        assert resolved == EmbeddingIdentity(
            backend="mlx",
            model_name="mlx-community/all-MiniLM-L6-v2-bf16",
        )

    def test_resolve_embedding_identity_unwraps_wrappers(self) -> None:
        """Wrapped embedding models are unwrapped before inference."""
        fallback = EmbeddingIdentity(
            backend="huggingface",
            model_name="fallback-model",
        )

        wrapped = _WrappedEmbedding(_MockMLXEmbedding())
        resolved = resolve_embedding_identity(wrapped, fallback=fallback)

        assert resolved.backend == "mlx"
        assert resolved.model_name == "mlx-community/all-MiniLM-L6-v2-bf16"
