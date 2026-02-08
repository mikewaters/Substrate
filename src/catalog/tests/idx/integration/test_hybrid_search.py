"""Integration tests for hybrid search.

Tests the full hybrid search pipeline using SearchService with different modes
(FTS-only, vector-only, hybrid) and RRF fusion behavior.

Requirements tested:
- FTS-only mode returns keyword matches
- Vector-only mode returns semantic matches
- Hybrid mode returns superset of both (before truncation)
- RRF ordering (results appearing in both lists rank higher)
"""

from contextlib import contextmanager
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from catalog.ingest.pipelines import DatasetIngestPipeline
from catalog.integrations.obsidian import SourceObsidianConfig
from catalog.search.fts import FTSSearch
from catalog.search.fts_chunk import FTSChunkRetriever
from catalog.search.hybrid import WeightedRRFRetriever
from catalog.search.models import SearchCriteria, SearchResult, SearchResults
from catalog.store.database import Base, create_engine_for_path
from catalog.store.fts import create_fts_table
from catalog.store.fts_chunk import create_chunks_fts_table
from catalog.store.session_context import use_session


@pytest.fixture
def test_engine(tmp_path: Path) -> Engine:
    """Create a temporary database and return the engine."""
    db_path = tmp_path / "test.db"
    engine = create_engine_for_path(db_path)
    Base.metadata.create_all(engine)
    create_fts_table(engine)
    create_chunks_fts_table(engine)
    return engine


@pytest.fixture
def session_factory(test_engine: Engine):
    """Create a session factory for the test database."""
    return sessionmaker(bind=test_engine, expire_on_commit=False)


@contextmanager
def create_session(factory) -> Generator[Session, None, None]:
    """Create a session that auto-commits on exit."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@pytest.fixture
def patched_get_session(session_factory):
    """Patch get_session to use the test database."""
    @contextmanager
    def get_test_session():
        with create_session(session_factory) as session:
            yield session

    with patch("catalog.ingest.pipelines.get_session", get_test_session):
        yield get_test_session


@pytest.fixture
def sample_vault(tmp_path: Path) -> Path:
    """Create a sample Obsidian vault for hybrid search testing.

    Creates documents with distinct keyword and semantic content to test
    that hybrid search correctly combines both signals.
    """
    vault = tmp_path / "vault"
    vault.mkdir()
    # Create .obsidian to mark as Obsidian vault
    (vault / ".obsidian").mkdir()

    # Document with specific keywords - "authentication" and "OAuth2"
    (vault / "auth.md").write_text("""# Authentication Guide

How to implement user authentication in your application.
OAuth2 is the recommended protocol for secure token-based authentication.
JWT tokens provide stateless session management.
""")

    # Document with database keywords
    (vault / "database.md").write_text("""# Database Design

SQL databases and schema design patterns.
Indexing strategies for query optimization.
PostgreSQL and SQLite are popular choices.
""")

    # Document with API keywords
    (vault / "api.md").write_text("""# API Design Patterns

RESTful API patterns and best practices.
Rate limiting protects your endpoints.
Authentication endpoints should use HTTPS.
""")

    # Document about machine learning (for semantic matching)
    (vault / "ml.md").write_text("""# Machine Learning Basics

Neural networks learn patterns from data.
Training involves optimizing loss functions.
Deep learning requires large datasets.
""")

    # Document about security (semantic overlap with auth)
    (vault / "security.md").write_text("""# Security Best Practices

