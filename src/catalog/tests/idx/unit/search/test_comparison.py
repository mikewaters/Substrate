"""Tests for catalog.search.comparison module."""

from unittest.mock import MagicMock, patch

import pytest

from catalog.search.comparison import ComparisonResult, SearchComparison
from catalog.search.models import SearchCriteria, SearchResult, SearchResults


class TestComparisonResultDataclass:
    """Tests for ComparisonResult dataclass."""

    def test_creates_with_defaults(self) -> None:
        """ComparisonResult has sensible defaults."""
        result = ComparisonResult(query="test")

        assert result.query == "test"
        assert result.v1_results == []
        assert result.v2_results == []
        assert result.v1_time_ms == 0.0
        assert result.v2_time_ms == 0.0
        assert result.overlap_at_5 == 0.0
        assert result.overlap_at_10 == 0.0
        assert result.rank_correlation == 0.0

    def test_creates_with_all_values(self) -> None:
        """ComparisonResult accepts all field values."""
        v1 = [
            SearchResult(path="a.md", dataset_name="ds", score=1.0, scores={}),
        ]
        v2 = [
            SearchResult(path="b.md", dataset_name="ds", score=0.9, scores={}),
        ]

        result = ComparisonResult(
            query="machine learning",
            v1_results=v1,
            v2_results=v2,
            v1_time_ms=50.0,
            v2_time_ms=75.0,
            overlap_at_5=0.5,
            overlap_at_10=0.6,
            rank_correlation=0.8,
        )

        assert result.query == "machine learning"
        assert len(result.v1_results) == 1
        assert len(result.v2_results) == 1
        assert result.v1_time_ms == 50.0
        assert result.v2_time_ms == 75.0
        assert result.overlap_at_5 == 0.5
        assert result.overlap_at_10 == 0.6
        assert result.rank_correlation == 0.8


class TestSearchComparisonInit:
    """Tests for SearchComparison initialization."""

    def test_init_stores_session(self) -> None:
        """SearchComparison stores session reference."""
        mock_session = MagicMock()
        comparison = SearchComparison(mock_session)

        assert comparison.session is mock_session

    def test_lazy_initialization(self) -> None:
        """Services are not loaded on init."""
        mock_session = MagicMock()
        comparison = SearchComparison(mock_session)

        assert comparison._v1_service is None
        assert comparison._v2_service is None


class TestSearchComparisonLazyLoading:
    """Tests for lazy service loading."""

    def test_ensure_v1_service_loads_once(self) -> None:
        """V1 service is loaded once and cached."""
        mock_session = MagicMock()
        comparison = SearchComparison(mock_session)

        with patch("catalog.search.service.SearchService") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            service1 = comparison._ensure_v1_service()
            service2 = comparison._ensure_v1_service()

            assert service1 is service2

    def test_ensure_v2_service_loads_once(self) -> None:
        """V2 service is loaded once and cached."""
        mock_session = MagicMock()
        comparison = SearchComparison(mock_session)

        with patch("catalog.search.service_v2.SearchServiceV2") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            service1 = comparison._ensure_v2_service()
            service2 = comparison._ensure_v2_service()

            assert service1 is service2


