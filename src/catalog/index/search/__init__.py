"""index.search - Search abstractions.

Full-text search, vector search, hybrid retrieval (RRF),
and LLM-as-judge reranking. Called from the orchestration layer.

Example usage:
    from index.search import search

    # Search with automatic session management
    results = search(SearchCriteria(query="python async", mode="hybrid"))
    for r in results.results:
        print(f"{r.path}: {r.score:.3f}")

    # For more control, use SearchService directly
    from index.search import SearchService, SearchCriteria
    service = SearchService(session)
    results = service.search(SearchCriteria(query="...", mode="fts"))
"""

from index.search.formatting import Snippet, build_snippet, extract_snippet
from index.search.fts import FTSSearch
from index.search.fts_chunk import FTSChunkRetriever
from index.search.hybrid import HybridRetriever, WeightedRRFRetriever
from index.search.models import SearchCriteria, SearchResult, SearchResults, SnippetResult
from index.search.postprocessors import (
    KeywordChunkSelector,
    PerDocDedupePostprocessor,
    ScoreNormalizerPostprocessor,
    TopRankBonusPostprocessor,
)
from index.search.query_expansion import QueryExpansionResult, QueryExpansionTransform
from index.search.rerank import Reranker
from index.search.service import SearchService, search


__all__ = [
    "search",
    "build_snippet",
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
    "SnippetResult",
    "TopRankBonusPostprocessor",
    "WeightedRRFRetriever",
]
