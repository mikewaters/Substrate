"""Tests for catalog.eval.golden module.

Tests the Golden Query Evaluation Suite for RAG v2.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from catalog.eval.golden import (
    EVAL_THRESHOLDS,
    EvalResult,
    GoldenQuery,
    _aggregate_metrics,
    _evaluate_single,
    evaluate_golden_queries,
    load_golden_queries,
)
from catalog.search.models import SearchCriteria, SearchResult, SearchResults, SnippetResult


class TestGoldenQueryDataclass:
    """Tests for GoldenQuery dataclass."""

    def test_create_minimal_golden_query(self) -> None:
        """GoldenQuery can be created with required fields."""
        gq = GoldenQuery(
            query="test query",
            expected_docs=["doc1.md", "doc2.md"],
            difficulty="easy",
            retriever_types=["bm25"],
        )
        assert gq.query == "test query"
        assert gq.expected_docs == ["doc1.md", "doc2.md"]
        assert gq.difficulty == "easy"
        assert gq.retriever_types == ["bm25"]
        assert gq.notes is None

    def test_create_full_golden_query(self) -> None:
        """GoldenQuery can be created with all fields."""
        gq = GoldenQuery(
            query="complex query",
            expected_docs=["doc1.md"],
            difficulty="hard",
            retriever_types=["bm25", "vector", "hybrid"],
            notes="This is a hard query requiring semantic understanding",
        )
        assert gq.notes == "This is a hard query requiring semantic understanding"

    def test_golden_query_with_multiple_expected_docs(self) -> None:
        """GoldenQuery supports multiple expected documents."""
        gq = GoldenQuery(
            query="multi-doc query",
            expected_docs=["doc1.md", "doc2.md", "doc3.md"],
            difficulty="medium",
            retriever_types=["hybrid"],
        )
        assert len(gq.expected_docs) == 3

    def test_golden_query_difficulty_levels(self) -> None:
        """GoldenQuery supports all difficulty levels."""
        for difficulty in ["easy", "medium", "hard", "fusion"]:
            gq = GoldenQuery(
                query="test",
                expected_docs=["doc.md"],
                difficulty=difficulty,  # type: ignore[arg-type]
                retriever_types=["bm25"],
            )
            assert gq.difficulty == difficulty


class TestEvalResultDataclass:
    """Tests for EvalResult dataclass."""

    def test_create_minimal_eval_result(self) -> None:
        """EvalResult can be created with required fields."""
        result = EvalResult(
            query="test query",
            difficulty="easy",
            retriever_type="bm25",
            hits={1: True, 3: True, 5: True, 10: True},
        )
        assert result.query == "test query"
        assert result.difficulty == "easy"
        assert result.retriever_type == "bm25"
        assert result.hit_at_1 is True
        assert result.retrieved_docs == []
        assert result.scores == []

    def test_create_full_eval_result(self) -> None:
        """EvalResult can be created with all fields."""
        result = EvalResult(
            query="test query",
            difficulty="hard",
            retriever_type="hybrid",
            hits={1: False, 3: True, 5: True, 10: True},
            retrieved_docs=["doc1.md", "doc2.md", "doc3.md"],
            scores=[0.95, 0.85, 0.75],
        )
        assert result.retrieved_docs == ["doc1.md", "doc2.md", "doc3.md"]
        assert result.scores == [0.95, 0.85, 0.75]
        assert result.hit_at_1 is False
        assert result.hit_at_3 is True

    def test_eval_result_miss_at_all_k(self) -> None:
        """EvalResult can represent a complete miss."""
        result = EvalResult(
            query="hard query",
            difficulty="hard",
            retriever_type="vector",
            hits={1: False, 3: False, 5: False, 10: False},
            retrieved_docs=["wrong1.md", "wrong2.md"],
            scores=[0.5, 0.4],
        )
        assert result.hit_at_1 is False
        assert result.hit_at_10 is False

    def test_hit_at_k_method(self) -> None:
        """EvalResult.hit_at_k returns correct values for arbitrary k."""
        result = EvalResult(
            query="test",
            difficulty="easy",
            retriever_type="bm25",
            hits={1: False, 2: True, 5: True},
        )
        assert result.hit_at_k(1) is False
        assert result.hit_at_k(2) is True
        assert result.hit_at_k(5) is True
        assert result.hit_at_k(100) is False  # Not in hits dict


class TestLoadGoldenQueries:
    """Tests for load_golden_queries function."""

    def test_load_valid_json_file(self, tmp_path: Path) -> None:
        """load_golden_queries loads valid JSON file."""
        data = [
            {
                "query": "test query 1",
                "expected_docs": ["doc1.md"],
                "difficulty": "easy",
                "retriever_types": ["bm25"],
            },
            {
                "query": "test query 2",
                "expected_docs": ["doc2.md", "doc3.md"],
                "difficulty": "medium",
                "retriever_types": ["vector", "hybrid"],
                "notes": "A medium difficulty query",
            },
        ]
        file_path = tmp_path / "golden.json"
        file_path.write_text(json.dumps(data))

        queries = load_golden_queries(str(file_path))

        assert len(queries) == 2
        assert queries[0].query == "test query 1"
        assert queries[0].difficulty == "easy"
        assert queries[1].notes == "A medium difficulty query"

    def test_load_file_not_found(self) -> None:
        """load_golden_queries raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError, match="not found"):
            load_golden_queries("/nonexistent/path/golden.json")

    def test_load_invalid_json(self, tmp_path: Path) -> None:
        """load_golden_queries raises JSONDecodeError for invalid JSON."""
        file_path = tmp_path / "invalid.json"
        file_path.write_text("not valid json {{{")

        with pytest.raises(json.JSONDecodeError):
            load_golden_queries(str(file_path))

    def test_load_non_array_json(self, tmp_path: Path) -> None:
        """load_golden_queries raises ValueError for object without 'queries' array."""
        file_path = tmp_path / "object.json"
        file_path.write_text('{"query": "test"}')

        with pytest.raises(ValueError, match="Expected JSON array or object with 'queries' array"):
            load_golden_queries(str(file_path))

    def test_load_wrapped_queries_dict(self, tmp_path: Path) -> None:
        """load_golden_queries accepts object with 'queries' key (wrapper format)."""
        data = {
            "version": "1.0",
            "description": "Test fixture",
            "queries": [
                {
                    "query": "wrapped query",
                    "expected_docs": ["doc.md"],
                    "difficulty": "easy",
                    "retriever_types": ["bm25"],
                },
            ],
        }
        file_path = tmp_path / "wrapped.json"
        file_path.write_text(json.dumps(data))

        queries = load_golden_queries(str(file_path))
        assert len(queries) == 1
        assert queries[0].query == "wrapped query"

    def test_load_missing_required_field(self, tmp_path: Path) -> None:
        """load_golden_queries raises KeyError for missing required field."""
        data = [
            {
                "query": "test",
                "expected_docs": ["doc.md"],
                # missing "difficulty" and "retriever_types"
            }
        ]
        file_path = tmp_path / "missing.json"
        file_path.write_text(json.dumps(data))

        with pytest.raises(KeyError, match="missing required field"):
            load_golden_queries(str(file_path))

    def test_load_invalid_difficulty(self, tmp_path: Path) -> None:
        """load_golden_queries raises ValueError for invalid difficulty."""
        data = [
            {
                "query": "test",
                "expected_docs": ["doc.md"],
                "difficulty": "impossible",
                "retriever_types": ["bm25"],
            }
        ]
        file_path = tmp_path / "invalid_diff.json"
        file_path.write_text(json.dumps(data))

        with pytest.raises(ValueError, match="invalid difficulty"):
            load_golden_queries(str(file_path))

    def test_load_invalid_retriever_type(self, tmp_path: Path) -> None:
        """load_golden_queries raises ValueError for invalid retriever type."""
        data = [
            {
                "query": "test",
                "expected_docs": ["doc.md"],
                "difficulty": "easy",
                "retriever_types": ["unknown_retriever"],
            }
        ]
        file_path = tmp_path / "invalid_rt.json"
        file_path.write_text(json.dumps(data))

        with pytest.raises(ValueError, match="invalid retriever_type"):
            load_golden_queries(str(file_path))

    def test_load_empty_array(self, tmp_path: Path) -> None:
        """load_golden_queries handles empty array."""
        file_path = tmp_path / "empty.json"
        file_path.write_text("[]")

        queries = load_golden_queries(str(file_path))
        assert queries == []


