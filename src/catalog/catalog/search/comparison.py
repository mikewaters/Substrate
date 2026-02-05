"""catalog.search.comparison - Side-by-side comparison of v1 and v2 search.

Provides utilities for comparing search results between SearchService (v1)
and SearchServiceV2 (v2), calculating overlap and ranking correlation metrics
to evaluate retrieval quality and consistency.

Example usage:
    from catalog.search.comparison import SearchComparison, ComparisonResult
    from catalog.search.models import SearchCriteria
    from catalog.store.database import get_session
    from catalog.store.session_context import use_session

    with get_session() as session:
        with use_session(session):
            comparison = SearchComparison(session)

            # Compare single query
            result = comparison.compare(SearchCriteria(
                query="python async patterns",
                mode="hybrid",
            ))
            print(f"Overlap@5: {result.overlap_at_5:.2%}")
            print(f"Rank correlation: {result.rank_correlation:.3f}")

            # Compare batch of queries
            queries = ["machine learning", "async error handling", "database design"]
            results = comparison.compare_batch(queries)
            summary = comparison.summary_report(results)
"""

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from agentlayer.logging import get_logger

from catalog.search.models import SearchCriteria, SearchResult

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

__all__ = ["ComparisonResult", "SearchComparison"]

logger = get_logger(__name__)


@dataclass
class ComparisonResult:
    """Result of comparing v1 and v2 search for a single query.

    Contains timing, results, and statistical metrics for evaluating
    the similarity between v1 (SearchService) and v2 (SearchServiceV2)
    search implementations.

    Attributes:
        query: The search query used for comparison.
        v1_results: Results from SearchService (v1).
        v2_results: Results from SearchServiceV2 (v2).
        v1_time_ms: Time taken by v1 search in milliseconds.
        v2_time_ms: Time taken by v2 search in milliseconds.
        overlap_at_5: Jaccard similarity of top 5 results (0-1).
        overlap_at_10: Jaccard similarity of top 10 results (0-1).
        rank_correlation: Spearman rank correlation of overlapping results (-1 to 1).
    """

    query: str
    v1_results: list[SearchResult] = field(default_factory=list)
    v2_results: list[SearchResult] = field(default_factory=list)
    v1_time_ms: float = 0.0
    v2_time_ms: float = 0.0
    overlap_at_5: float = 0.0
    overlap_at_10: float = 0.0
    rank_correlation: float = 0.0


