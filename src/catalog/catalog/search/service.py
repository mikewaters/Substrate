"""catalog.search.service - Search service with full QMD feature parity.

Provides the unified search orchestrator integrating:
- Query expansion (lex/vec/HyDE)
- Weighted RRF hybrid retrieval
- Cached LLM reranking
- Top-rank bonuses

Example usage:
    from catalog.search.service import SearchService, search
    from catalog.search.models import SearchCriteria
    from catalog.store.database import get_session
    from catalog.store.session_context import use_session

    # Using convenience function
    results = search(SearchCriteria(
        query="python async patterns",
        mode="hybrid",
        rerank=True,
    ))

    # Using service directly
    with get_session() as session:
        with use_session(session):
            service = SearchService(session)
            results = service.search(SearchCriteria(
                query="machine learning",
                rerank=True,
            ))
"""

import asyncio
from typing import TYPE_CHECKING, Any

from agentlayer.logging import get_logger

from catalog.core.settings import get_settings
from catalog.search.models import SearchCriteria, SearchResult, SearchResults
from catalog.store.llm_cache import LLMCache

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from catalog.llm.reranker import CachedReranker
    from catalog.search.fts_chunk import FTSChunkRetriever
    from catalog.search.hybrid import HybridRetriever
    from catalog.search.postprocessors import (
        PerDocDedupePostprocessor,
        TopRankBonusPostprocessor,
    )
    from catalog.search.query_expansion import QueryExpansionTransform
    from catalog.search.vector import VectorSearch
    from catalog.store.vector import VectorStoreManager

__all__ = ["SearchService", "search"]

logger = get_logger(__name__)


