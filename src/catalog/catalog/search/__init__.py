"""catalog.search - Search abstractions.

Full-text search, vector search, hybrid retrieval (RRF),
and LLM-as-judge reranking. Called from the orchestration layer.

Example usage:
    from catalog.search import search

    # Search with automatic session management
    results = search(SearchCriteria(query="python async", mode="hybrid"))
    for r in results.results:
        print(f"{r.path}: {r.score:.3f}")

    # For more control, use SearchService directly
    from catalog.search import SearchService, SearchCriteria
    service = SearchService(session)
    results = service.search(SearchCriteria(query="...", mode="fts"))
"""

from catalog.search.formatting import Snippet, extract_snippet
from catalog.search.fts import FTSSearch
from catalog.search.fts_chunk import FTSChunkRetriever
from catalog.search.hybrid import HybridRetriever, WeightedRRFRetriever
from catalog.search.models import SearchCriteria, SearchResult, SearchResults
from catalog.search.postprocessors import (
    KeywordChunkSelector,
    PerDocDedupePostprocessor,
    ScoreNormalizerPostprocessor,
    TopRankBonusPostprocessor,
)
from catalog.search.query_expansion import QueryExpansionResult, QueryExpansionTransform
from catalog.search.rerank import Reranker
from catalog.search.service import SearchService, search


__all__ = [
    "search",
    "extract_snippet",
    "FTSChunkRetriever",
    "FTSSearch",
    "HybridRetriever",
    "KeywordChunkSelector",
    "PerDocDedupePostprocessor",
    "QueryExpansionResult",
    "QueryExpansionTransform",
    "Reranker",
    "ScoreNormalizerPostprocessor",
    "SearchCriteria",
    "SearchResult",
    "SearchResults",
    "SearchService",
    "Snippet",
    "TopRankBonusPostprocessor",
    "WeightedRRFRetriever",
]