class TestEvaluateSingle:
    """Tests for _evaluate_single function."""

    @pytest.fixture
    def mock_service(self) -> MagicMock:
        """Create a mock SearchServiceV2."""
        return MagicMock()

    def test_hit_at_1(self, mock_service: MagicMock) -> None:
        """_evaluate_single calculates hit@1 correctly."""
        # Mock search results with expected doc at position 0
        mock_service.search.return_value = SearchResults(
            results=[
                SearchResult(
                    path="expected.md",
                    dataset_name="test",
                    score=0.9,
                    snippet=SnippetResult(text="content", start_line=1, end_line=1, header="@@ -1,1 +1,1 @@ test"),
                    scores={},
                ),
                SearchResult(
                    path="other.md",
                    dataset_name="test",
                    score=0.8,
                    snippet=SnippetResult(text="content", start_line=1, end_line=1, header="@@ -1,1 +1,1 @@ test"),
                    scores={},
                ),
            ],
            query="test",
            mode="fts",
            total_candidates=2,
            timing_ms=10,
        )

        gq = GoldenQuery(
            query="test query",
            expected_docs=["expected.md"],
            difficulty="easy",
            retriever_types=["bm25"],
        )

        result = _evaluate_single(mock_service, gq, "bm25", [1, 3, 5, 10])

        assert result.hit_at_1 is True
        assert result.hit_at_3 is True
        assert result.hit_at_5 is True
        assert result.hit_at_10 is True

    def test_hit_at_3_not_at_1(self, mock_service: MagicMock) -> None:
        """_evaluate_single calculates hit@3 when expected doc is at position 2."""
        mock_service.search.return_value = SearchResults(
            results=[
                SearchResult(path="other1.md", dataset_name="test", score=0.9, snippet=None, scores={}),
                SearchResult(path="other2.md", dataset_name="test", score=0.85, snippet=None, scores={}),
                SearchResult(path="expected.md", dataset_name="test", score=0.8, snippet=None, scores={}),
            ],
            query="test",
            mode="fts",
            total_candidates=3,
            timing_ms=10,
        )

        gq = GoldenQuery(
            query="test query",
            expected_docs=["expected.md"],
            difficulty="medium",
            retriever_types=["bm25"],
        )

        result = _evaluate_single(mock_service, gq, "bm25", [1, 3, 5, 10])

        assert result.hit_at_1 is False
        assert result.hit_at_3 is True
        assert result.hit_at_5 is True
        assert result.hit_at_10 is True

    def test_miss_at_all_k(self, mock_service: MagicMock) -> None:
        """_evaluate_single calculates miss when expected doc not in top 10."""
        mock_service.search.return_value = SearchResults(
            results=[
                SearchResult(path=f"other{i}.md", dataset_name="test", score=0.9 - i * 0.01, snippet=None, scores={})
                for i in range(10)
            ],
            query="test",
            mode="vector",
            total_candidates=10,
            timing_ms=10,
        )

        gq = GoldenQuery(
            query="test query",
            expected_docs=["expected.md"],
            difficulty="hard",
            retriever_types=["vector"],
        )

        result = _evaluate_single(mock_service, gq, "vector", [1, 3, 5, 10])

        assert result.hit_at_1 is False
        assert result.hit_at_3 is False
        assert result.hit_at_5 is False
        assert result.hit_at_10 is False

    def test_multiple_expected_docs(self, mock_service: MagicMock) -> None:
        """_evaluate_single hits if any expected doc is found."""
        mock_service.search.return_value = SearchResults(
            results=[
                SearchResult(path="other.md", dataset_name="test", score=0.9, snippet=None, scores={}),
                SearchResult(path="expected2.md", dataset_name="test", score=0.8, snippet=None, scores={}),
            ],
            query="test",
            mode="hybrid",
            total_candidates=2,
            timing_ms=10,
        )

        gq = GoldenQuery(
            query="test query",
            expected_docs=["expected1.md", "expected2.md"],
            difficulty="easy",
            retriever_types=["hybrid"],
        )

        result = _evaluate_single(mock_service, gq, "hybrid", [1, 3, 5, 10])

        # expected2.md is at position 2, so hit@1 is False, hit@3 is True
        assert result.hit_at_1 is False
        assert result.hit_at_3 is True

    def test_mode_mapping(self, mock_service: MagicMock) -> None:
        """_evaluate_single maps retriever types to search modes correctly."""
        mock_service.search.return_value = SearchResults(
            results=[],
            query="test",
            mode="fts",
            total_candidates=0,
            timing_ms=0,
        )

        gq = GoldenQuery(
            query="test",
            expected_docs=["doc.md"],
            difficulty="easy",
            retriever_types=["bm25"],
        )

        # Test bm25 -> fts
        _evaluate_single(mock_service, gq, "bm25", [1, 3, 5, 10])
        call_args = mock_service.search.call_args
        assert call_args[0][0].mode == "fts"

        # Test vector -> vector
        _evaluate_single(mock_service, gq, "vector", [1, 3, 5, 10])
        call_args = mock_service.search.call_args
        assert call_args[0][0].mode == "vector"

        # Test hybrid -> hybrid
        _evaluate_single(mock_service, gq, "hybrid", [1, 3, 5, 10])
        call_args = mock_service.search.call_args
        assert call_args[0][0].mode == "hybrid"

    def test_retrieved_docs_and_scores(self, mock_service: MagicMock) -> None:
        """_evaluate_single captures retrieved docs and scores."""
        mock_service.search.return_value = SearchResults(
            results=[
                SearchResult(path="doc1.md", dataset_name="test", score=0.95, snippet=None, scores={}),
                SearchResult(path="doc2.md", dataset_name="test", score=0.85, snippet=None, scores={}),
            ],
            query="test",
            mode="fts",
            total_candidates=2,
            timing_ms=10,
        )

        gq = GoldenQuery(
            query="test",
            expected_docs=["doc1.md"],
            difficulty="easy",
            retriever_types=["bm25"],
        )

        result = _evaluate_single(mock_service, gq, "bm25", [1, 3, 5, 10])

        assert result.retrieved_docs == ["doc1.md", "doc2.md"]
        assert result.scores == [0.95, 0.85]


