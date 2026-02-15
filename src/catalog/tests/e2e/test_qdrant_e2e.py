"""End-to-end test for Qdrant vector retrieval.

Flow:
1. Assert no datasets exist.
2. Create a test-owned dataset directory.
3. Ingest through production pipeline using Qdrant.
4. Run vector-only search via Qdrant and validate results.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from llama_index.core.embeddings import BaseEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from sqlalchemy import text

from catalog.core.settings import get_settings
from catalog.ingest.directory import SourceDirectoryConfig
from catalog.ingest.pipelines import DatasetIngestPipeline
from catalog.search.models import SearchCriteria
from catalog.search.service import SearchService
from catalog.store.session_context import use_session
from catalog.store.vector import VectorStoreManager

from .conftest import E2EInfra


class _SemanticMockEmbedding(BaseEmbedding):
    """Deterministic embedding model with separable topic vectors."""

    embed_dim: int = 384

    def __init__(self, embed_dim: int = 384) -> None:
        super().__init__(model_name="semantic-mock", embed_batch_size=16)
        self.embed_dim = embed_dim

    def _target_vector(self) -> list[float]:
        return [1.0] + [0.0] * (self.embed_dim - 1)

    def _distractor_vector(self) -> list[float]:
        return [0.0, 1.0] + [0.0] * (self.embed_dim - 2)

    def _encode(self, text: str) -> list[float]:
        lowered = text.lower()
        if "oauth2" in lowered or "authentication" in lowered or "token" in lowered:
            return self._target_vector()
        return self._distractor_vector()

    def _get_text_embedding(self, text: str) -> list[float]:
        return self._encode(text)

    def _get_query_embedding(self, query: str) -> list[float]:
        return self._encode(query)

    async def _aget_text_embedding(self, text: str) -> list[float]:
        return self._get_text_embedding(text)

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return self._get_query_embedding(query)


class TestQdrantEndToEnd:
    """End-to-end Qdrant query path after real ingestion."""

    def test_ingest_then_vector_search_uses_qdrant_backend(
        self,
        e2e: E2EInfra,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ingest dataset, query in vector-only mode, and verify Qdrant was used."""
        dataset_name = "qdrant-e2e-vault"

        with e2e.session() as session:
            dataset_count = session.execute(
                text("SELECT COUNT(*) FROM datasets")
            ).scalar_one()
        assert dataset_count == 0

        docs = tmp_path / "qdrant-e2e-docs"
        docs.mkdir()
        (docs / "target.md").write_text(
            "# Target\n\nOAuth2 authentication token exchange flow.\n",
            encoding="utf-8",
        )
        (docs / "distractor.md").write_text(
            "# Distractor\n\nGardening soil composition and watering schedule.\n",
            encoding="utf-8",
        )

        monkeypatch.setenv("IDX_VECTOR_DB__BACKEND", "qdrant")
        monkeypatch.delenv("IDX_VECTOR_DB__ENABLE_EXPERIMENTAL_ZVEC", raising=False)
        monkeypatch.setenv("IDX_RAG__EXPANSION_ENABLED", "false")
        get_settings.cache_clear()

        embed_model = _SemanticMockEmbedding(embed_dim=384)
        with patch(
            "catalog.ingest.pipelines.get_embed_model",
            return_value=embed_model,
        ):
            pipeline = DatasetIngestPipeline()
            ingest_result = pipeline.ingest_dataset(
                SourceDirectoryConfig(
                    source_path=docs,
                    dataset_name=dataset_name,
                    patterns=["**/*.md"],
                )
            )
        assert ingest_result.documents_created == 2
        assert ingest_result.documents_failed == 0

        qdrant_query_calls = 0
        original_query_qdrant = QdrantVectorStore.query

        def _query_qdrant_spy(self, *args, **kwargs):
            nonlocal qdrant_query_calls
            qdrant_query_calls += 1
            return original_query_qdrant(self, *args, **kwargs)

        with e2e.session() as session:
            with use_session(session):
                with patch.object(
                    QdrantVectorStore,
                    "query",
                    _query_qdrant_spy,
                ):
                    with patch.object(
                        VectorStoreManager,
                        "get_embed_model_for_identity",
                        return_value=embed_model,
                    ):
                        service = SearchService(session)
                        search_results = service.search(
                            SearchCriteria(
                                query="oauth2 authentication",
                                mode="vector",
                                dataset_name=dataset_name,
                                limit=5,
                            )
                        )
                        assert service._ensure_vector_manager().vector_backend == "qdrant"

        assert qdrant_query_calls >= 1
        assert len(search_results.results) >= 1
        assert search_results.results[0].path == "target.md"
        assert all(r.dataset_name == dataset_name for r in search_results.results)
        assert search_results.timing_ms >= 0.0

    def test_query_uses_stored_embedding_profile_when_runtime_config_differs(
        self,
        e2e: E2EInfra,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Query-time model selection uses stored profile, not current config profile."""
        dataset_name = "qdrant-e2e-provenance-vault"

        with e2e.session() as session:
            dataset_count = session.execute(
                text("SELECT COUNT(*) FROM datasets")
            ).scalar_one()
        assert dataset_count == 0

        docs = tmp_path / "qdrant-e2e-provenance-docs"
        docs.mkdir()
        (docs / "target.md").write_text(
            "# Target\n\nOAuth2 authentication token exchange flow.\n",
            encoding="utf-8",
        )
        (docs / "distractor.md").write_text(
            "# Distractor\n\nGardening soil composition and watering schedule.\n",
            encoding="utf-8",
        )

        # Ingest identity (stored): huggingface:semantic-mock
        monkeypatch.setenv("IDX_VECTOR_DB__BACKEND", "qdrant")
        monkeypatch.delenv("IDX_VECTOR_DB__ENABLE_EXPERIMENTAL_ZVEC", raising=False)
        monkeypatch.setenv("IDX_EMBEDDING__BACKEND", "huggingface")
        monkeypatch.setenv("IDX_EMBEDDING__MODEL_NAME", "ingest-config-model")
        monkeypatch.setenv("IDX_RAG__EXPANSION_ENABLED", "false")
        get_settings.cache_clear()

        embed_model = _SemanticMockEmbedding(embed_dim=384)
        with patch(
            "catalog.ingest.pipelines.get_embed_model",
            return_value=embed_model,
        ):
            pipeline = DatasetIngestPipeline()
            ingest_result = pipeline.ingest_dataset(
                SourceDirectoryConfig(
                    source_path=docs,
                    dataset_name=dataset_name,
                    patterns=["**/*.md"],
                )
            )
        assert ingest_result.documents_created == 2
        assert ingest_result.documents_failed == 0

        # Runtime configured identity differs from stored profile.
        monkeypatch.setenv("IDX_EMBEDDING__BACKEND", "mlx")
        monkeypatch.setenv("IDX_EMBEDDING__MODEL_NAME", "query-config-model")
        get_settings.cache_clear()

        requested_profiles: list[str] = []

        def _model_for_identity(identity):
            requested_profiles.append(identity.profile)
            return embed_model

        with e2e.session() as session:
            with use_session(session):
                with patch.object(
                    VectorStoreManager,
                    "get_embed_model_for_identity",
                    side_effect=_model_for_identity,
                ):
                    service = SearchService(session)
                    search_results = service.search(
                        SearchCriteria(
                            query="oauth2 authentication",
                            mode="vector",
                            dataset_name=dataset_name,
                            limit=5,
                        )
                    )
                    assert service._ensure_vector_manager().vector_backend == "qdrant"

        assert len(search_results.results) >= 1
        assert requested_profiles == ["huggingface:semantic-mock"]