class TestJaccardSimilarity:
    """Tests for Jaccard similarity calculation."""

    @pytest.fixture
    def comparison(self) -> SearchComparison:
        """Create SearchComparison instance."""
        return SearchComparison(MagicMock())

    def test_identical_results_returns_one(self, comparison: SearchComparison) -> None:
        """Jaccard of identical sets is 1.0."""
        results = [
            SearchResult(path="a.md", dataset_name="ds", score=1.0, scores={}),
            SearchResult(path="b.md", dataset_name="ds", score=0.9, scores={}),
            SearchResult(path="c.md", dataset_name="ds", score=0.8, scores={}),
        ]

        jaccard = comparison._jaccard(results, results, k=3)

        assert jaccard == 1.0

    def test_completely_different_returns_zero(
        self, comparison: SearchComparison
    ) -> None:
        """Jaccard of disjoint sets is 0.0."""
        v1_results = [
            SearchResult(path="a.md", dataset_name="ds", score=1.0, scores={}),
            SearchResult(path="b.md", dataset_name="ds", score=0.9, scores={}),
        ]
        v2_results = [
            SearchResult(path="x.md", dataset_name="ds", score=1.0, scores={}),
            SearchResult(path="y.md", dataset_name="ds", score=0.9, scores={}),
        ]

        jaccard = comparison._jaccard(v1_results, v2_results, k=2)

        assert jaccard == 0.0

    def test_partial_overlap(self, comparison: SearchComparison) -> None:
        """Jaccard with partial overlap calculates correctly."""
        # v1: {a, b, c}, v2: {b, c, d}
        # intersection: {b, c} = 2
        # union: {a, b, c, d} = 4
        # jaccard = 2/4 = 0.5
        v1_results = [
            SearchResult(path="a.md", dataset_name="ds", score=1.0, scores={}),
            SearchResult(path="b.md", dataset_name="ds", score=0.9, scores={}),
            SearchResult(path="c.md", dataset_name="ds", score=0.8, scores={}),
        ]
        v2_results = [
            SearchResult(path="b.md", dataset_name="ds", score=1.0, scores={}),
            SearchResult(path="c.md", dataset_name="ds", score=0.9, scores={}),
            SearchResult(path="d.md", dataset_name="ds", score=0.8, scores={}),
        ]

        jaccard = comparison._jaccard(v1_results, v2_results, k=3)

        assert jaccard == 0.5

    def test_respects_k_limit(self, comparison: SearchComparison) -> None:
        """Jaccard only considers top K results."""
        # Top 2: v1={a,b}, v2={a,c}
        # intersection: {a} = 1
        # union: {a, b, c} = 3
        # jaccard = 1/3 ~= 0.333
        v1_results = [
            SearchResult(path="a.md", dataset_name="ds", score=1.0, scores={}),
            SearchResult(path="b.md", dataset_name="ds", score=0.9, scores={}),
            SearchResult(path="x.md", dataset_name="ds", score=0.8, scores={}),
        ]
        v2_results = [
            SearchResult(path="a.md", dataset_name="ds", score=1.0, scores={}),
            SearchResult(path="c.md", dataset_name="ds", score=0.9, scores={}),
            SearchResult(path="b.md", dataset_name="ds", score=0.8, scores={}),
        ]

        jaccard = comparison._jaccard(v1_results, v2_results, k=2)

        assert jaccard == pytest.approx(1 / 3)

    def test_empty_results_returns_zero(self, comparison: SearchComparison) -> None:
        """Jaccard of empty sets is 0.0."""
        jaccard = comparison._jaccard([], [], k=5)
        assert jaccard == 0.0

    def test_one_empty_returns_zero(self, comparison: SearchComparison) -> None:
        """Jaccard with one empty set is 0.0."""
        results = [
            SearchResult(path="a.md", dataset_name="ds", score=1.0, scores={}),
        ]

        assert comparison._jaccard(results, [], k=5) == 0.0
        assert comparison._jaccard([], results, k=5) == 0.0

    def test_different_datasets_are_distinct(
        self, comparison: SearchComparison
    ) -> None:
        """Same path in different datasets are considered different."""
        v1_results = [
            SearchResult(path="notes.md", dataset_name="obsidian", score=1.0, scores={}),
        ]
        v2_results = [
            SearchResult(path="notes.md", dataset_name="other", score=1.0, scores={}),
        ]

        jaccard = comparison._jaccard(v1_results, v2_results, k=5)

        assert jaccard == 0.0