class TestAggregateMetrics:
    """Tests for _aggregate_metrics function."""

    def test_aggregate_single_group(self) -> None:
        """_aggregate_metrics calculates metrics for a single group."""
        results = [
            EvalResult("q1", "easy", "bm25", {1: True, 3: True, 5: True, 10: True}, [], []),
            EvalResult("q2", "easy", "bm25", {1: False, 3: True, 5: True, 10: True}, [], []),
            EvalResult("q3", "easy", "bm25", {1: False, 3: False, 5: True, 10: True}, [], []),
            EvalResult("q4", "easy", "bm25", {1: False, 3: False, 5: False, 10: True}, [], []),
        ]

        aggregated = _aggregate_metrics(results, [1, 3, 5, 10])

        assert "bm25" in aggregated
        assert "easy" in aggregated["bm25"]
        metrics = aggregated["bm25"]["easy"]
        assert metrics["hit_at_1"] == 0.25  # 1/4
        assert metrics["hit_at_3"] == 0.50  # 2/4
        assert metrics["hit_at_5"] == 0.75  # 3/4
        assert metrics["hit_at_10"] == 1.0  # 4/4
        assert metrics["count"] == 4.0

    def test_aggregate_multiple_retrievers(self) -> None:
        """_aggregate_metrics groups by retriever type."""
        results = [
            EvalResult("q1", "easy", "bm25", {1: True, 3: True, 5: True, 10: True}, [], []),
            EvalResult("q2", "easy", "vector", {1: False, 3: True, 5: True, 10: True}, [], []),
        ]

        aggregated = _aggregate_metrics(results, [1, 3, 5, 10])

        assert "bm25" in aggregated
        assert "vector" in aggregated
        assert aggregated["bm25"]["easy"]["hit_at_1"] == 1.0
        assert aggregated["vector"]["easy"]["hit_at_1"] == 0.0

    def test_aggregate_multiple_difficulties(self) -> None:
        """_aggregate_metrics groups by difficulty level."""
        results = [
            EvalResult("q1", "easy", "bm25", {1: True, 3: True, 5: True, 10: True}, [], []),
            EvalResult("q2", "hard", "bm25", {1: False, 3: False, 5: True, 10: True}, [], []),
        ]

        aggregated = _aggregate_metrics(results, [1, 3, 5, 10])

        assert "easy" in aggregated["bm25"]
        assert "hard" in aggregated["bm25"]
        assert aggregated["bm25"]["easy"]["hit_at_1"] == 1.0
        assert aggregated["bm25"]["hard"]["hit_at_1"] == 0.0

    def test_aggregate_empty_results(self) -> None:
        """_aggregate_metrics handles empty results."""
        aggregated = _aggregate_metrics([], [1, 3, 5, 10])
        assert aggregated == {}


