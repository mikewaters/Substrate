"""Tests for catalog.store.vector module."""

import sys
from types import ModuleType

from catalog.store.vector import _build_embed_model


class _FakeHuggingFaceEmbedding:
    """Test double for HuggingFaceEmbedding."""

    init_count = 0

    def __init__(self, model_name: str, embed_batch_size: int) -> None:
        type(self).init_count += 1
        self.model_name = model_name
        self.embed_batch_size = embed_batch_size


class TestEmbeddingModelCache:
    """Tests for process-level embedding model cache behavior."""

    def setup_method(self) -> None:
        """Reset cache and counters before each test."""
        _build_embed_model.cache_clear()
        _FakeHuggingFaceEmbedding.init_count = 0

    def test_reuses_model_for_identical_configuration(self, monkeypatch) -> None:
        """Same backend/model/batch returns the same cached model instance."""
        fake_module = ModuleType("llama_index.embeddings.huggingface")
        fake_module.HuggingFaceEmbedding = _FakeHuggingFaceEmbedding
        monkeypatch.setitem(sys.modules, "llama_index.embeddings.huggingface", fake_module)

        model_a = _build_embed_model("huggingface", "test-model", 16)
        model_b = _build_embed_model("huggingface", "test-model", 16)

        assert model_a is model_b
        assert _FakeHuggingFaceEmbedding.init_count == 1

    def test_builds_new_model_for_different_configuration(self, monkeypatch) -> None:
        """Different model configuration does not reuse prior cache entries."""
        fake_module = ModuleType("llama_index.embeddings.huggingface")
        fake_module.HuggingFaceEmbedding = _FakeHuggingFaceEmbedding
        monkeypatch.setitem(sys.modules, "llama_index.embeddings.huggingface", fake_module)

        first = _build_embed_model("huggingface", "model-a", 16)
        second = _build_embed_model("huggingface", "model-b", 16)

        assert first is not second
        assert _FakeHuggingFaceEmbedding.init_count == 2