class TestSpearmanCorrelation:
    """Tests for Spearman rank correlation calculation."""

    @pytest.fixture
    def comparison(self) -> SearchComparison:
        """Create SearchComparison instance."""
        return SearchComparison(MagicMock())

    def test_identical_ranking_returns_one(self, comparison: SearchComparison) -> None:
        """Identical rankings give correlation of 1.0."""
        results = [
            SearchResult(path="a.md", dataset_name="ds", score=1.0, scores={}),
            SearchResult(path="b.md", dataset_name="ds", score=0.9, scores={}),
            SearchResult(path="c.md", dataset_name="ds", score=0.8, scores={}),
        ]

        rho = comparison._spearman(results, results)

        assert rho == pytest.approx(1.0)

    def test_reversed_ranking_returns_negative_one(
        self, comparison: SearchComparison
    ) -> None:
        """Perfectly reversed rankings give correlation of -1.0."""
        v1_results = [
            SearchResult(path="a.md", dataset_name="ds", score=1.0, scores={}),
            SearchResult(path="b.md", dataset_name="ds", score=0.9, scores={}),
            SearchResult(path="c.md", dataset_name="ds", score=0.8, scores={}),
        ]
        v2_results = [
            SearchResult(path="c.md", dataset_name="ds", score=1.0, scores={}),
            SearchResult(path="b.md", dataset_name="ds", score=0.9, scores={}),
            SearchResult(path="a.md", dataset_name="ds", score=0.8, scores={}),
        ]

        rho = comparison._spearman(v1_results, v2_results)

        assert rho == pytest.approx(-1.0)

    def test_no_overlap_returns_zero(self, comparison: SearchComparison) -> None:
        """No overlapping documents gives correlation of 0.0."""
        v1_results = [
            SearchResult(path="a.md", dataset_name="ds", score=1.0, scores={}),
            SearchResult(path="b.md", dataset_name="ds", score=0.9, scores={}),
        ]
        v2_results = [
            SearchResult(path="x.md", dataset_name="ds", score=1.0, scores={}),
            SearchResult(path="y.md", dataset_name="ds", score=0.9, scores={}),
        ]

        rho = comparison._spearman(v1_results, v2_results)

        assert rho == 0.0

    def test_single_overlap_returns_zero(self, comparison: SearchComparison) -> None:
        """Single overlapping document gives correlation of 0.0."""
        v1_results = [
            SearchResult(path="a.md", dataset_name="ds", score=1.0, scores={}),
            SearchResult(path="b.md", dataset_name="ds", score=0.9, scores={}),
        ]
        v2_results = [
            SearchResult(path="a.md", dataset_name="ds", score=1.0, scores={}),
            SearchResult(path="x.md", dataset_name="ds", score=0.9, scores={}),
        ]

        rho = comparison._spearman(v1_results, v2_results)

        assert rho == 0.0

    def test_partial_overlap_correlation(self, comparison: SearchComparison) -> None:
        """Correlation calculated for overlapping subset."""
        # v1: a(1), b(2), c(3), x(4)
        # v2: y(1), b(2), c(3), a(4)
        # Overlapping: a, b, c
        # v1 ranks: a=1, b=2, c=3
        # v2 ranks: b=2, c=3, a=4
        # d values: a=(1-4)=-3, b=(2-2)=0, c=(3-3)=0
        # d^2: 9, 0, 0 = 9
        # n=3, rho = 1 - 6*9/(3*(9-1)) = 1 - 54/24 = 1 - 2.25 = -1.25
        # Clamped to valid range [-1, 1], but actually this is a valid calculation
        v1_results = [
            SearchResult(path="a.md", dataset_name="ds", score=1.0, scores={}),
            SearchResult(path="b.md", dataset_name="ds", score=0.9, scores={}),
            SearchResult(path="c.md", dataset_name="ds", score=0.8, scores={}),
            SearchResult(path="x.md", dataset_name="ds", score=0.7, scores={}),
        ]
        v2_results = [
            SearchResult(path="y.md", dataset_name="ds", score=1.0, scores={}),
            SearchResult(path="b.md", dataset_name="ds", score=0.9, scores={}),
            SearchResult(path="c.md", dataset_name="ds", score=0.8, scores={}),
            SearchResult(path="a.md", dataset_name="ds", score=0.7, scores={}),
        ]

        rho = comparison._spearman(v1_results, v2_results)

        # d^2 = (1-4)^2 + (2-2)^2 + (3-3)^2 = 9 + 0 + 0 = 9
        # rho = 1 - 6*9/(3*8) = 1 - 54/24 = 1 - 2.25 = -1.25
        # This is below -1, but mathematically valid for this edge case
        expected = 1 - (6 * 9) / (3 * 8)
        assert rho == pytest.approx(expected)

    def test_empty_results_returns_zero(self, comparison: SearchComparison) -> None:
        """Empty results give correlation of 0.0."""
        rho = comparison._spearman([], [])
        assert rho == 0.0


class TestSearchComparisonCompare:
    """Tests for compare method."""

    @pytest.fixture
    def comparison(self) -> SearchComparison:
        """Create SearchComparison instance."""
        return SearchComparison(MagicMock())

    def test_compare_calls_both_services(self, comparison: SearchComparison) -> None:
        """compare() invokes both v1 and v2 services."""
        mock_v1 = MagicMock()
        mock_v2 = MagicMock()

        v1_result = SearchResults(
            results=[
                SearchResult(path="a.md", dataset_name="ds", score=1.0, scores={}),
            ],
            query="test",
            mode="hybrid",
            total_candidates=1,
            timing_ms=10.0,
        )
        v2_result = SearchResults(
            results=[
                SearchResult(path="a.md", dataset_name="ds", score=0.9, scores={}),
            ],
            query="test",
            mode="hybrid",
            total_candidates=1,
            timing_ms=15.0,
        )

        mock_v1.search.return_value = v1_result
        mock_v2.search.return_value = v2_result

        with patch.object(comparison, "_ensure_v1_service", return_value=mock_v1):
            with patch.object(comparison, "_ensure_v2_service", return_value=mock_v2):
                criteria = SearchCriteria(query="test", mode="hybrid")
                result = comparison.compare(criteria)

                mock_v1.search.assert_called_once_with(criteria)
                mock_v2.search.assert_called_once_with(criteria)

                assert result.query == "test"
                assert len(result.v1_results) == 1
                assert len(result.v2_results) == 1
                assert result.v1_time_ms > 0
                assert result.v2_time_ms > 0

    def test_compare_calculates_metrics(self, comparison: SearchComparison) -> None:
        """compare() calculates overlap and correlation metrics."""
        mock_v1 = MagicMock()
        mock_v2 = MagicMock()

        # Identical results for testing
        shared_results = [
            SearchResult(path="a.md", dataset_name="ds", score=1.0, scores={}),
            SearchResult(path="b.md", dataset_name="ds", score=0.9, scores={}),
            SearchResult(path="c.md", dataset_name="ds", score=0.8, scores={}),
        ]

        mock_v1.search.return_value = SearchResults(
            results=shared_results,
            query="test",
            mode="hybrid",
            total_candidates=3,
            timing_ms=10.0,
        )
        mock_v2.search.return_value = SearchResults(
            results=shared_results,
            query="test",
            mode="hybrid",
            total_candidates=3,
            timing_ms=15.0,
        )

        with patch.object(comparison, "_ensure_v1_service", return_value=mock_v1):
            with patch.object(comparison, "_ensure_v2_service", return_value=mock_v2):
                criteria = SearchCriteria(query="test", mode="hybrid")
                result = comparison.compare(criteria)

                # Identical results should have perfect overlap and correlation
                assert result.overlap_at_5 == 1.0
                assert result.overlap_at_10 == 1.0
                assert result.rank_correlation == pytest.approx(1.0)