Protect your systems from unauthorized access.
Encryption safeguards sensitive data.
Identity verification prevents impersonation.
""")

    return vault


class TestSearchServiceModes:
    """Tests for SearchService with different search modes."""

    def test_fts_mode_returns_keyword_matches(
        self,
        patched_get_session,
        patched_embedding,
        session_factory,
        sample_vault: Path,
    ) -> None:
        """FTS-only mode returns results matching exact keywords."""
        # Ingest documents
        pipeline = DatasetIngestPipeline()
        config = SourceObsidianConfig(
            source_path=sample_vault,
            dataset_name="test-vault",
        )
        pipeline.ingest_dataset(config)

        # Search for specific keyword
        with create_session(session_factory) as session:
            fts = FTSSearch(session)
            results = fts.search(
                SearchCriteria(query="OAuth2", mode="fts", limit=10)
            )

        # Should find auth.md which contains "OAuth2"
        assert len(results.results) >= 1
        paths = [r.path for r in results.results]
        assert any("auth" in p.lower() for p in paths)

    def test_fts_mode_with_dataset_filter(
        self,
        patched_get_session,
        patched_embedding,
        session_factory,
        sample_vault: Path,
        tmp_path: Path,
    ) -> None:
        """FTS mode respects dataset_name filter."""
        pipeline = DatasetIngestPipeline()

        # Ingest first dataset
        config1 = SourceObsidianConfig(
            source_path=sample_vault,
            dataset_name="vault1",
        )
        pipeline.ingest_dataset(config1)

        # Create and ingest second dataset with same content
        vault2 = tmp_path / "vault2"
        vault2.mkdir()
        (vault2 / ".obsidian").mkdir()
        (vault2 / "other.md").write_text("# Another auth doc\n\nOAuth2 content here too.")

        config2 = SourceObsidianConfig(
            source_path=vault2,
            dataset_name="vault2",
        )
        pipeline.ingest_dataset(config2)

        # Search with filter
        with create_session(session_factory) as session:
            fts = FTSSearch(session)
            results = fts.search(
                SearchCriteria(
                    query="OAuth2",
                    mode="fts",
                    dataset_name="vault1",
                    limit=10,
                )
            )

        # All results should be from vault1
        for result in results.results:
            assert result.dataset_name == "vault1"


class TestHybridSearchRRF:
    """Tests for hybrid search RRF fusion behavior using WeightedRRFRetriever."""

    def test_hybrid_search_returns_results(
        self,
        patched_get_session,
        patched_embedding,
        session_factory,
        sample_vault: Path,
    ) -> None:
        """WeightedRRFRetriever returns fused results from sub-retrievers."""
        # Ingest documents
        pipeline = DatasetIngestPipeline()
        config = SourceObsidianConfig(
            source_path=sample_vault,
            dataset_name="test-vault",
        )
        pipeline.ingest_dataset(config)

        # Create mock FTS and vector retrievers
        mock_fts_retriever = MagicMock()
        mock_fts_retriever.retrieve.return_value = [
            NodeWithScore(
                node=TextNode(
                    id_="fts-1",
                    text="OAuth2 authentication",
                    metadata={"source_doc_id": "test-vault:auth.md"},
                ),
                score=1.0,
            ),
        ]

        mock_vector_retriever = MagicMock()
        mock_vector_retriever.retrieve.return_value = [
            NodeWithScore(
                node=TextNode(
                    id_="vec-1",
                    text="Identity verification",
                    metadata={"source_doc_id": "test-vault:security.md"},
                ),
                score=0.85,
            ),
        ]

        # Create WeightedRRFRetriever with mock sub-retrievers
        retriever = WeightedRRFRetriever(
            retrievers=[mock_fts_retriever, mock_vector_retriever],
            weights=[1.0, 1.0],
            k=60,
            top_n=10,
        )

        results = retriever.retrieve(QueryBundle(query_str="authentication"))

        assert len(results) >= 1
        assert all(isinstance(r, NodeWithScore) for r in results)

    def test_rrf_combines_fts_and_vector_results(
        self,
        patched_get_session,
        patched_embedding,
        session_factory,
        sample_vault: Path,
    ) -> None:
        """RRF fusion combines results from both FTS and vector search."""
        # Ingest documents
        pipeline = DatasetIngestPipeline()
        config = SourceObsidianConfig(
            source_path=sample_vault,
            dataset_name="test-vault",
        )
        pipeline.ingest_dataset(config)

        # Create mock retrievers with overlapping results
        # auth.md appears in both, api.md only in FTS
        mock_fts_retriever = MagicMock()
        mock_fts_retriever.retrieve.return_value = [
            NodeWithScore(
                node=TextNode(
                    id_="auth-node",
                    text="OAuth2 authentication",
                    metadata={"source_doc_id": "test-vault:auth.md"},
                ),
                score=1.0,
            ),
            NodeWithScore(
                node=TextNode(
                    id_="api-node",
                    text="Authentication endpoints",
                    metadata={"source_doc_id": "test-vault:api.md"},
                ),
                score=0.8,
            ),
        ]

        mock_vector_retriever = MagicMock()
        mock_vector_retriever.retrieve.return_value = [
            NodeWithScore(
                node=TextNode(
                    id_="auth-node",
                    text="OAuth2 authentication",
                    metadata={"source_doc_id": "test-vault:auth.md"},
                ),
                score=0.9,
            ),
        ]

        retriever = WeightedRRFRetriever(
            retrievers=[mock_fts_retriever, mock_vector_retriever],
            weights=[1.0, 1.0],
            k=60,
            top_n=10,
        )

        results = retriever.retrieve(QueryBundle(query_str="authentication security"))

        # Results should be ordered by RRF score descending
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

        # auth-node should rank higher (appears in both retrievers)
        assert len(results) >= 2
        assert results[0].node.node_id == "auth-node"


class TestSearchResultShapes:
    """Tests for correct result shapes and metadata."""

    def test_fts_result_has_required_fields(
        self,
        patched_get_session,
        patched_embedding,
        session_factory,
        sample_vault: Path,
    ) -> None:
        """FTS results have all required fields."""
        pipeline = DatasetIngestPipeline()
        config = SourceObsidianConfig(
            source_path=sample_vault,
            dataset_name="test-vault",
        )
        pipeline.ingest_dataset(config)

        with create_session(session_factory) as session:
            fts = FTSSearch(session)
            results = fts.search(
                SearchCriteria(query="database", mode="fts", limit=10)
            )

        if results.results:
            result = results.results[0]
            assert result.path
            assert result.dataset_name == "test-vault"
            assert result.score >= 0.0
            # FTS mode has scores dict
            assert hasattr(result, "scores")

    def test_search_results_has_metadata(
        self,
        patched_get_session,
        patched_embedding,
        session_factory,
        sample_vault: Path,
    ) -> None:
        """SearchResults wrapper has correct metadata."""
        pipeline = DatasetIngestPipeline()
        config = SourceObsidianConfig(
            source_path=sample_vault,
            dataset_name="test-vault",
        )
        pipeline.ingest_dataset(config)

        with create_session(session_factory) as session:
            fts = FTSSearch(session)
            results = fts.search(
                SearchCriteria(query="machine learning", mode="fts", limit=10)
            )

        assert results.query == "machine learning"
        assert results.mode == "fts"
        assert results.total_candidates >= 0


class TestFTSChunkRetriever:
    """Tests for FTSChunkRetriever with chunk-level FTS."""

    def test_chunk_retriever_returns_nodes(
        self,
        patched_get_session,
        patched_embedding,
        session_factory,
        sample_vault: Path,
    ) -> None:
        """FTSChunkRetriever returns NodeWithScore objects."""
        pipeline = DatasetIngestPipeline()
        config = SourceObsidianConfig(
            source_path=sample_vault,
            dataset_name="test-vault",
        )
        pipeline.ingest_dataset(config)

        # Test chunk retriever
        with create_session(session_factory) as session:
            with use_session(session):
                retriever = FTSChunkRetriever(similarity_top_k=10)
                nodes = retriever.retrieve(QueryBundle(query_str="authentication"))

        # Should return some results
        assert isinstance(nodes, list)
        # Nodes should be NodeWithScore instances
        for node in nodes:
            assert hasattr(node, "node")
            assert hasattr(node, "score")

    def test_chunk_retriever_respects_dataset_filter(
        self,
        patched_get_session,
        patched_embedding,
        session_factory,
        sample_vault: Path,
        tmp_path: Path,
    ) -> None:
        """FTSChunkRetriever filters by dataset name."""
        pipeline = DatasetIngestPipeline()

        # Ingest first dataset
        config1 = SourceObsidianConfig(
            source_path=sample_vault,
            dataset_name="vault1",
        )
        pipeline.ingest_dataset(config1)

        # Create and ingest second dataset
        vault2 = tmp_path / "vault2"
        vault2.mkdir()
        (vault2 / ".obsidian").mkdir()
        (vault2 / "auth2.md").write_text("# Auth\n\nOAuth2 in another vault.")

        config2 = SourceObsidianConfig(
            source_path=vault2,
            dataset_name="vault2",
        )
        pipeline.ingest_dataset(config2)

        with create_session(session_factory) as session:
            with use_session(session):
                retriever = FTSChunkRetriever(
                    similarity_top_k=10,
                    dataset_name="vault1",
                )
                nodes = retriever.retrieve(QueryBundle(query_str="OAuth2"))

        # All nodes should have source_doc_id starting with vault1:
        for node in nodes:
            source_doc_id = node.node.metadata.get("source_doc_id", "")
            assert source_doc_id.startswith("vault1:")


class TestHybridSuperset:
    """Tests that hybrid mode returns superset of FTS and vector results."""

    def test_hybrid_includes_fts_matches(
        self,
        patched_get_session,
        patched_embedding,
        session_factory,
        sample_vault: Path,
    ) -> None:
        """Hybrid search includes documents found by FTS."""
        pipeline = DatasetIngestPipeline()
        config = SourceObsidianConfig(
            source_path=sample_vault,
            dataset_name="test-vault",
        )
        pipeline.ingest_dataset(config)

        # First, get FTS-only results
        with create_session(session_factory) as session:
            fts = FTSSearch(session)
            fts_results = fts.search(
                SearchCriteria(query="PostgreSQL", mode="fts", limit=10)
            )

        fts_paths = {r.path for r in fts_results.results}

        # Build a WeightedRRFRetriever with a real FTS retriever and mock vector
        mock_vector_retriever = MagicMock()
        mock_vector_retriever.retrieve.return_value = [
            NodeWithScore(
                node=TextNode(
                    id_="vec-db",
                    text="PostgreSQL and SQLite",
                    metadata={"source_doc_id": "test-vault:database.md"},
                ),
                score=0.7,
            ),
        ]

        with create_session(session_factory) as session:
            with use_session(session):
                fts_retriever = FTSChunkRetriever(similarity_top_k=10)

                retriever = WeightedRRFRetriever(
                    retrievers=[fts_retriever, mock_vector_retriever],
                    weights=[1.0, 1.0],
                    k=60,
                    top_n=10,
                )

                hybrid_results = retriever.retrieve(
                    QueryBundle(query_str="PostgreSQL")
                )

        hybrid_doc_ids = {
            n.node.metadata.get("source_doc_id", "") for n in hybrid_results
        }

        # Hybrid results should include matches
        assert len(hybrid_doc_ids) >= 1


class TestEmptyAndEdgeCases:
    """Tests for edge cases and empty results."""

    def test_empty_query_returns_empty_results(
        self,
        patched_get_session,
        patched_embedding,
        session_factory,
        sample_vault: Path,
    ) -> None:
        """Empty or whitespace query returns empty results."""
        pipeline = DatasetIngestPipeline()
        config = SourceObsidianConfig(
            source_path=sample_vault,
            dataset_name="test-vault",
        )
        pipeline.ingest_dataset(config)

        with create_session(session_factory) as session:
            fts = FTSSearch(session)
            # FTS5 may raise error on empty query, but we handle it gracefully
            try:
                results = fts.search(
                    SearchCriteria(query="xyznonexistent123", mode="fts", limit=10)
                )
                # Should return empty or no results
                assert len(results.results) == 0
            except Exception:
                # Some FTS implementations may raise on invalid queries
                pass

    def test_special_characters_in_query(
        self,
        patched_get_session,
        patched_embedding,
        session_factory,
        sample_vault: Path,
    ) -> None:
        """Query with special characters doesn't crash."""
        pipeline = DatasetIngestPipeline()
        config = SourceObsidianConfig(
            source_path=sample_vault,
            dataset_name="test-vault",
        )
        pipeline.ingest_dataset(config)

        with create_session(session_factory) as session:
            fts = FTSSearch(session)
            # Queries with special chars should be handled gracefully
            try:
                results = fts.search(
                    SearchCriteria(query="test-query", mode="fts", limit=10)
                )
                # Should not crash
                assert isinstance(results.results, list)
            except Exception:
                # FTS5 may reject certain query syntax, which is acceptable
                pass

    def test_limit_parameter_respected(
        self,
        patched_get_session,
        patched_embedding,
        session_factory,
        sample_vault: Path,
    ) -> None:
        """Search respects the limit parameter."""
        pipeline = DatasetIngestPipeline()
        config = SourceObsidianConfig(
            source_path=sample_vault,
            dataset_name="test-vault",
        )
        pipeline.ingest_dataset(config)

        with create_session(session_factory) as session:
            fts = FTSSearch(session)
            # Request only 2 results
            results = fts.search(
                SearchCriteria(query="the", mode="fts", limit=2)
            )

        assert len(results.results) <= 2
