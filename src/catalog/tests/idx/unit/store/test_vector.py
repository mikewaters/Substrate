"""Tests for catalog.store.vector module."""

import json
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest

from catalog.core.settings import get_settings
from catalog.embedding.identity import (
    EMBEDDING_PROFILE_METADATA_KEY,
    EmbeddingIdentity,
)
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


class _FixedEmbeddingModel:
    """Embedding model test double with fixed query embedding."""

    def __init__(self, vector: list[float]) -> None:
        self._vector = vector

    def get_query_embedding(self, query: str) -> list[float]:
        return self._vector


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

    def test_get_embedding_identities_reads_zvec_local_metadata(
        self,
        tmp_path,
        monkeypatch,
    ) -> None:
        """Zvec identity discovery reads profile metadata from local index entries."""
        get_settings.cache_clear()
        index_path = tmp_path / "zvec-index.json"
        index_path.write_text(
            json.dumps(
                {
                    "collections": {
                        "catalog_vectors": [
                            {
                                "id": "chunk-a",
                                "vector": [1.0, 0.0],
                                "metadata": {
                                    "source_doc_id": "obsidian:path/a.md",
                                    EMBEDDING_PROFILE_METADATA_KEY: "mlx:model-a",
                                },
                            },
                            {
                                "id": "chunk-b",
                                "vector": [0.0, 1.0],
                                "metadata": {
                                    "source_doc_id": "obsidian:path/b.md",
                                    EMBEDDING_PROFILE_METADATA_KEY: "huggingface:model-b",
                                },
                            },
                            {
                                "id": "chunk-c",
                                "vector": [1.0, 1.0],
                                "metadata": {
                                    "source_doc_id": "archive:path/c.md",
                                    EMBEDDING_PROFILE_METADATA_KEY: "mlx:model-c",
                                },
                            },
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )

        monkeypatch.setenv("IDX_VECTOR_DB__BACKEND", "zvec")
        monkeypatch.setenv("IDX_VECTOR_DB__ENABLE_EXPERIMENTAL_ZVEC", "true")
        monkeypatch.setenv("IDX_ZVEC__INDEX_PATH", str(index_path))

        manager = VectorStoreManager(persist_dir=tmp_path / "vectors")

        identities = manager.get_embedding_identities(dataset_name="obsidian")

        assert identities == [
            EmbeddingIdentity(backend="mlx", model_name="model-a"),
            EmbeddingIdentity(backend="huggingface", model_name="model-b"),
        ]
        get_settings.cache_clear()


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

    def test_payload_strategy_prefers_stored_identity_over_runtime_config(
        self,
        tmp_path,
        monkeypatch,
    ) -> None:
        """Stored payload identity is used even when runtime config identity differs."""
        get_settings.cache_clear()
        monkeypatch.setenv("IDX_EMBEDDING__BACKEND", "mlx")
        monkeypatch.setenv("IDX_EMBEDDING__MODEL_NAME", "runtime-config-model")

        manager = VectorStoreManager(persist_dir=tmp_path / "qdrant")
        vector_store = MagicMock()
        manager.get_vector_store = MagicMock(return_value=vector_store)

        stored_identity = EmbeddingIdentity(
            backend="huggingface",
            model_name="stored-model",
        )
        manager.get_embedding_identities = MagicMock(return_value=[stored_identity])
        manager.get_embed_model_for_identity = MagicMock(
            return_value=_FakeEmbeddingModel()
        )
        vector_store.query.return_value = SimpleNamespace(
            ids=["chunk-a"],
            similarities=[0.9],
            nodes=[SimpleNamespace(metadata={"source_doc_id": "obsidian:path/a.md"})],
        )

        hits = manager.semantic_query(query="hello", top_k=5, dataset_name="obsidian")

        called_profiles = [
            call_args.args[0].profile
            for call_args in manager.get_embed_model_for_identity.call_args_list
        ]
        assert called_profiles == ["huggingface:stored-model"]
        assert called_profiles != [manager.get_configured_embedding_identity().profile]
        assert len(hits) == 1
        assert hits[0].metadata[EMBEDDING_PROFILE_METADATA_KEY] == "huggingface:stored-model"
        get_settings.cache_clear()


class TestZvecBackend:
    """Tests for latent Zvec backend wiring."""

    def test_semantic_query_uses_zvec_client(self, tmp_path, monkeypatch) -> None:
        """Zvec backend delegates semantic query to local index file."""
        get_settings.cache_clear()
        index_path = tmp_path / "zvec-index.json"
        index_payload = {
            "collections": {
                "catalog_vectors": [
                    {
                        "id": "chunk-z1",
                        "vector": [0.1, 5.0],
                        "metadata": {"source_doc_id": "obsidian:path/z.md"},
                    },
                    {
                        "id": "chunk-z2",
                        "vector": [0.9, 0.1],
                        "metadata": {"source_doc_id": "archive:path/z2.md"},
                    },
                ]
            }
        }
        index_path.write_text(json.dumps(index_payload), encoding="utf-8")

        monkeypatch.setenv("IDX_VECTOR_DB__BACKEND", "zvec")
        monkeypatch.setenv("IDX_VECTOR_DB__ENABLE_EXPERIMENTAL_ZVEC", "true")
        monkeypatch.setenv("IDX_ZVEC__INDEX_PATH", str(index_path))

        manager = VectorStoreManager(persist_dir=tmp_path / "vectors")
        manager.get_embed_model_for_identity = MagicMock(return_value=_FakeEmbeddingModel())

        hits = manager.semantic_query(query="hello", top_k=4, dataset_name="obsidian")

        assert manager.vector_backend == "zvec"
        assert manager.capabilities.native_embedding_identity is False
        assert manager._zvec_settings.index_path == index_path
        assert len(hits) == 1
        assert hits[0].node_id == "chunk-z1"
        assert hits[0].score == pytest.approx(1.0)
        assert hits[0].metadata[EMBEDDING_PROFILE_METADATA_KEY] == (
            manager.get_configured_embedding_identity().profile
        )

        get_settings.cache_clear()

    def test_semantic_query_uses_stored_embedding_provenance(
        self,
        tmp_path,
        monkeypatch,
    ) -> None:
        """Zvec search uses stored embedding provenance to select query-time model."""
        get_settings.cache_clear()
        index_path = tmp_path / "zvec-index.json"
        index_path.write_text(
            json.dumps(
                {
                    "collections": {
                        "catalog_vectors": [
                            {
                                "id": "chunk-a",
                                "vector": [1.0, 0.0],
                                "metadata": {
                                    "source_doc_id": "obsidian:path/a.md",
                                    EMBEDDING_PROFILE_METADATA_KEY: "mlx:model-a",
                                },
                            },
                            {
                                "id": "chunk-b",
                                "vector": [0.0, 1.0],
                                "metadata": {
                                    "source_doc_id": "obsidian:path/b.md",
                                    EMBEDDING_PROFILE_METADATA_KEY: "huggingface:model-b",
                                },
                            },
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )

        monkeypatch.setenv("IDX_VECTOR_DB__BACKEND", "zvec")
        monkeypatch.setenv("IDX_VECTOR_DB__ENABLE_EXPERIMENTAL_ZVEC", "true")
        monkeypatch.setenv("IDX_ZVEC__INDEX_PATH", str(index_path))

        manager = VectorStoreManager(persist_dir=tmp_path / "vectors")

        def _model_for_identity(identity: EmbeddingIdentity):
            if identity.profile == "mlx:model-a":
                return _FixedEmbeddingModel([1.0, 0.0])
            if identity.profile == "huggingface:model-b":
                return _FixedEmbeddingModel([0.0, 1.0])
            raise AssertionError(f"Unexpected identity: {identity.profile}")

        manager.get_embed_model_for_identity = MagicMock(side_effect=_model_for_identity)

        hits = manager.semantic_query(query="hello", top_k=2, dataset_name="obsidian")

        assert [hit.node_id for hit in hits] == ["chunk-a", "chunk-b"]
        assert hits[0].metadata[EMBEDDING_PROFILE_METADATA_KEY] == "mlx:model-a"
        assert hits[1].metadata[EMBEDDING_PROFILE_METADATA_KEY] == "huggingface:model-b"
        called_profiles = [
            call_args.args[0].profile
            for call_args in manager.get_embed_model_for_identity.call_args_list
        ]
        assert called_profiles == ["mlx:model-a", "huggingface:model-b"]
        get_settings.cache_clear()

    def test_zvec_backend_requires_explicit_enablement(self, tmp_path, monkeypatch) -> None:
        """Zvec backend is disabled by default until explicitly enabled."""
        get_settings.cache_clear()
        monkeypatch.setenv("IDX_VECTOR_DB__BACKEND", "zvec")
        monkeypatch.delenv("IDX_VECTOR_DB__ENABLE_EXPERIMENTAL_ZVEC", raising=False)

        with pytest.raises(ValueError, match="Zvec backend is disabled"):
            VectorStoreManager(persist_dir=tmp_path / "vectors")

        get_settings.cache_clear()