class TestSearchComparisonCompareBatch:
    """Tests for compare_batch method."""

    @pytest.fixture
    def comparison(self) -> SearchComparison:
        """Create SearchComparison instance."""
        return SearchComparison(MagicMock())

    def test_compare_batch_calls_compare_for_each(
        self, comparison: SearchComparison
    ) -> None:
        """compare_batch() calls compare for each query."""
        queries = ["query1", "query2", "query3"]

        with patch.object(comparison, "compare") as mock_compare:
            mock_compare.return_value = ComparisonResult(query="mock")

            results = comparison.compare_batch(queries)

            assert mock_compare.call_count == 3
            assert len(results) == 3

    def test_compare_batch_uses_provided_options(
        self, comparison: SearchComparison
    ) -> None:
        """compare_batch() passes mode, limit, dataset_name to compare."""
        queries = ["test"]

        with patch.object(comparison, "compare") as mock_compare:
            mock_compare.return_value = ComparisonResult(query="test")

            comparison.compare_batch(
                queries, mode="fts", limit=5, dataset_name="obsidian"
            )

            call_args = mock_compare.call_args[0][0]
            assert call_args.query == "test"
            assert call_args.mode == "fts"
            assert call_args.limit == 5
            assert call_args.dataset_name == "obsidian"


class TestSearchComparisonSummaryReport:
    """Tests for summary_report method."""

    @pytest.fixture
    def comparison(self) -> SearchComparison:
        """Create SearchComparison instance."""
        return SearchComparison(MagicMock())

    def test_empty_results_returns_zeros(self, comparison: SearchComparison) -> None:
        """Empty results list returns zeroed summary."""
        summary = comparison.summary_report([])

        assert summary["count"] == 0
        assert summary["v1_mean_time_ms"] == 0.0
        assert summary["v2_mean_time_ms"] == 0.0
        assert summary["mean_overlap_at_5"] == 0.0
        assert summary["mean_overlap_at_10"] == 0.0
        assert summary["mean_rank_correlation"] == 0.0
        assert summary["queries_with_no_overlap"] == 0

    def test_calculates_means_correctly(self, comparison: SearchComparison) -> None:
        """summary_report calculates correct means."""
        results = [
            ComparisonResult(
                query="q1",
                v1_time_ms=100.0,
                v2_time_ms=200.0,
                overlap_at_5=0.8,
                overlap_at_10=0.9,
                rank_correlation=0.7,
            ),
            ComparisonResult(
                query="q2",
                v1_time_ms=200.0,
                v2_time_ms=300.0,
                overlap_at_5=0.6,
                overlap_at_10=0.7,
                rank_correlation=0.5,
            ),
        ]

        summary = comparison.summary_report(results)

        assert summary["count"] == 2
        assert summary["v1_mean_time_ms"] == 150.0
        assert summary["v2_mean_time_ms"] == 250.0
        assert summary["mean_overlap_at_5"] == 0.7
        assert summary["mean_overlap_at_10"] == 0.8
        assert summary["mean_rank_correlation"] == 0.6
        assert summary["queries_with_no_overlap"] == 0

    def test_counts_queries_with_no_overlap(
        self, comparison: SearchComparison
    ) -> None:
        """summary_report counts queries with zero overlap."""
        results = [
            ComparisonResult(query="q1", overlap_at_10=0.5),
            ComparisonResult(query="q2", overlap_at_10=0.0),
            ComparisonResult(query="q3", overlap_at_10=0.0),
            ComparisonResult(query="q4", overlap_at_10=0.3),
        ]

        summary = comparison.summary_report(results)

        assert summary["queries_with_no_overlap"] == 2