class TestEvaluateGoldenQueries:
    """Tests for evaluate_golden_queries function."""

    @pytest.fixture
    def mock_service(self) -> MagicMock:
        """Create a mock SearchServiceV2."""
        return MagicMock()

    def test_evaluate_single_query_single_retriever(self, mock_service: MagicMock) -> None:
        """evaluate_golden_queries evaluates a single query against one retriever."""
        mock_service.search.return_value = SearchResults(
            results=[
                SearchResult(path="expected.md", dataset_name="test", score=0.9, snippet=None, scores={}),
            ],
            query="test",
            mode="fts",
            total_candidates=1,
            timing_ms=10,
        )

        golden_queries = [
            GoldenQuery(
                query="test query",
                expected_docs=["expected.md"],
                difficulty="easy",
                retriever_types=["bm25"],
            )
        ]

        result = evaluate_golden_queries(mock_service, golden_queries)

        assert "bm25" in result
        assert "easy" in result["bm25"]
        assert result["bm25"]["easy"]["hit_at_1"] == 1.0

    def test_evaluate_multiple_retrievers(self, mock_service: MagicMock) -> None:
        """evaluate_golden_queries evaluates against multiple retriever types."""
        mock_service.search.return_value = SearchResults(
            results=[
                SearchResult(path="expected.md", dataset_name="test", score=0.9, snippet=None, scores={}),
            ],
            query="test",
            mode="hybrid",
            total_candidates=1,
            timing_ms=10,
        )

        golden_queries = [
            GoldenQuery(
                query="test query",
                expected_docs=["expected.md"],
                difficulty="easy",
                retriever_types=["bm25", "vector", "hybrid"],
            )
        ]

        result = evaluate_golden_queries(mock_service, golden_queries)

        # Should have results for all three retriever types
        assert "bm25" in result
        assert "vector" in result
        assert "hybrid" in result
        # Each should have 100% hit rate since expected doc is returned
        assert result["bm25"]["easy"]["hit_at_1"] == 1.0
        assert result["vector"]["easy"]["hit_at_1"] == 1.0
        assert result["hybrid"]["easy"]["hit_at_1"] == 1.0

    def test_evaluate_custom_k_values(self, mock_service: MagicMock) -> None:
        """evaluate_golden_queries uses custom k values."""
        mock_service.search.return_value = SearchResults(
            results=[
                SearchResult(path="other.md", dataset_name="test", score=0.9, snippet=None, scores={}),
                SearchResult(path="expected.md", dataset_name="test", score=0.8, snippet=None, scores={}),
            ],
            query="test",
            mode="fts",
            total_candidates=2,
            timing_ms=10,
        )

        golden_queries = [
            GoldenQuery(
                query="test",
                expected_docs=["expected.md"],
                difficulty="easy",
                retriever_types=["bm25"],
            )
        ]

        # Only evaluate at k=1 and k=2
        result = evaluate_golden_queries(mock_service, golden_queries, k_values=[1, 2])

        metrics = result["bm25"]["easy"]
        assert "hit_at_1" in metrics
        assert "hit_at_2" in metrics
        assert metrics["hit_at_1"] == 0.0  # expected.md is at position 2
        assert metrics["hit_at_2"] == 1.0  # expected.md is within top 2


