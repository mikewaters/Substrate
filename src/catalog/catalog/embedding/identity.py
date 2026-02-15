"""catalog.embedding.identity - Embedding identity metadata helpers.

Defines a stable embedding identity payload that is attached to each vector at
ingest time and reused at query time to choose the correct embedding model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

EMBEDDING_BACKEND_METADATA_KEY = "embedding_backend"
EMBEDDING_MODEL_METADATA_KEY = "embedding_model_name"
EMBEDDING_PROFILE_METADATA_KEY = "embedding_profile"

__all__ = [
    "EMBEDDING_BACKEND_METADATA_KEY",
    "EMBEDDING_MODEL_METADATA_KEY",
    "EMBEDDING_PROFILE_METADATA_KEY",
    "EmbeddingIdentity",
    "resolve_embedding_identity",
]


@dataclass(frozen=True, slots=True)
class EmbeddingIdentity:
    """Identity describing the embedding space for a vector.

    Attributes:
        backend: Embedding backend name (for example ``mlx`` or
            ``huggingface``).
        model_name: Model identifier used for vector generation.
    """

    backend: str
    model_name: str

    @property
    def profile(self) -> str:
        """Stable profile key used in vector metadata and filters."""
        return f"{self.backend}:{self.model_name}"

    def to_metadata(self) -> dict[str, str]:
        """Serialize identity to vector metadata fields."""
        return {
            EMBEDDING_BACKEND_METADATA_KEY: self.backend,
            EMBEDDING_MODEL_METADATA_KEY: self.model_name,
            EMBEDDING_PROFILE_METADATA_KEY: self.profile,
        }

    @classmethod
    def from_metadata(
        cls,
        metadata: Mapping[str, Any] | None,
    ) -> "EmbeddingIdentity | None":
        """Parse embedding identity from vector metadata.

        Supports both explicit backend/model fields and the combined profile
        field.
        """
        if not metadata:
            return None

        profile = metadata.get(EMBEDDING_PROFILE_METADATA_KEY)
        if isinstance(profile, str) and ":" in profile:
            backend, model_name = profile.split(":", 1)
            if backend and model_name:
                return cls(backend=backend, model_name=model_name)

        backend = metadata.get(EMBEDDING_BACKEND_METADATA_KEY)
        model_name = metadata.get(EMBEDDING_MODEL_METADATA_KEY)
        if isinstance(backend, str) and isinstance(model_name, str):
            if backend and model_name:
                return cls(backend=backend, model_name=model_name)

        return None


def resolve_embedding_identity(
    embed_model: Any,
    fallback: EmbeddingIdentity,
) -> EmbeddingIdentity:
    """Resolve embedding identity from a model instance.

    Args:
        embed_model: Embedding model object, possibly wrapped.
        fallback: Fallback identity when model introspection is incomplete.

    Returns:
        EmbeddingIdentity inferred from the model and fallback values.
    """
    model = getattr(embed_model, "_embed_model", embed_model)

    model_name = getattr(model, "model_name", None)
    if not isinstance(model_name, str) or not model_name:
        model_name = fallback.model_name

    backend = _infer_backend(model)
    if backend is None:
        backend = fallback.backend

    return EmbeddingIdentity(backend=backend, model_name=model_name)


def _infer_backend(embed_model: Any) -> str | None:
    """Best-effort backend inference from module/class names."""
    module_name = type(embed_model).__module__.lower()
    class_name = type(embed_model).__name__.lower()
    combined = f"{module_name}.{class_name}"

    if "huggingface" in combined:
        return "huggingface"
    if "mlx" in combined:
        return "mlx"
    return None
