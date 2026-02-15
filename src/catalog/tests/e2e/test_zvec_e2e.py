"""End-to-end test for Zvec vector retrieval.

Flow:
1. Assert no datasets exist.
2. Create a test-owned dataset directory.
3. Ingest through production pipeline.
4. Build a local Zvec index from ingested vectors.
5. Run vector-only search via Zvec and validate results.
"""

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy import text

from catalog.core.settings import get_settings
from catalog.ingest.directory import SourceDirectoryConfig
from catalog.ingest.pipelines import DatasetIngestPipeline
from catalog.search.models import SearchCriteria
from catalog.search.service import SearchService
from catalog.store.session_context import use_session
from catalog.store.vector import VectorStoreManager

from .conftest import E2EInfra


def _rewrite_zvec_index_vectors(
    index_path: Path,
    target_source_doc_id_suffix: str,
) -> None:
    """Rewrite persisted Zvec vectors for deterministic query ranking."""
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    embedding_dict: dict[str, list[float]] = {
        str(node_id): [float(v) for v in vector]
        for node_id, vector in payload.get("embedding_dict", {}).items()
    }
    metadata_dict: dict[str, dict[str, Any]] = {
        str(node_id): (metadata if isinstance(metadata, dict) else {})
        for node_id, metadata in payload.get("metadata_dict", {}).items()
    }

    low_similarity_vector = [1.0 if i % 2 == 0 else -1.0 for i in range(384)]
    for node_id, metadata in metadata_dict.items():
        source_doc_id = str(metadata.get("source_doc_id", ""))
        is_target = source_doc_id.endswith(target_source_doc_id_suffix)
        embedding_dict[node_id] = [1.0] * 384 if is_target else low_similarity_vector

    payload["embedding_dict"] = embedding_dict
    index_path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


class TestZvecEndToEnd:
    """End-to-end Zvec query path after real ingestion."""

    def test_ingest_then_vector_search_uses_zvec_backend(
        self,
        e2e: E2EInfra,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ingest dataset, query in vector-only mode, and verify Zvec was used."""
        dataset_name = "zvec-e2e-vault"

        with e2e.session() as session:
            dataset_count = session.execute(
                text("SELECT COUNT(*) FROM datasets")
            ).scalar_one()
        assert dataset_count == 0

        docs = tmp_path / "zvec-e2e-docs"
        docs.mkdir()
        (docs / "target.md").write_text(
            "# Target\n\nOAuth2 authentication token exchange flow.\n",
            encoding="utf-8",
        )
        (docs / "distractor.md").write_text(
            "# Distractor\n\nGardening soil composition and watering schedule.\n",
            encoding="utf-8",
        )

        zvec_index_path = e2e.output_dir / "zvec-index.json"
        monkeypatch.setenv("IDX_VECTOR_DB__BACKEND", "zvec")
        monkeypatch.setenv("IDX_VECTOR_DB__ENABLE_EXPERIMENTAL_ZVEC", "true")
        monkeypatch.setenv("IDX_ZVEC__INDEX_PATH", str(zvec_index_path))
        monkeypatch.setenv("IDX_RAG__EXPANSION_ENABLED", "false")
        get_settings.cache_clear()

        with patch("catalog.ingest.pipelines.get_embed_model", return_value=e2e.embed_model):
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
        assert zvec_index_path.exists()

        _rewrite_zvec_index_vectors(
            index_path=zvec_index_path,
            target_source_doc_id_suffix=f"{dataset_name}:target.md",
        )

        zvec_query_calls = 0
        original_query_zvec = VectorStoreManager._query_zvec

        def _query_zvec_spy(self, *args: Any, **kwargs: Any):
            nonlocal zvec_query_calls
            zvec_query_calls += 1
            return original_query_zvec(self, *args, **kwargs)

        with e2e.session() as session:
            with use_session(session):
                with patch.object(VectorStoreManager, "_query_zvec", _query_zvec_spy):
                    with patch.object(
                        VectorStoreManager,
                        "get_embed_model_for_identity",
                        return_value=e2e.embed_model,
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
                        assert service._ensure_vector_manager().vector_backend == "zvec"

        assert zvec_query_calls >= 1
        assert len(search_results.results) >= 1
        assert search_results.results[0].path == "target.md"
        assert all(r.dataset_name == dataset_name for r in search_results.results)

    def test_query_uses_stored_embedding_profile_when_runtime_config_differs(
        self,
        e2e: E2EInfra,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Query-time Zvec model selection uses stored profile over runtime config."""
        dataset_name = "zvec-e2e-provenance-vault"

        with e2e.session() as session:
            dataset_count = session.execute(
                text("SELECT COUNT(*) FROM datasets")
            ).scalar_one()
        assert dataset_count == 0

        docs = tmp_path / "zvec-e2e-provenance-docs"
        docs.mkdir()
        (docs / "target.md").write_text(
            "# Target\n\nOAuth2 authentication token exchange flow.\n",
            encoding="utf-8",
        )
        (docs / "distractor.md").write_text(
            "# Distractor\n\nGardening soil composition and watering schedule.\n",
            encoding="utf-8",
        )

        zvec_index_path = e2e.output_dir / "zvec-index.json"
        monkeypatch.setenv("IDX_VECTOR_DB__BACKEND", "zvec")
        monkeypatch.setenv("IDX_VECTOR_DB__ENABLE_EXPERIMENTAL_ZVEC", "true")
        monkeypatch.setenv("IDX_ZVEC__INDEX_PATH", str(zvec_index_path))
        monkeypatch.setenv("IDX_EMBEDDING__BACKEND", "huggingface")
        monkeypatch.setenv("IDX_EMBEDDING__MODEL_NAME", "ingest-config-model")
        monkeypatch.setenv("IDX_RAG__EXPANSION_ENABLED", "false")
        get_settings.cache_clear()

        with patch("catalog.ingest.pipelines.get_embed_model", return_value=e2e.embed_model):
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
        assert zvec_index_path.exists()

        monkeypatch.setenv("IDX_EMBEDDING__BACKEND", "mlx")
        monkeypatch.setenv("IDX_EMBEDDING__MODEL_NAME", "query-config-model")
        get_settings.cache_clear()

        requested_profiles: list[str] = []
        zvec_query_calls = 0

        original_query_zvec = VectorStoreManager._query_zvec

        def _query_zvec_spy(self, *args: Any, **kwargs: Any):
            nonlocal zvec_query_calls
            zvec_query_calls += 1
            return original_query_zvec(self, *args, **kwargs)

        def _model_for_identity(identity):
            requested_profiles.append(identity.profile)
            return e2e.embed_model

        with e2e.session() as session:
            with use_session(session):
                with patch.object(VectorStoreManager, "_query_zvec", _query_zvec_spy):
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
                        assert service._ensure_vector_manager().vector_backend == "zvec"

        assert zvec_query_calls >= 1
        assert len(search_results.results) >= 1
        assert all(r.dataset_name == dataset_name for r in search_results.results)
        assert requested_profiles == ["huggingface:mock-embedding"]