class SearchService:
    """Search orchestrator with full QMD feature parity.

    Provides unified search interface with:
    - Query expansion via LLM (lex/vec/HyDE variants)
    - Weighted RRF fusion for hybrid search
    - Cached LLM-as-judge reranking
    - Top-rank bonuses for high-confidence results

    All components are lazy-loaded on first use to minimize startup time.

    Attributes:
        session: SQLAlchemy session for database access.
        _settings: RAGSettings instance.
        _cache: Lazy-loaded LLMCache instance.
        _query_expander: Lazy-loaded QueryExpansionTransform.
        _hybrid_retriever: Lazy-loaded HybridRetriever.
        _cached_reranker: Lazy-loaded CachedReranker.
    """

    def __init__(self, session: "Session") -> None:
        """Initialize the SearchService.

        Args:
            session: SQLAlchemy session for database access.
        """
        self.session = session
        self._settings = get_settings().rag
        self._cache: LLMCache | None = None
        self._query_expander: "QueryExpansionTransform | None" = None
        self._hybrid_retriever_factory: "HybridRetriever | None" = None
        self._cached_reranker: "CachedReranker | None" = None
        self._fts_search: "FTSChunkRetriever | None" = None
        self._vector_search: "VectorSearch | None" = None
        self._vector_manager: "VectorStoreManager | None" = None

    def _ensure_vector_manager(self) -> "VectorStoreManager":
        """Lazy-load shared VectorStoreManager.

        A single manager instance avoids creating multiple local Qdrant clients
        in one process, which would contend on the same on-disk lock file.
        """
        if self._vector_manager is None:
            from catalog.store.vector import VectorStoreManager

            self._vector_manager = VectorStoreManager()
        return self._vector_manager

    @property
    def cache(self) -> LLMCache:
        """Get or create LLMCache instance."""
        if self._cache is None:
            self._cache = LLMCache(
                session=self.session,
                ttl_hours=self._settings.cache_ttl_hours,
            )
        return self._cache

    def _ensure_query_expander(self) -> "QueryExpansionTransform":
        """Lazy-load QueryExpansionTransform."""
        if self._query_expander is None:
            from catalog.search.query_expansion import QueryExpansionTransform

            logger.debug("Lazy-loading QueryExpansionTransform")
            self._query_expander = QueryExpansionTransform(session=self.session)
        return self._query_expander

    def _ensure_hybrid_retriever(self) -> "HybridRetriever":
        """Lazy-load HybridRetriever factory."""
        if self._hybrid_retriever_factory is None:
            from catalog.search.hybrid import HybridRetriever

            logger.debug("Lazy-loading HybridRetriever")
            self._hybrid_retriever_factory = HybridRetriever(
                self.session,
                vector_manager=self._ensure_vector_manager(),
            )
        return self._hybrid_retriever_factory

    def _ensure_cached_reranker(self) -> "CachedReranker":
        """Lazy-load CachedReranker."""
        if self._cached_reranker is None:
            from catalog.llm.reranker import CachedReranker
            from catalog.search.rerank import Reranker

            logger.debug("Lazy-loading CachedReranker")
            base_reranker = Reranker()
            self._cached_reranker = CachedReranker(
                reranker=base_reranker,
                cache=self.cache,
            )
        return self._cached_reranker

    def _ensure_fts_search(self) -> "FTSChunkRetriever":
        """Lazy-load FTSChunkRetriever."""
        if self._fts_search is None:
            from catalog.search.fts_chunk import FTSChunkRetriever

            logger.debug("Lazy-loading FTSChunkRetriever")
            self._fts_search = FTSChunkRetriever()
        return self._fts_search

    def _ensure_vector_search(self) -> "VectorSearch":
        """Lazy-load VectorSearch."""
        if self._vector_search is None:
            from catalog.search.vector import VectorSearch

            logger.debug("Lazy-loading VectorSearch")
            self._vector_search = VectorSearch(
                vector_manager=self._ensure_vector_manager()
            )
        return self._vector_search

    def search(self, criteria: SearchCriteria) -> SearchResults:
        """Execute search with query expansion, weighted RRF, and caching.

        Pipeline:
        1. Query expansion (if enabled)
        2. Dispatch to appropriate search mode. For vector/hybrid retrieval,
           query-time embeddings are resolved by vector-store provenance so
           the matching embedding model identity is used per stored profile.
        3. Apply top-rank bonus
        4. Rerank (if enabled)
        5. Return results

        Args:
            criteria: Search criteria specifying query, mode, filters,
                and reranking options.

        Returns:
            SearchResults containing matching documents ordered by score.
        """
        import time

        start = time.perf_counter()
        debug_info: dict[str, Any] = {}

        # 1. Query expansion (if enabled and not pure FTS)
        expansion_result = None
        if self._settings.expansion_enabled and criteria.mode != "fts":
            try:
                expander = self._ensure_query_expander()
                expansion_result = asyncio.run(expander.expand(criteria.query))
                debug_info["expansion"] = {
                    "lex": expansion_result.lex_expansions,
                    "vec": expansion_result.vec_expansions,
                    "hyde": expansion_result.hyde_passage,
                }
            except Exception as e:
                logger.warning(f"Query expansion failed: {e}")

        # 2. Dispatch based on mode
        effective_limit = (
            criteria.rerank_candidates if criteria.rerank else criteria.limit
        )

        if criteria.mode == "fts":
            results = self.search_fts(
                criteria.query,
                criteria.dataset_name,
                effective_limit,
            )
        elif criteria.mode == "vector":
            results = self.search_vector(
                criteria.query,
                criteria.dataset_name,
                effective_limit,
            )
        else:  # hybrid (default)
            results = self.search_hybrid(
                criteria.query,
                criteria.dataset_name,
                effective_limit,
                expansion_result=expansion_result,
            )

        search_elapsed_ms = (time.perf_counter() - start) * 1000
        debug_info["search_time_ms"] = search_elapsed_ms
        debug_info["candidates_retrieved"] = len(results.results)

        # 3. Apply top-rank bonus
        if results.results:
            results = self._apply_top_rank_bonus(results)

        # 4. Rerank if requested
        if criteria.rerank and results.results:
            rerank_start = time.perf_counter()
            results = self._apply_rerank(results, criteria.query, criteria.limit)
            debug_info["rerank_time_ms"] = (time.perf_counter() - rerank_start) * 1000
        else:
            # Apply limit without reranking
            results = SearchResults(
                results=results.results[: criteria.limit],
                query=results.query,
                mode=results.mode,
                total_candidates=results.total_candidates,
                timing_ms=results.timing_ms,
            )

        total_elapsed_ms = (time.perf_counter() - start) * 1000

        logger.debug(
            f"SearchService.search({criteria.mode}) for '{criteria.query[:50]}...' "
            f"returned {len(results.results)} results in {total_elapsed_ms:.1f}ms"
        )

        return SearchResults(
            results=results.results,
            query=criteria.query,
            mode=criteria.mode,
            total_candidates=len(results.results),
            timing_ms=total_elapsed_ms,
        )

    def search_fts(
        self,
        query: str,
        dataset_name: str | None = None,
        limit: int | None = None,
    ) -> SearchResults:
        """Execute FTS search.

        Args:
            query: Search query string.
            dataset_name: Optional dataset filter.
            limit: Maximum results to return.

        Returns:
            SearchResults from FTS search.
        """
        from llama_index.core.schema import QueryBundle

        limit = limit or self._settings.fts_top_k
        fts = self._ensure_fts_search()

        # Apply dataset filter at the retriever level so FTS5 filters
        # via source_doc_id prefix rather than post-filtering on a
        # metadata key that doesn't exist in FTS results.
        fts.dataset_name = dataset_name
        fts.similarity_top_k = limit

        # Use the retriever interface
        query_bundle = QueryBundle(query_str=query)
        nodes = fts.retrieve(query_bundle)

        # Convert to SearchResults
        results = self._nodes_to_search_results(nodes[:limit])

        return SearchResults(
            results=results,
            query=query,
            mode="fts",
            total_candidates=len(results),
            timing_ms=0,
        )

    def search_vector(
        self,
        query: str,
        dataset_name: str | None = None,
        limit: int | None = None,
    ) -> SearchResults:
        """Execute vector search.

        Args:
            query: Search query string.
            dataset_name: Optional dataset filter.
            limit: Maximum results to return.

        Returns:
            SearchResults from vector search.
        """
        limit = limit or self._settings.vector_top_k
        vector = self._ensure_vector_search()

        results = vector.search(
            query=query,
            top_k=limit,
            dataset_name=dataset_name,
        )

        return SearchResults(
            results=results,
            query=query,
            mode="vector",
            total_candidates=len(results),
            timing_ms=0,
        )

    def search_hybrid(
        self,
        query: str,
        dataset_name: str | None = None,
        limit: int | None = None,
        expansion_result: Any = None,
    ) -> SearchResults:
        """Execute hybrid search with weighted RRF fusion.

        Args:
            query: Search query string.
            dataset_name: Optional dataset filter.
            limit: Maximum results to return.
            expansion_result: Optional QueryExpansionResult for multi-query search.

        Returns:
            SearchResults from hybrid search.
        """
        from llama_index.core.schema import QueryBundle

        limit = limit or self._settings.fusion_top_k
        hybrid_factory = self._ensure_hybrid_retriever()

        # Build retriever
        retriever = hybrid_factory.build(dataset_name=dataset_name, fusion_top_k=limit)

        # Execute search
        query_bundle = QueryBundle(query_str=query)
        nodes = retriever.retrieve(query_bundle)

        # Convert to SearchResults
        results = self._nodes_to_search_results(nodes)

        return SearchResults(
            results=results,
            query=query,
            mode="hybrid",
            total_candidates=len(results),
            timing_ms=0,
        )

    def _build_snippet(self, chunk_text: str | None, doc_path: str) -> "SnippetResult | None":
        """Build a SnippetResult from chunk text.

        Args:
            chunk_text: The chunk text content. Returns None if empty/None.
            doc_path: Document path for the diff header.

        Returns:
            SnippetResult or None if no text available.
        """
        if not chunk_text:
            return None

        from catalog.search.formatting import build_snippet
        from catalog.search.models import SnippetResult

        s = build_snippet(chunk_text, doc_path)
        return SnippetResult(
            text=s.text,
            start_line=s.start_line,
            end_line=s.end_line,
            header=s.header,
        )

    def _nodes_to_search_results(self, nodes: list) -> list[SearchResult]:
        """Convert LlamaIndex nodes to SearchResult objects.

        Args:
            nodes: List of NodeWithScore objects.

        Returns:
            List of SearchResult objects.
        """
        results = []
        for node in nodes:
            metadata = node.node.metadata or {}

            # Extract source info
            source_doc_id = metadata.get("source_doc_id", "")
            if ":" in source_doc_id:
                dataset_name, path = source_doc_id.split(":", 1)
            else:
                dataset_name = metadata.get("dataset_name", "")
                path = metadata.get("file_path", metadata.get("path", ""))

            chunk_text = node.node.get_content()
            snippet = self._build_snippet(chunk_text, path)

            results.append(
                SearchResult(
                    path=path,
                    dataset_name=dataset_name,
                    score=node.score or 0.0,
                    snippet=snippet,
                    chunk_seq=metadata.get("chunk_seq"),
                    chunk_pos=metadata.get("chunk_pos"),
                    metadata=metadata,
                    scores={"retrieval": node.score or 0.0},
                )
            )
        return results

    def _apply_top_rank_bonus(self, results: SearchResults) -> SearchResults:
        """Apply top-rank bonus to results.

        Args:
            results: SearchResults to modify.

        Returns:
            SearchResults with bonus scores applied.
        """
        rank_1_bonus = self._settings.rrf_rank1_bonus
        rank_23_bonus = self._settings.rrf_rank23_bonus

        modified_results = []
        for i, result in enumerate(results.results):
            bonus = 0.0
            if i == 0:
                bonus = rank_1_bonus
            elif i <= 2:
                bonus = rank_23_bonus

            modified_results.append(
                SearchResult(
                    path=result.path,
                    dataset_name=result.dataset_name,
                    score=result.score + bonus,
                    snippet=result.snippet,
                    chunk_seq=result.chunk_seq,
                    chunk_pos=result.chunk_pos,
                    metadata=result.metadata,
                    scores={**result.scores, "bonus": bonus},
                )
            )

        # Re-sort by score
        modified_results.sort(key=lambda r: r.score, reverse=True)

        return SearchResults(
            results=modified_results,
            query=results.query,
            mode=results.mode,
            total_candidates=results.total_candidates,
            timing_ms=results.timing_ms,
        )

    def _apply_rerank(
        self,
        results: SearchResults,
        query: str,
        limit: int,
    ) -> SearchResults:
        """Apply cached LLM reranking to results.

        Args:
            results: SearchResults to rerank.
            query: Query for relevance evaluation.
            limit: Maximum results after reranking.

        Returns:
            Reranked SearchResults.
        """
        from llama_index.core.schema import NodeWithScore, TextNode

        reranker = self._ensure_cached_reranker()

        # Convert to nodes
        nodes = []
        result_map = {}
        for i, result in enumerate(results.results):
            node_id = f"result_{i}"
            metadata = {
                "source_doc_id": f"{result.dataset_name}:{result.path}",
                "content_hash": result.metadata.get("content_hash", node_id)
                if result.metadata
                else node_id,
                **(result.metadata or {}),
            }

            node = TextNode(
                id_=node_id,
                text=result.snippet.text if result.snippet else "",
                metadata=metadata,
            )
            nodes.append(NodeWithScore(node=node, score=result.score))
            result_map[node_id] = result

        logger.debug(f"Reranking {len(nodes)} candidates")

        # Apply reranking
        reranked = reranker.rerank(query=query, nodes=nodes, top_n=limit)

        # Convert back
        reranked_results = []
        for node in reranked:
            original = result_map.get(node.node.id_)
            if original:
                reranked_results.append(
                    SearchResult(
                        path=original.path,
                        dataset_name=original.dataset_name,
                        score=node.score or 0.0,
                        snippet=original.snippet,
                        chunk_seq=original.chunk_seq,
                        chunk_pos=original.chunk_pos,
                        metadata=original.metadata,
                        scores={**original.scores, "rerank": node.score or 0.0},
                    )
                )

        return SearchResults(
            results=reranked_results,
            query=query,
            mode=results.mode,
            total_candidates=len(reranked_results),
            timing_ms=results.timing_ms,
        )


def search(criteria: SearchCriteria) -> SearchResults:
    """Search with query expansion, weighted RRF, and caching.

    Convenience function that creates a session and SearchService
    for one-off searches.

    Args:
        criteria: Search criteria.

    Returns:
        SearchResults from search.
    """
    from catalog.store.database import get_session
    from catalog.store.session_context import use_session

    with get_session() as session:
        with use_session(session):
            service = SearchService(session)
            return service.search(criteria)
