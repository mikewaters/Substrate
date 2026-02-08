"""End-to-end tests for the Catalog ingest-search pipeline.

Each test provisions real, persistent infrastructure (SQLite + file-based
Qdrant) via the ``e2e`` fixture. Databases survive after the run at
``tests/e2e/.output/<test_name>/`` for manual inspection.

Only the embedding model is mocked (for speed). Everything else runs
through production code paths with no patching.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import Field
from sqlalchemy import text

from catalog.ingest.directory import SourceDirectoryConfig
from catalog.ingest.pipelines import DatasetIngestPipeline
from catalog.integrations.obsidian import VaultSchema
from catalog.integrations.obsidian.source import SourceObsidianConfig
from catalog.search.fts import FTSSearch
from catalog.search.models import SearchCriteria
from catalog.search.service import SearchService
from catalog.store.database import get_session
from catalog.store.repositories import DocumentLinkRepository
from catalog.store.session_context import use_session

from .conftest import E2EInfra


# ---------------------------------------------------------------------------
# Vault schema for ontology test
# ---------------------------------------------------------------------------

class SampleVaultSchema(VaultSchema):
    """Schema for the ontology test vault frontmatter."""

    tags: list[str] = Field(default_factory=list, json_schema_extra={"maps_to": "tags"})
    note_type: str | None = Field(None, json_schema_extra={"maps_to": "categories"})
    author: str | None = Field(None, json_schema_extra={"maps_to": "author"})
    aliases: list[str] = Field(default_factory=list)
    cssclass: str | None = None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestIngestAndSearch:
    """Ingest documents and validate FTS search results."""

    def test_ingest_and_fts_search(
        self,
        e2e: E2EInfra,
        sample_vault: Path,
    ) -> None:
        """Ingest a small vault via directory source and verify FTS works."""
        pipeline = DatasetIngestPipeline()
        config = SourceDirectoryConfig(
            source_path=sample_vault,
            dataset_name="test-vault",
            patterns=["**/*.md"],
        )

        result = pipeline.ingest_dataset(config)

        assert result.documents_created == 4
        assert result.documents_failed == 0

        # Search for Python content
        with e2e.session() as session:
            with use_session(session):
                search = FTSSearch()
                results = search.search(
                    SearchCriteria(query="python", limit=10)
                )

        assert len(results.results) >= 2  # note1.md and project1.md
        paths = {r.path for r in results.results}
        assert any("note1" in p for p in paths) or any("project1" in p for p in paths)

    def test_fts_keyword_search(
        self,
        e2e: E2EInfra,
        hybrid_vault: Path,
    ) -> None:
        """Ingest Obsidian vault and verify keyword search finds expected doc."""
        pipeline = DatasetIngestPipeline()
        config = SourceObsidianConfig(
            source_path=hybrid_vault,
            dataset_name="test-vault",
        )
        pipeline.ingest_dataset(config)

        with e2e.session() as session:
            with use_session(session):
                search = FTSSearch()
                results = search.search(
                    SearchCriteria(query="OAuth2", mode="fts", limit=10)
                )

        assert len(results.results) >= 1
        paths = [r.path for r in results.results]
        assert any("auth" in p.lower() for p in paths)


class TestHybridSearch:
    """Hybrid search combining FTS and vector retrieval."""

    def test_hybrid_search_returns_results(
        self,
        e2e: E2EInfra,
        hybrid_vault: Path,
    ) -> None:
        """Hybrid search with real Qdrant returns RRF-scored results."""
        pipeline = DatasetIngestPipeline()
        config = SourceObsidianConfig(
            source_path=hybrid_vault,
            dataset_name="test-vault",
        )
        pipeline.ingest_dataset(config)

        with e2e.session() as session:
            with use_session(session):
                service = SearchService(session)
                search_results = service.search(
                    SearchCriteria(
                        query="authentication",
                        mode="hybrid",
                        limit=10,
                    )
                )

        assert len(search_results.results) >= 1
        assert all(isinstance(r.score, float) for r in search_results.results)

    @pytest.mark.asyncio
    async def test_full_pipeline_ingest_search_rerank(
        self,
        e2e: E2EInfra,
        sample_docs: Path,
    ) -> None:
        """Full flow: ingest -> hybrid search -> LLM rerank (LLM mocked)."""
        from catalog.llm.reranker import Reranker

        # 1. Ingest
        pipeline = DatasetIngestPipeline()
        config = SourceDirectoryConfig(
            source_path=sample_docs,
            dataset_name="test-vault",
            patterns=["**/*.md"],
        )
        result = pipeline.ingest_dataset(config)
        assert result.documents_created == 3

        # 2. Hybrid search via SearchService (real Qdrant + FTS, mock embedding)
        with e2e.session() as session:
            with use_session(session):
                service = SearchService(session)
                search_results = service.search(
                    SearchCriteria(
                        query="authentication",
                        mode="hybrid",
                        limit=10,
                    )
                )

        assert len(search_results.results) >= 1

        result_list = search_results.results

        # Add chunk text for reranker if missing
        for res in result_list:
            if not res.chunk_text:
                res.chunk_text = f"Content from {res.path}"

        # 3. Rerank with mocked LLM
        mock_provider = MagicMock()
        mock_provider.generate = AsyncMock(
            side_effect=["Yes"] * len(result_list)
        )

        reranker = Reranker(provider=mock_provider)
        reranked = await reranker.rerank("authentication", result_list)

        # 4. Verify reranked results
        assert len(reranked) >= 1

        for result in reranked:
            assert result.path
            assert result.dataset_name
            assert "rerank" in result.scores
            assert "blend_weight" in result.scores

        # Results should be sorted by score descending
        scores = [r.score for r in reranked]
        assert scores == sorted(scores, reverse=True)


class TestObsidianLinks:
    """Obsidian wikilink resolution through the full pipeline."""

    def test_backlinks_queryable(
        self,
        e2e: E2EInfra,
        linked_vault: Path,
    ) -> None:
        """Backlinks (incoming) are queryable after full pipeline ingestion."""
        pipeline = DatasetIngestPipeline()
        config = SourceObsidianConfig(
            source_path=linked_vault,
            dataset_name="link-test-vault",
        )
        pipeline.ingest_dataset(config)

        with e2e.session() as session:
            # Find note A's document ID
            row_a = session.execute(
                text("SELECT d.id FROM documents d WHERE d.path LIKE '%A.md'")
            ).fetchone()
            assert row_a is not None

            with use_session(session):
                link_repo = DocumentLinkRepository()
                incoming = link_repo.list_incoming(row_a[0])

            # B and D both link to A
            assert len(incoming) == 2


class TestFrontmatterOntology:
    """Frontmatter-to-ontology metadata through the full pipeline."""

    def test_frontmatter_ontology_metadata(
        self,
        e2e: E2EInfra,
        ontology_vault: Path,
    ) -> None:
        """Ingested vault has ontology-shaped metadata in the database."""
        pipeline = DatasetIngestPipeline()
        config = SourceObsidianConfig(
            source_path=ontology_vault,
            dataset_name="ontology-test-vault",
            ontology_spec=SampleVaultSchema,
        )
        result = pipeline.ingest_dataset(config)
        assert result.documents_created == 5

        with e2e.session() as session:
            rows = session.execute(
                text(
                    "SELECT d.path, r.title, r.description, d.metadata_json "
                    "FROM documents d JOIN resources r ON d.id = r.id "
                    "ORDER BY d.path"
                )
            ).fetchall()

        assert len(rows) == 5

        # All documents should have ontology-shaped metadata
        for row in rows:
            assert row.metadata_json is not None
            meta = json.loads(row.metadata_json)
            assert "title" in meta or "tags" in meta, (
                f"Missing ontology keys in {row.path}"
            )

        # Verify full_meta.md specifically
        full_meta_row = next(r for r in rows if "full_meta" in r.path)
        assert full_meta_row.title == "Full Metadata Note"
        assert full_meta_row.description == "A note with every ontology field populated."

        meta = json.loads(full_meta_row.metadata_json)
        assert meta["tags"] == ["python", "testing"]
        assert meta["categories"] == ["tutorial"]
        assert meta["author"] == "Mike"
        assert meta["extra"]["aliases"] == ["FMN", "Full Note"]
        assert meta["extra"]["cssclass"] == "wide"
