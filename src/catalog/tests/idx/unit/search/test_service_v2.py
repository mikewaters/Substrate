"""Tests for catalog.search.service_v2 module."""

from unittest.mock import MagicMock, patch

import pytest

from catalog.search.models import SearchCriteria, SearchResult, SearchResults
from catalog.search.service_v2 import SearchServiceV2


class TestSearchServiceV2Init:
    """Tests for SearchServiceV2 initialization."""

    def test_init_stores_session(self) -> None:
        """Service stores session reference."""
        mock_session = MagicMock()
        service = SearchServiceV2(mock_session)
        assert service.session is mock_session

    def test_init_loads_settings(self) -> None:
        """Service loads RAGv2Settings."""
        mock_session = MagicMock()
        service = SearchServiceV2(mock_session)
        assert service._settings is not None
        assert service._settings.chunk_size == 800  # Default value

    def test_lazy_initialization(self) -> None:
        """Components are not loaded on init."""
        mock_session = MagicMock()
        service = SearchServiceV2(mock_session)
        assert service._cache is None
        assert service._query_expander is None
        assert service._hybrid_retriever_factory is None
        assert service._cached_reranker is None


class TestSearchServiceV2Cache:
    """Tests for LLMCache integration."""

    def test_cache_property_creates_cache(self) -> None:
        """cache property lazily creates LLMCache."""
        mock_session = MagicMock()
        service = SearchServiceV2(mock_session)

        with patch("catalog.search.service_v2.LLMCache") as mock_cache_cls:
            mock_cache_cls.return_value = MagicMock()
            cache = service.cache
            mock_cache_cls.assert_called_once()
            assert cache is not None

    def test_cache_property_caches_instance(self) -> None:
        """cache property returns same instance on subsequent calls."""
        mock_session = MagicMock()
        service = SearchServiceV2(mock_session)

        with patch("catalog.search.service_v2.LLMCache") as mock_cache_cls:
            mock_instance = MagicMock()
            mock_cache_cls.return_value = mock_instance

            cache1 = service.cache
            cache2 = service.cache

            mock_cache_cls.assert_called_once()
            assert cache1 is cache2


class TestSearchServiceV2LazyLoading:
    """Tests for lazy component loading."""

    def test_ensure_query_expander_loads_once(self) -> None:
        """Query expander is loaded once."""
        mock_session = MagicMock()
        service = SearchServiceV2(mock_session)

        with patch(
            "catalog.search.query_expansion.QueryExpansionTransform"
        ) as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            # First call loads
            expander1 = service._ensure_query_expander()
            # Second call returns cached
            expander2 = service._ensure_query_expander()

            # Should only be called once (caching works)
            assert expander1 is expander2

    def test_ensure_hybrid_retriever_loads_once(self) -> None:
        """Hybrid retriever is loaded once."""
        mock_session = MagicMock()
        service = SearchServiceV2(mock_session)

        with patch("catalog.search.hybrid_v2.HybridRetrieverV2") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            retriever1 = service._ensure_hybrid_retriever()
            retriever2 = service._ensure_hybrid_retriever()

            assert retriever1 is retriever2


class TestSearchServiceV2Search:
    """Tests for search method."""

    @pytest.fixture
    def mock_service(self) -> SearchServiceV2:
        """Create service with mocked components."""
        mock_session = MagicMock()
        service = SearchServiceV2(mock_session)
        return service

    def test_search_fts_mode(self, mock_service: SearchServiceV2) -> None:
        """FTS mode dispatches to search_fts."""
        mock_results = [
            SearchResult(
                path="test.md",
                dataset_name="test",
                score=1.0,
                chunk_text="test content",
                scores={"retrieval": 1.0},
            )
        ]

        with patch.object(
            mock_service, "search_fts"
        ) as mock_fts:
            mock_fts.return_value = SearchResults(
                results=mock_results,
                query="test",
                mode="fts",
                total_candidates=1,
                timing_ms=0,
            )

            criteria = SearchCriteria(query="test", mode="fts", limit=10)
            results = mock_service.search(criteria)

            mock_fts.assert_called_once()
            assert results.mode == "fts"

    def test_search_vector_mode(self, mock_service: SearchServiceV2) -> None:
        """Vector mode dispatches to search_vector."""
        mock_results = [
            SearchResult(
                path="test.md",
                dataset_name="test",
                score=1.0,
                chunk_text="test content",
                scores={"retrieval": 1.0},
            )
        ]

        with patch.object(mock_service, "search_vector") as mock_vector:
            mock_vector.return_value = SearchResults(
                results=mock_results,
                query="test",
                mode="vector",
                total_candidates=1,
                timing_ms=0,
            )

            criteria = SearchCriteria(query="test", mode="vector", limit=10)
            results = mock_service.search(criteria)

            mock_vector.assert_called_once()
            assert results.mode == "vector"

    def test_search_hybrid_mode_default(self, mock_service: SearchServiceV2) -> None:
        """Hybrid mode is used by default for non-fts."""
        mock_results = [
            SearchResult(
                path="test.md",
                dataset_name="test",
                score=1.0,
                chunk_text="test content",
                scores={"retrieval": 1.0},
            )
        ]

        with patch.object(mock_service, "search_hybrid") as mock_hybrid:
            mock_hybrid.return_value = SearchResults(
                results=mock_results,
                query="test",
                mode="hybrid",
                total_candidates=1,
                timing_ms=0,
            )

            criteria = SearchCriteria(query="test", mode="hybrid", limit=10)
            results = mock_service.search(criteria)

            mock_hybrid.assert_called_once()
            assert results.mode == "hybrid"


