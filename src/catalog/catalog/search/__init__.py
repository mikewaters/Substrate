"""catalog.search - Search abstractions.

Full-text search, vector search, hybrid retrieval (RRF),
and LLM-as-judge reranking. Called from the orchestration layer.

Example usage:
    from catalog.search import search

    # Simple search with automatic session management
    results = search("python async", mode="hybrid")
    for r in results.results:
        print(f"{r.path}: {r.score:.3f}")

    # For more control, use SearchService directly
    from catalog.search import SearchService, SearchCriteria
    service = SearchService()
    results = service.search(SearchCriteria(query="...", mode="fts"))
"""

from catalog.search.comparison import ComparisonResult, SearchComparison
from catalog.search.formatting import Snippet, extract_snippet
from catalog.search.fts import FTSSearch
from catalog.search.fts_chunk import FTSChunkRetriever
from catalog.search.hybrid_v2 import HybridRetrieverV2, WeightedRRFRetriever
from catalog.search.models import SearchCriteria, SearchResult, SearchResults
from catalog.search.postprocessors import (
    KeywordChunkSelector,
    PerDocDedupePostprocessor,
    ScoreNormalizerPostprocessor,
    TopRankBonusPostprocessor,
)
from catalog.search.query_expansion import QueryExpansionResult, QueryExpansionTransform
from catalog.search.rerank import Reranker
from catalog.search.service import SearchService
from catalog.search.service_v2 import SearchServiceV2, search_v2


def search(
    query: str,
    mode: str = "hybrid",
    limit: int = 10,
    dataset_name: str | None = None,
) -> SearchResults:
    """Execute a search with automatic session management.

    Convenience function that handles database session setup internally.
    For more control, use SearchService directly.

    Args:
        query: Search query string.
        mode: Search mode - "fts", "vector", or "hybrid".
        limit: Maximum results to return.
        dataset_name: Optional filter to specific dataset.

    Returns:
        SearchResults with matching documents.
    """
    from catalog.store.database import get_session
    from catalog.store.session_context import use_session

    with get_session() as session:
        with use_session(session):
            service = SearchService()
            return service.search(
                SearchCriteria(
                    query=query,
                    mode=mode,
                    limit=limit,
                    dataset_name=dataset_name,
                )
            )


__all__ = [
    "search",
    "search_v2",
    "ComparisonResult",
    "extract_snippet",
    "FTSChunkRetriever",
    "FTSSearch",
    "HybridRetrieverV2",
    "KeywordChunkSelector",
    "PerDocDedupePostprocessor",
    "QueryExpansionResult",
    "QueryExpansionTransform",
    "Reranker",
    "ScoreNormalizerPostprocessor",
    "SearchComparison",
    "SearchCriteria",
    "SearchResult",
    "SearchResults",
    "SearchService",
    "SearchServiceV2",
    "Snippet",
    "TopRankBonusPostprocessor",
    "WeightedRRFRetriever",
]