class TestEvalThresholds:
    """Tests for EVAL_THRESHOLDS configuration."""

    def test_all_retriever_types_present(self) -> None:
        """EVAL_THRESHOLDS has all retriever types."""
        assert "bm25" in EVAL_THRESHOLDS
        assert "vector" in EVAL_THRESHOLDS
        assert "hybrid" in EVAL_THRESHOLDS

    def test_all_difficulty_levels_present(self) -> None:
        """EVAL_THRESHOLDS has all difficulty levels for each retriever."""
        for retriever in ["bm25", "vector", "hybrid"]:
            assert "easy" in EVAL_THRESHOLDS[retriever]
            assert "medium" in EVAL_THRESHOLDS[retriever]
            assert "hard" in EVAL_THRESHOLDS[retriever]
            assert "fusion" in EVAL_THRESHOLDS[retriever]

    def test_all_k_values_present(self) -> None:
        """EVAL_THRESHOLDS has all k values for each difficulty."""
        for retriever in ["bm25", "vector", "hybrid"]:
            for difficulty in ["easy", "medium", "hard", "fusion"]:
                metrics = EVAL_THRESHOLDS[retriever][difficulty]
                assert "hit_at_1" in metrics
                assert "hit_at_3" in metrics
                assert "hit_at_5" in metrics
                assert "hit_at_10" in metrics

    def test_thresholds_are_valid_percentages(self) -> None:
        """EVAL_THRESHOLDS values are valid percentages (0-1)."""
        for retriever in EVAL_THRESHOLDS:
            for difficulty in EVAL_THRESHOLDS[retriever]:
                for metric, value in EVAL_THRESHOLDS[retriever][difficulty].items():
                    assert 0.0 <= value <= 1.0, f"{retriever}/{difficulty}/{metric} = {value}"

    def test_thresholds_increase_with_k(self) -> None:
        """EVAL_THRESHOLDS increase as k increases (more chances to hit)."""
        for retriever in EVAL_THRESHOLDS:
            for difficulty in EVAL_THRESHOLDS[retriever]:
                metrics = EVAL_THRESHOLDS[retriever][difficulty]
                assert metrics["hit_at_1"] <= metrics["hit_at_3"]
                assert metrics["hit_at_3"] <= metrics["hit_at_5"]
                assert metrics["hit_at_5"] <= metrics["hit_at_10"]

    def test_hybrid_generally_best(self) -> None:
        """EVAL_THRESHOLDS shows hybrid generally has highest thresholds."""
        # Hybrid should be >= others for most cases (not strict due to tuning)
        for difficulty in ["easy", "medium"]:
            hybrid_hit3 = EVAL_THRESHOLDS["hybrid"][difficulty]["hit_at_3"]
            bm25_hit3 = EVAL_THRESHOLDS["bm25"][difficulty]["hit_at_3"]
            vector_hit3 = EVAL_THRESHOLDS["vector"][difficulty]["hit_at_3"]
            # Hybrid should be at least as good as the max of others
            assert hybrid_hit3 >= max(bm25_hit3, vector_hit3) * 0.9  # Allow 10% tolerance
