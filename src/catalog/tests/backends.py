"""Shared backend discovery and configuration for parametrized vector store tests.

Dynamically extracts supported backend names from the VectorDBSettings type
annotation so that adding a new Literal member automatically includes it in
test parametrization.
"""

from pathlib import Path
from typing import get_args

import pytest

from catalog.core.settings import VectorDBSettings, get_settings


def get_supported_backends() -> list[str]:
    """Return backend names from the Literal annotation on VectorDBSettings.backend."""
    annotation = VectorDBSettings.model_fields["backend"].annotation
    backends = list(get_args(annotation))
    assert backends, "Failed to extract backend names from VectorDBSettings.backend annotation"
    return backends


SUPPORTED_BACKENDS: list[str] = get_supported_backends()


def configure_backend(
    monkeypatch: pytest.MonkeyPatch,
    backend: str,
    output_dir: Path,
) -> None:
    """Configure environment for a single active vector backend."""
    monkeypatch.setenv("IDX_VECTOR_DB__BACKEND", backend)
    monkeypatch.setenv("IDX_RAG__EXPANSION_ENABLED", "false")

    # Zvec is the default; always set its index path relative to the test output dir.
    monkeypatch.setenv("IDX_ZVEC__INDEX_PATH", str(output_dir / "zvec-index.json"))

    get_settings.cache_clear()
