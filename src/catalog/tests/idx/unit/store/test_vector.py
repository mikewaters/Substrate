"""Tests for catalog.store.vector module."""

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

from catalog.embedding.identity import EmbeddingIdentity
from catalog.store.vector import (
    VectorBackendCapabilities,
    VectorStoreManager,
    _build_embed_model,
)


class _FakeHuggingFaceEmbedding:
    """Test double for HuggingFaceEmbedding."""

    init_count = 0

    def __init__(self, model_name: str, embed_batch_size: int) -> None:
        type(self).init_count += 1
        self.model_name = model_name
        self.embed_batch_size = embed_batch_size


class _FakeEmbeddingModel:
    """Minimal embedding model test double."""

    def get_query_embedding(self, query: str) -> list[float]:
        return [0.1, float(len(query))]


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


class TestEmbeddingIdentityDiscovery:
    """Tests for vector payload embedding identity discovery."""

    def test_get_embedding_identities_returns_distinct_profiles(
        self,
        tmp_path,
    ) -> None:
        """Distinct embedding identities are deduplicated by profile."""
        manager = VectorStoreManager(persist_dir=tmp_path / "qdrant")
        manager._collection_exists = MagicMock(return_value=True)
        manager._get_client = MagicMock(return_value=MagicMock())

        manager._get_client.return_value.scroll.side_effect = [
            (
                [
                    SimpleNamespace(payload={"embedding_profile": "mlx:model-a"}),
                    SimpleNamespace(payload={"embedding_profile": "mlx:model-a"}),
                    SimpleNamespace(
                        payload={
                            "embedding_backend": "huggingface",
                            "embedding_model_name": "model-b",
                        }
                    ),
                ],
                None,
            )
        ]

        identities = manager.get_embedding_identities(dataset_name="obsidian")

        assert identities == [
            EmbeddingIdentity(backend="mlx", model_name="model-a"),
            EmbeddingIdentity(backend="huggingface", model_name="model-b"),
        ]
        scroll_call = manager._get_client.return_value.scroll.call_args.kwargs
        assert scroll_call["scroll_filter"] is not None

    def test_get_embedding_identities_returns_empty_when_collection_missing(
        self,
        tmp_path,
    ) -> None:
        """Missing collection returns no embedding identities."""
        manager = VectorStoreManager(persist_dir=tmp_path / "qdrant")
        manager._collection_exists = MagicMock(return_value=False)

        identities = manager.get_embedding_identities(dataset_name=None)

        assert identities == []


class TestEmbeddingIdentityStrategies:
    """Tests for capability-driven embedding identity strategy selection."""

    def test_native_strategy_has_no_ingest_identity_transforms(self, tmp_path) -> None:
        """Native identity backends skip payload identity ingest transforms."""
        manager = VectorStoreManager(
            persist_dir=tmp_path / "qdrant",
            capabilities=VectorBackendCapabilities(native_embedding_identity=True),
        )

        transforms = manager.build_ingest_transforms(embed_model=_FakeEmbeddingModel())

        assert transforms == []

    def test_native_strategy_skips_payload_identity_path(self, tmp_path) -> None:
        """Native identity capability bypasses payload identity discovery."""
        manager = VectorStoreManager(
            persist_dir=tmp_path / "qdrant",
            capabilities=VectorBackendCapabilities(native_embedding_identity=True),
        )
        vector_store = MagicMock()
        manager.get_vector_store = MagicMock(return_value=vector_store)
        manager._get_embed_model = MagicMock(return_value=_FakeEmbeddingModel())
        manager.get_embedding_identities = MagicMock(
            side_effect=AssertionError("payload discovery should not run")
        )
        vector_store.query.return_value = SimpleNamespace(
            ids=[],
            similarities=[],
            nodes=[],
        )

        manager.semantic_query(query="hello", top_k=5, dataset_name="obsidian")

        manager.get_embedding_identities.assert_not_called()

    def test_payload_strategy_discovers_embedding_identities(self, tmp_path) -> None:
        """Non-native capability uses payload identity strategy."""
        manager = VectorStoreManager(persist_dir=tmp_path / "qdrant")
        vector_store = MagicMock()
        manager.get_vector_store = MagicMock(return_value=vector_store)
        manager.get_embedding_identities = MagicMock(
            return_value=[EmbeddingIdentity(backend="mlx", model_name="model-a")]
        )
        manager.get_embed_model_for_identity = MagicMock(
            return_value=_FakeEmbeddingModel()
        )
        vector_store.query.return_value = SimpleNamespace(
            ids=["chunk-a"],
            similarities=[0.8],
            nodes=[SimpleNamespace(metadata={"source_doc_id": "obsidian:path/a.md"})],
        )

        hits = manager.semantic_query(query="hello", top_k=5, dataset_name="obsidian")

        manager.get_embedding_identities.assert_called_once_with(dataset_name="obsidian")
        assert len(hits) == 1
        assert hits[0].node_id == "chunk-a"
