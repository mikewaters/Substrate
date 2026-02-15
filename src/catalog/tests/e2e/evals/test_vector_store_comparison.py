"""E2E eval comparing Qdrant and Zvec vector retrieval behavior."""

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import pytest
from llama_index.core.embeddings import BaseEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from sqlalchemy import text

from catalog.core.settings import get_settings
from catalog.ingest.directory import SourceDirectoryConfig
from catalog.ingest.pipelines import DatasetIngestPipeline
from catalog.search.models import SearchCriteria, SearchResults
from catalog.search.service import SearchService
from catalog.store.session_context import use_session
from catalog.store.vector import VectorStoreManager

from ..conftest import E2EInfra


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


@dataclass(frozen=True)
class _BackendEvalResult:
    """Comparable backend evaluation outcome."""

    backend: str
    top_path: str | None
    timing_ms: float
    total_results: int
    qdrant_query_calls: int
    zvec_query_calls: int


def _configure_backend(
    monkeypatch: pytest.MonkeyPatch,
    backend: str,
    output_dir: Path,
) -> None:
    """Configure environment for a single active vector backend."""
    monkeypatch.setenv("IDX_VECTOR_DB__BACKEND", backend)
    monkeypatch.setenv("IDX_RAG__EXPANSION_ENABLED", "false")

    if backend == "zvec":
        monkeypatch.setenv("IDX_VECTOR_DB__ENABLE_EXPERIMENTAL_ZVEC", "true")
        monkeypatch.setenv("IDX_ZVEC__INDEX_PATH", str(output_dir / "zvec-index.json"))
    else:
        monkeypatch.delenv("IDX_VECTOR_DB__ENABLE_EXPERIMENTAL_ZVEC", raising=False)
        monkeypatch.delenv("IDX_ZVEC__INDEX_PATH", raising=False)

    get_settings.cache_clear()


def _ingest_dataset(
    dataset_name: str,
    docs_dir: Path,
    embed_model: BaseEmbedding,
) -> None:
    """Ingest a two-document dataset for backend comparison."""
    with patch(
        "catalog.ingest.pipelines.get_embed_model",
        return_value=embed_model,
    ):
        pipeline = DatasetIngestPipeline()
        ingest_result = pipeline.ingest_dataset(
            SourceDirectoryConfig(
                source_path=docs_dir,
                dataset_name=dataset_name,
                patterns=["**/*.md"],
            )
        )
    assert ingest_result.documents_created == 2
    assert ingest_result.documents_failed == 0


def _search_vector_only(
    e2e: E2EInfra,
    dataset_name: str,
    query: str,
    embed_model: BaseEmbedding,
    backend: str,
) -> tuple[SearchResults, int, int]:
    """Run vector-only search and return results with backend call counts."""
    qdrant_query_calls = 0
    zvec_query_calls = 0

    original_qdrant_query = QdrantVectorStore.query
    original_zvec_query = VectorStoreManager._query_zvec

    def _query_qdrant_spy(self, *args, **kwargs):
        nonlocal qdrant_query_calls
        qdrant_query_calls += 1
        return original_qdrant_query(self, *args, **kwargs)

    def _query_zvec_spy(self, *args, **kwargs):
        nonlocal zvec_query_calls
        zvec_query_calls += 1
        return original_zvec_query(self, *args, **kwargs)

    with e2e.session() as session:
        with use_session(session):
            with patch.object(QdrantVectorStore, "query", _query_qdrant_spy):
                with patch.object(VectorStoreManager, "_query_zvec", _query_zvec_spy):
                    with patch.object(
                        VectorStoreManager,
                        "get_embed_model_for_identity",
                        return_value=embed_model,
                    ):
                        service = SearchService(session)
                        search_results = service.search(
                            SearchCriteria(
                                query=query,
                                mode="vector",
                                dataset_name=dataset_name,
                                limit=5,
                            )
                        )
                        assert service._ensure_vector_manager().vector_backend == backend

    return search_results, qdrant_query_calls, zvec_query_calls


class TestVectorStoreComparisonEval:
    """Eval coverage comparing Qdrant and Zvec on the same task."""

    def _run_backend_round_trip(
        self,
        backend: str,
        e2e: E2EInfra,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> _BackendEvalResult:
        """Run ingest + vector query for one backend and capture metrics."""
        dataset_name = f"{backend}-eval-vault"
        docs = tmp_path / f"{backend}-eval-docs"
        docs.mkdir()
        (docs / "target.md").write_text(
            "# Target\n\nOAuth2 authentication token exchange flow.\n",
            encoding="utf-8",
        )
        (docs / "distractor.md").write_text(
            "# Distractor\n\nGardening soil composition and watering schedule.\n",
            encoding="utf-8",
        )

        _configure_backend(monkeypatch=monkeypatch, backend=backend, output_dir=e2e.output_dir)

        embed_model = _SemanticMockEmbedding(embed_dim=384)
        _ingest_dataset(
            dataset_name=dataset_name,
            docs_dir=docs,
            embed_model=embed_model,
        )
        search_results, qdrant_calls, zvec_calls = _search_vector_only(
            e2e=e2e,
            dataset_name=dataset_name,
            query="oauth2 authentication",
            embed_model=embed_model,
            backend=backend,
        )

        assert all(r.dataset_name == dataset_name for r in search_results.results)
        top_path = search_results.results[0].path if search_results.results else None
        return _BackendEvalResult(
            backend=backend,
            top_path=top_path,
            timing_ms=search_results.timing_ms,
            total_results=len(search_results.results),
            qdrant_query_calls=qdrant_calls,
            zvec_query_calls=zvec_calls,
        )

    def test_accuracy_and_latency_comparison_between_backends(
        self,
        e2e: E2EInfra,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Compare top-hit accuracy and latency metrics across vector stores."""
        with e2e.session() as session:
            dataset_count = session.execute(
                text("SELECT COUNT(*) FROM datasets")
            ).scalar_one()
        assert dataset_count == 0

        qdrant_eval = self._run_backend_round_trip(
            backend="qdrant",
            e2e=e2e,
            tmp_path=tmp_path,
            monkeypatch=monkeypatch,
        )
        zvec_eval = self._run_backend_round_trip(
            backend="zvec",
            e2e=e2e,
            tmp_path=tmp_path,
            monkeypatch=monkeypatch,
        )

        assert qdrant_eval.total_results >= 1
        assert zvec_eval.total_results >= 1
        assert qdrant_eval.top_path == "target.md"
        assert zvec_eval.top_path == "target.md"
        assert qdrant_eval.top_path == zvec_eval.top_path

        assert qdrant_eval.qdrant_query_calls >= 1
        assert qdrant_eval.zvec_query_calls == 0
        assert zvec_eval.zvec_query_calls >= 1
        assert zvec_eval.qdrant_query_calls == 0

        assert qdrant_eval.timing_ms >= 0.0
        assert zvec_eval.timing_ms >= 0.0
        print(
            "vector_store_latency_ms "
            f"qdrant={qdrant_eval.timing_ms:.3f} "
            f"zvec={zvec_eval.timing_ms:.3f}"
        )