class SearchComparison:
    """Compare v1 and v2 search results.

    Provides utilities for running the same query against both
    SearchService (v1) and SearchServiceV2 (v2), then computing
    metrics to evaluate consistency and quality differences.

    Attributes:
        session: SQLAlchemy session for database access.
        _v1_service: Lazy-loaded SearchService instance.
        _v2_service: Lazy-loaded SearchServiceV2 instance.
    """

    def __init__(self, session: "Session") -> None:
        """Initialize SearchComparison.

        Args:
            session: SQLAlchemy session for database access.
        """
        self.session = session
        self._v1_service = None
        self._v2_service = None

    def _ensure_v1_service(self):
        """Lazy-load SearchService (v1)."""
        if self._v1_service is None:
            from catalog.search.service import SearchService

            logger.debug("Lazy-loading SearchService (v1)")
            self._v1_service = SearchService()
        return self._v1_service

    def _ensure_v2_service(self):
        """Lazy-load SearchServiceV2 (v2)."""
        if self._v2_service is None:
            from catalog.search.service_v2 import SearchServiceV2

            logger.debug("Lazy-loading SearchServiceV2 (v2)")
            self._v2_service = SearchServiceV2(self.session)
        return self._v2_service

    def compare(self, criteria: SearchCriteria) -> ComparisonResult:
        """Run same query on v1 and v2, compare results.

        Executes the search criteria against both v1 (SearchService) and
        v2 (SearchServiceV2), timing each execution and computing overlap
        and ranking correlation metrics.

        Args:
            criteria: Search criteria to execute on both services.

        Returns:
            ComparisonResult containing results and metrics.
        """
        v1_service = self._ensure_v1_service()
        v2_service = self._ensure_v2_service()

        # Time and run v1
        v1_start = time.perf_counter()
        v1_results = v1_service.search(criteria)
        v1_time_ms = (time.perf_counter() - v1_start) * 1000

        # Time and run v2
        v2_start = time.perf_counter()
        v2_results = v2_service.search(criteria)
        v2_time_ms = (time.perf_counter() - v2_start) * 1000

        # Calculate metrics
        overlap_at_5 = self._jaccard(v1_results.results, v2_results.results, k=5)
        overlap_at_10 = self._jaccard(v1_results.results, v2_results.results, k=10)
        rank_correlation = self._spearman(v1_results.results, v2_results.results)

        logger.debug(
            f"Comparison for '{criteria.query[:50]}...': "
            f"v1={v1_time_ms:.1f}ms, v2={v2_time_ms:.1f}ms, "
            f"overlap@5={overlap_at_5:.2f}, rho={rank_correlation:.3f}"
        )

        return ComparisonResult(
            query=criteria.query,
            v1_results=v1_results.results,
            v2_results=v2_results.results,
            v1_time_ms=v1_time_ms,
            v2_time_ms=v2_time_ms,
            overlap_at_5=overlap_at_5,
            overlap_at_10=overlap_at_10,
            rank_correlation=rank_correlation,
        )

    def compare_batch(
        self,
        queries: list[str],
        mode: str = "hybrid",
        limit: int = 10,
        dataset_name: str | None = None,
    ) -> list[ComparisonResult]:
        """Compare multiple queries.

        Args:
            queries: List of query strings to compare.
            mode: Search mode to use (default: "hybrid").
            limit: Maximum results per query (default: 10).
            dataset_name: Optional dataset filter.

        Returns:
            List of ComparisonResult for each query.
        """
        results = []
        for query in queries:
            criteria = SearchCriteria(
                query=query,
                mode=mode,  # type: ignore
                limit=limit,
                dataset_name=dataset_name,
            )
            results.append(self.compare(criteria))
        return results

    def summary_report(self, results: list[ComparisonResult]) -> dict:
        """Generate summary statistics for a batch of comparisons.

        Computes aggregate metrics across all comparison results,
        including mean times, overlap percentages, and correlations.

        Args:
            results: List of ComparisonResult from compare_batch.

        Returns:
            Dictionary with summary statistics:
            - count: Number of comparisons
            - v1_mean_time_ms: Average v1 search time
            - v2_mean_time_ms: Average v2 search time
            - mean_overlap_at_5: Average Jaccard@5
            - mean_overlap_at_10: Average Jaccard@10
            - mean_rank_correlation: Average Spearman correlation
            - queries_with_no_overlap: Count where overlap@10 == 0
        """
        if not results:
            return {
                "count": 0,
                "v1_mean_time_ms": 0.0,
                "v2_mean_time_ms": 0.0,
                "mean_overlap_at_5": 0.0,
                "mean_overlap_at_10": 0.0,
                "mean_rank_correlation": 0.0,
                "queries_with_no_overlap": 0,
            }

        count = len(results)
        v1_mean = sum(r.v1_time_ms for r in results) / count
        v2_mean = sum(r.v2_time_ms for r in results) / count
        mean_overlap_5 = sum(r.overlap_at_5 for r in results) / count
        mean_overlap_10 = sum(r.overlap_at_10 for r in results) / count
        mean_correlation = sum(r.rank_correlation for r in results) / count
        no_overlap_count = sum(1 for r in results if r.overlap_at_10 == 0.0)

        return {
            "count": count,
            "v1_mean_time_ms": v1_mean,
            "v2_mean_time_ms": v2_mean,
            "mean_overlap_at_5": mean_overlap_5,
            "mean_overlap_at_10": mean_overlap_10,
            "mean_rank_correlation": mean_correlation,
            "queries_with_no_overlap": no_overlap_count,
        }

    def _jaccard(
        self,
        v1_results: list[SearchResult],
        v2_results: list[SearchResult],
        k: int,
    ) -> float:
        """Calculate Jaccard similarity of top K results.

        Jaccard index = |A intersection B| / |A union B|

        Args:
            v1_results: Results from v1 search.
            v2_results: Results from v2 search.
            k: Number of top results to consider.

        Returns:
            Jaccard similarity coefficient (0-1).
            Returns 0.0 if both result sets are empty.
        """
        v1_top_k = v1_results[:k]
        v2_top_k = v2_results[:k]

        # Extract document identifiers (dataset_name:path)
        v1_docs = {f"{r.dataset_name}:{r.path}" for r in v1_top_k}
        v2_docs = {f"{r.dataset_name}:{r.path}" for r in v2_top_k}

        if not v1_docs and not v2_docs:
            return 0.0

        intersection = v1_docs & v2_docs
        union = v1_docs | v2_docs

        return len(intersection) / len(union) if union else 0.0

    def _spearman(
        self,
        v1_results: list[SearchResult],
        v2_results: list[SearchResult],
    ) -> float:
        """Calculate Spearman rank correlation for overlapping documents.

        Computes rank correlation only for documents that appear in both
        result sets. Uses the standard Spearman formula:
        rho = 1 - (6 * sum(d^2)) / (n * (n^2 - 1))

        Args:
            v1_results: Results from v1 search.
            v2_results: Results from v2 search.

        Returns:
            Spearman correlation coefficient (-1 to 1).
            Returns 0.0 if fewer than 2 documents overlap.
        """
        # Build rank maps (1-indexed for standard Spearman)
        v1_ranks = {
            f"{r.dataset_name}:{r.path}": i + 1 for i, r in enumerate(v1_results)
        }
        v2_ranks = {
            f"{r.dataset_name}:{r.path}": i + 1 for i, r in enumerate(v2_results)
        }

        # Find overlapping documents
        overlap_docs = set(v1_ranks.keys()) & set(v2_ranks.keys())

        if len(overlap_docs) < 2:
            return 0.0

        # Calculate sum of squared rank differences
        d_squared_sum = sum(
            (v1_ranks[doc] - v2_ranks[doc]) ** 2 for doc in overlap_docs
        )

        n = len(overlap_docs)

        # Spearman formula: rho = 1 - (6 * sum(d^2)) / (n * (n^2 - 1))
        rho = 1 - (6 * d_squared_sum) / (n * (n**2 - 1))

        return rho