class TestSearchServiceV2TopRankBonus:
    """Tests for top-rank bonus application."""

    @pytest.fixture
    def service(self) -> SearchServiceV2:
        """Create service."""
        mock_session = MagicMock()
        return SearchServiceV2(mock_session)

    def test_applies_rank_1_bonus(self, service: SearchServiceV2) -> None:
        """Rank 1 result gets rank_1_bonus."""
        results = SearchResults(
            results=[
                SearchResult(
                    path="a.md",
                    dataset_name="test",
                    score=1.0,
                    chunk_text="a",
                    scores={"retrieval": 1.0},
                ),
                SearchResult(
                    path="b.md",
                    dataset_name="test",
                    score=0.9,
                    chunk_text="b",
                    scores={"retrieval": 0.9},
                ),
            ],
            query="test",
            mode="hybrid",
            total_candidates=2,
            timing_ms=0,
        )

        modified = service._apply_top_rank_bonus(results)

        # First result should have rank_1_bonus (0.05 default)
        assert modified.results[0].scores.get("bonus") == 0.05

    def test_applies_rank_23_bonus(self, service: SearchServiceV2) -> None:
        """Ranks 2-3 get rank_23_bonus."""
        results = SearchResults(
            results=[
                SearchResult(
                    path=f"{i}.md",
                    dataset_name="test",
                    score=1.0 - i * 0.1,
                    chunk_text=str(i),
                    scores={"retrieval": 1.0 - i * 0.1},
                )
                for i in range(4)
            ],
            query="test",
            mode="hybrid",
            total_candidates=4,
            timing_ms=0,
        )

        modified = service._apply_top_rank_bonus(results)

        # Rank 1: rank_1_bonus
        assert modified.results[0].scores.get("bonus") == 0.05
        # Ranks 2-3: rank_23_bonus
        assert modified.results[1].scores.get("bonus") == 0.02
        assert modified.results[2].scores.get("bonus") == 0.02
        # Rank 4+: no bonus
        assert modified.results[3].scores.get("bonus") == 0.0


class TestSearchServiceV2NodeConversion:
    """Tests for node-to-SearchResult conversion."""

    @pytest.fixture
    def service(self) -> SearchServiceV2:
        """Create service."""
        mock_session = MagicMock()
        return SearchServiceV2(mock_session)

    def test_converts_node_with_source_doc_id(self, service: SearchServiceV2) -> None:
        """Converts node with source_doc_id metadata."""
        from llama_index.core.schema import NodeWithScore, TextNode

        node = TextNode(
            id_="test",
            text="content",
            metadata={"source_doc_id": "dataset:path/to/file.md"},
        )
        nodes = [NodeWithScore(node=node, score=0.9)]

        results = service._nodes_to_search_results(nodes)

        assert len(results) == 1
        assert results[0].dataset_name == "dataset"
        assert results[0].path == "path/to/file.md"
        assert results[0].score == 0.9

    def test_converts_node_with_separate_metadata(
        self, service: SearchServiceV2
    ) -> None:
        """Converts node with separate dataset_name and path."""
        from llama_index.core.schema import NodeWithScore, TextNode

        node = TextNode(
            id_="test",
            text="content",
            metadata={
                "dataset_name": "mydata",
                "file_path": "notes.md",
            },
        )
        nodes = [NodeWithScore(node=node, score=0.8)]

        results = service._nodes_to_search_results(nodes)

        assert len(results) == 1
        assert results[0].dataset_name == "mydata"
        assert results[0].path == "notes.md"


class TestSearchV2ConvenienceFunction:
    """Tests for search_v2 convenience function."""

    def test_search_v2_creates_session_and_service(self) -> None:
        """search_v2 handles session management."""
        from catalog.search.service_v2 import search_v2

        with patch("catalog.store.database.get_session") as mock_get_session:
            with patch("catalog.store.session_context.use_session"):
                mock_session = MagicMock()
                mock_get_session.return_value.__enter__ = MagicMock(
                    return_value=mock_session
                )
                mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

                with patch.object(
                    SearchServiceV2, "search"
                ) as mock_search:
                    mock_search.return_value = SearchResults(
                        results=[],
                        query="test",
                        mode="hybrid",
                        total_candidates=0,
                        timing_ms=0,
                    )

                    criteria = SearchCriteria(query="test")
                    search_v2(criteria)

                    mock_search.assert_called_once_with(criteria)
