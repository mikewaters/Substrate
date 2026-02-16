"""Golden Query Evaluation Suite for RAG search.

Provides data models and functions for evaluating search quality against
a set of golden (ground truth) queries. Supports multiple retriever types
(bm25, vector, hybrid) and difficulty levels.

Example usage:
    from catalog.eval.golden import (
        load_golden_queries,
        evaluate_golden_queries,
        EVAL_THRESHOLDS,
    )
    from catalog.search.service import SearchService

    golden_queries = load_golden_queries("tests/fixtures/golden_queries.json")
    results = evaluate_golden_queries(service, golden_queries)

    # Check against thresholds
    for retriever, difficulty_metrics in results.items():
        for difficulty, metrics in difficulty_metrics.items():
            threshold = EVAL_THRESHOLDS[retriever][difficulty]["hit_at_3"]
            assert metrics["hit_at_3"] >= threshold
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from agentlayer.logging import get_logger

if TYPE_CHECKING:
    from catalog.search.service import SearchService

__all__ = [
    "GoldenQuery",
    "EvalResult",
    "load_golden_queries",
    "evaluate_golden_queries",
    "EVAL_THRESHOLDS",
]

logger = get_logger(__name__)


# Evaluation thresholds by retriever type and difficulty
# These represent minimum acceptable Hit@K rates
EVAL_THRESHOLDS: dict[str, dict[str, dict[str, float]]] = {
    "bm25": {
        "easy": {"hit_at_1": 0.70, "hit_at_3": 0.80, "hit_at_5": 0.85, "hit_at_10": 0.90},
        "medium": {"hit_at_1": 0.50, "hit_at_3": 0.65, "hit_at_5": 0.75, "hit_at_10": 0.85},
        "hard": {"hit_at_1": 0.30, "hit_at_3": 0.45, "hit_at_5": 0.55, "hit_at_10": 0.70},
        "fusion": {"hit_at_1": 0.40, "hit_at_3": 0.55, "hit_at_5": 0.65, "hit_at_10": 0.75},
    },
    "vector": {
        "easy": {"hit_at_1": 0.50, "hit_at_3": 0.60, "hit_at_5": 0.70, "hit_at_10": 0.80},
        "medium": {"hit_at_1": 0.40, "hit_at_3": 0.55, "hit_at_5": 0.65, "hit_at_10": 0.75},
        "hard": {"hit_at_1": 0.25, "hit_at_3": 0.40, "hit_at_5": 0.50, "hit_at_10": 0.65},
        "fusion": {"hit_at_1": 0.35, "hit_at_3": 0.50, "hit_at_5": 0.60, "hit_at_10": 0.70},
    },
    "hybrid": {
        "easy": {"hit_at_1": 0.75, "hit_at_3": 0.85, "hit_at_5": 0.90, "hit_at_10": 0.95},
        "medium": {"hit_at_1": 0.55, "hit_at_3": 0.70, "hit_at_5": 0.80, "hit_at_10": 0.90},
        "hard": {"hit_at_1": 0.35, "hit_at_3": 0.50, "hit_at_5": 0.60, "hit_at_10": 0.75},
        "fusion": {"hit_at_1": 0.45, "hit_at_3": 0.60, "hit_at_5": 0.70, "hit_at_10": 0.80},
    },
}


@dataclass
class GoldenQuery:
    """A golden (ground truth) query for evaluation.

    Represents a query with known expected results, used to measure
    retrieval quality across different retriever types.

    Attributes:
        query: The search query string.
        expected_docs: List of expected document paths or doc IDs that
            should be retrieved for this query.
        difficulty: Query difficulty level affecting expected thresholds.
        retriever_types: List of retriever types to evaluate this query
            against (bm25, vector, hybrid).
        notes: Optional notes about this query or expected behavior.
    """

    query: str
    expected_docs: list[str]
    difficulty: Literal["easy", "medium", "hard", "fusion"]
    retriever_types: list[Literal["bm25", "vector", "hybrid"]]
    notes: str | None = None


@dataclass
class EvalResult:
    """Result from evaluating a single golden query.

    Contains hit-at-k metrics and retrieved documents for analysis.

    Attributes:
        query: The query string that was evaluated.
        difficulty: Difficulty level of the query.
        retriever_type: Type of retriever used (bm25, vector, hybrid).
        hits: Dict mapping k values to hit status (e.g., {1: True, 3: True}).
        retrieved_docs: List of document paths/IDs actually retrieved.
        scores: List of scores for each retrieved document.
    """

    query: str
    difficulty: str
    retriever_type: str
    hits: dict[int, bool] = field(default_factory=dict)
    retrieved_docs: list[str] = field(default_factory=list)
    scores: list[float] = field(default_factory=list)

    @property
    def hit_at_1(self) -> bool:
        """Whether any expected doc appeared in top 1."""
        return self.hits.get(1, False)

    @property
    def hit_at_3(self) -> bool:
        """Whether any expected doc appeared in top 3."""
        return self.hits.get(3, False)

    @property
    def hit_at_5(self) -> bool:
        """Whether any expected doc appeared in top 5."""
        return self.hits.get(5, False)

    @property
    def hit_at_10(self) -> bool:
        """Whether any expected doc appeared in top 10."""
        return self.hits.get(10, False)

    def hit_at_k(self, k: int) -> bool:
        """Get hit status for arbitrary k value."""
        return self.hits.get(k, False)


def load_golden_queries(path: str) -> list[GoldenQuery]:
    """Load golden queries from a JSON file.

    The JSON file may be either a top-level array of query objects, or an
    object with a "queries" key containing that array. Each object has:
        {
            "query": "search query text",
            "expected_docs": ["doc1.md", "doc2.md"],
            "difficulty": "easy|medium|hard|fusion",
            "retriever_types": ["bm25", "vector", "hybrid"],
            "notes": "optional notes"
        }

    Args:
        path: Path to the JSON file containing golden queries.

    Returns:
        List of GoldenQuery objects.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file contains invalid JSON.
        KeyError: If required fields are missing.
        ValueError: If field values are invalid.
    """
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"Golden queries file not found: {path}")

    with open(file_path) as f:
        data = json.load(f)

    if isinstance(data, dict) and "queries" in data:
        items = data["queries"]
    elif isinstance(data, list):
        items = data
    else:
        raise ValueError(
            f"Expected JSON array or object with 'queries' array, got {type(data).__name__}"
        )

    if not isinstance(items, list):
        raise ValueError(f"queries must be an array, got {type(items).__name__}")

    queries = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"Item {i} is not an object: {type(item).__name__}")

        # Validate required fields
        required = ["query", "expected_docs", "difficulty", "retriever_types"]
        for field_name in required:
            if field_name not in item:
                raise KeyError(f"Item {i} missing required field: {field_name}")

        # Validate difficulty
        valid_difficulties = {"easy", "medium", "hard", "fusion"}
        if item["difficulty"] not in valid_difficulties:
            raise ValueError(
                f"Item {i} has invalid difficulty: {item['difficulty']}. "
                f"Must be one of: {valid_difficulties}"
            )

        # Validate retriever_types
        valid_retrievers = {"bm25", "vector", "hybrid"}
        for rt in item["retriever_types"]:
            if rt not in valid_retrievers:
                raise ValueError(
                    f"Item {i} has invalid retriever_type: {rt}. "
                    f"Must be one of: {valid_retrievers}"
                )

        queries.append(
            GoldenQuery(
                query=item["query"],
                expected_docs=item["expected_docs"],
                difficulty=item["difficulty"],
                retriever_types=item["retriever_types"],
                notes=item.get("notes"),
            )
        )

    logger.debug(f"Loaded {len(queries)} golden queries from {path}")
    return queries


def evaluate_golden_queries(
    search_service: "SearchService",
    golden_queries: list[GoldenQuery],
    k_values: list[int] | None = None,
) -> dict[str, dict[str, dict[str, float]]]:
    """Evaluate search quality against golden queries.

    Runs each golden query against specified retriever types and
    calculates hit-at-k metrics. Results are aggregated by retriever
    type and difficulty level.

    Args:
        search_service: SearchService instance to use for search.
        golden_queries: List of GoldenQuery objects to evaluate.
        k_values: List of k values for hit@k calculation. Defaults
            to [1, 3, 5, 10].

    Returns:
        Nested dict with structure:
            {
                retriever_type: {
                    difficulty: {
                        "hit_at_1": float,
                        "hit_at_3": float,
                        "hit_at_5": float,
                        "hit_at_10": float,
                        "count": int,
                    }
                }
            }
    """
    if k_values is None:
        k_values = [1, 3, 5, 10]

    # Collect all individual results
    all_results: list[EvalResult] = []

    for gq in golden_queries:
        for retriever_type in gq.retriever_types:
            result = _evaluate_single(search_service, gq, retriever_type, k_values)
            all_results.append(result)

    # Aggregate metrics
    return _aggregate_metrics(all_results, k_values)


def _evaluate_single(
    service: "SearchService",
    gq: GoldenQuery,
    retriever_type: Literal["bm25", "vector", "hybrid"],
    k_values: list[int],
) -> EvalResult:
    """Evaluate a single golden query against a retriever type.

    Args:
        service: SearchService instance.
        gq: GoldenQuery to evaluate.
        retriever_type: Retriever type to use.
        k_values: List of k values for hit@k calculation.

    Returns:
        EvalResult with hit@k metrics and retrieved documents.
    """
    from catalog.search.models import SearchCriteria

    # Map retriever_type to search mode
    mode_map: dict[str, Literal["fts", "vector", "hybrid"]] = {
        "bm25": "fts",
        "vector": "vector",
        "hybrid": "hybrid",
    }
    mode = mode_map[retriever_type]

    # Execute search with enough results for all k values
    max_k = max(k_values)
    criteria = SearchCriteria(
        query=gq.query,
        mode=mode,
        limit=max_k,
        rerank=False,
    )

    results = service.search(criteria)

    # Extract retrieved doc paths
    retrieved_docs = [r.path for r in results.results]
    scores = [r.score for r in results.results]

    # Calculate hit@k for each k value
    expected_set = set(gq.expected_docs)
    hits: dict[int, bool] = {}
    for k in k_values:
        top_k_docs = set(retrieved_docs[:k])
        # Hit if any expected doc is in top k
        hits[k] = bool(expected_set & top_k_docs)

    logger.debug(
        f"Evaluated {retriever_type} for '{gq.query[:30]}...': "
        f"hit@3={hits.get(3, False)}"
    )

    return EvalResult(
        query=gq.query,
        difficulty=gq.difficulty,
        retriever_type=retriever_type,
        hits=hits,
        retrieved_docs=retrieved_docs,
        scores=scores,
    )


def _aggregate_metrics(
    results: list[EvalResult],
    k_values: list[int],
) -> dict[str, dict[str, dict[str, float]]]:
    """Aggregate evaluation results into summary metrics.

    Groups results by retriever type and difficulty, then calculates
    the proportion of queries that hit at each k value.

    Args:
        results: List of EvalResult objects.
        k_values: List of k values used in evaluation.

    Returns:
        Nested dict with aggregated metrics by retriever and difficulty.
    """
    # Group results by (retriever_type, difficulty)
    groups: dict[tuple[str, str], list[EvalResult]] = {}
    for result in results:
        key = (result.retriever_type, result.difficulty)
        if key not in groups:
            groups[key] = []
        groups[key].append(result)

    # Calculate aggregated metrics
    aggregated: dict[str, dict[str, dict[str, float]]] = {}

    for (retriever_type, difficulty), group_results in groups.items():
        if retriever_type not in aggregated:
            aggregated[retriever_type] = {}

        count = len(group_results)
        metrics: dict[str, float] = {"count": float(count)}

        for k in k_values:
            hit_attr = f"hit_at_{k}"
            hit_count = sum(1 for r in group_results if r.hits.get(k, False))
            metrics[hit_attr] = hit_count / count if count > 0 else 0.0

        aggregated[retriever_type][difficulty] = metrics

    logger.debug(
        f"Aggregated {len(results)} results into "
        f"{len(aggregated)} retriever types"
    )

    return aggregated
