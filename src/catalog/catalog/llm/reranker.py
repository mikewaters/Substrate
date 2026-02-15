"""catalog.llm.reranker - LLM-as-judge reranking with position-aware blending.

Provides document reranking using MLX for local LLM inference,
with configurable doc vs chunk evaluation and position-aware score blending.

Example:
    from catalog.llm.reranker import Reranker
    from catalog.search.models import SearchResult

    reranker = Reranker()
    results = await reranker.rerank(query, candidates)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol

from agentlayer.logging import get_logger
from pydantic import BaseModel, Field

from catalog.llm.prompts import RERANK_SYSTEM, format_rerank_prompt
from catalog.llm.provider import MLXProvider
from catalog.search.models import SearchResult

if TYPE_CHECKING:
    from llama_index.core.schema import NodeWithScore

    from catalog.store.llm_cache import LLMCache

__all__ = [
    "CachedReranker",
    "Reranker",
    "RerankConfig",
    "RerankScore",
    "blend_scores",
    "get_position_weight",
]

logger = get_logger(__name__)


class RerankConfig(BaseModel):
    """Configuration for reranking behavior.

    Attributes:
        mode: What text to evaluate - "chunk" uses chunk_text if available,
            "document" always fetches full document (not implemented yet).
        max_doc_chars: Maximum characters to send to LLM.
        temperature: LLM sampling temperature (0.0 for deterministic).
        max_tokens: Maximum tokens for LLM response.
    """

    mode: Literal["chunk", "document"] = Field(
        default="chunk",
        description="Evaluate chunk text or full document",
    )
    max_doc_chars: int = Field(
        default=2000,
        ge=100,
        le=10000,
        description="Max chars to send to LLM",
    )
    temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description="LLM sampling temperature",
    )
    max_tokens: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Max tokens for response",
    )


class RerankScore(BaseModel):
    """Rerank score for a single result.

    Attributes:
        path: Document path.
        dataset_name: Source dataset.
        relevant: Whether LLM judged document relevant.
        confidence: Confidence in judgment (0.1 or 0.9).
        score: Relevance score derived from judgment.
        raw_response: Raw LLM response text.
    """

    path: str
    dataset_name: str
    relevant: bool
    confidence: float = Field(ge=0.0, le=1.0)
    score: float = Field(ge=0.0, le=1.0)
    raw_response: str


def get_position_weight(rank: int) -> float:
    """Get RRF weight for position-aware blending.

    Position-aware strategy:
    - Rank 1-3: 75% RRF (top results usually correct)
    - Rank 4-10: 60% RRF (balanced)
    - Rank 11+: 40% RRF (trust reranker for borderline)

    Args:
        rank: 0-indexed position in results.

    Returns:
        Weight for RRF score (1 - weight goes to reranker).
    """
    if rank < 3:
        return 0.75
    elif rank < 10:
        return 0.60
    else:
        return 0.40


def blend_scores(
    results: list[SearchResult],
    rerank_scores: list[RerankScore],
) -> list[SearchResult]:
    """Blend RRF scores with reranker scores using position-aware weighting.

    Args:
        results: Original search results (ordered by RRF/hybrid score).
        rerank_scores: Reranking scores from LLM evaluation.

    Returns:
        New list of SearchResult with blended scores, re-sorted.
    """
    # Build lookup by (path, dataset_name)
    score_map = {(r.path, r.dataset_name): r for r in rerank_scores}

    blended = []
    for rank, result in enumerate(results):
        key = (result.path, result.dataset_name)
        rerank = score_map.get(key)

        rrf_score = result.score
        if rerank:
            rerank_score = rerank.score
            weight = get_position_weight(rank)
            final_score = weight * rrf_score + (1 - weight) * rerank_score

            # Update scores dict with rerank info
            new_scores = dict(result.scores)
            new_scores["rerank"] = rerank_score
            new_scores["blend_weight"] = weight

            blended.append(
                SearchResult(
                    path=result.path,
                    dataset_name=result.dataset_name,
                    score=final_score,
                    snippet=result.snippet,
                    chunk_seq=result.chunk_seq,
                    chunk_pos=result.chunk_pos,
                    metadata=result.metadata,
                    scores=new_scores,
                )
            )

            logger.debug(
                f"Blend rank={rank + 1}: {result.path} | "
                f"rrf={rrf_score:.3f} rerank={rerank_score:.3f} "
                f"weight={weight:.0%} -> {final_score:.3f}"
            )
        else:
            # Keep original if no rerank score
            blended.append(result)

    # Re-sort by blended score
    blended.sort(key=lambda r: r.score, reverse=True)
    return blended


class Reranker:
    """LLM-as-judge document reranker.

    Uses MLX for local inference to judge document relevance,
    with position-aware score blending.

    Example:
        reranker = Reranker()
        reranked = await reranker.rerank(
            query="authentication patterns",
            results=search_results,
        )
    """

    def __init__(
        self,
        provider: MLXProvider | None = None,
        config: RerankConfig | None = None,
    ) -> None:
        """Initialize reranker.

        Args:
            provider: MLX provider instance. If not provided,
                creates one with default settings.
            config: Reranking configuration.
        """
        self._provider = provider
        self._config = config or RerankConfig()

    @property
    def provider(self) -> MLXProvider:
        """Get the LLM provider, creating if needed."""
        if self._provider is None:
            self._provider = MLXProvider()
        return self._provider

    async def score_single(
        self,
        query: str,
        text: str,
        path: str,
        dataset_name: str,
    ) -> RerankScore:
        """Score a single document/chunk for relevance.

        Args:
            query: Search query.
            text: Document or chunk text to evaluate.
            path: Document path.
            dataset_name: Source dataset name.

        Returns:
            RerankScore with relevance judgment.
        """
        prompt = format_rerank_prompt(
            query=query,
            document_text=text,
            max_doc_chars=self._config.max_doc_chars,
        )

        try:
            response = await self.provider.generate(
                prompt,
                system=RERANK_SYSTEM,
                max_tokens=self._config.max_tokens,
                temperature=self._config.temperature,
            )

            # Parse response
            answer = response.strip().lower()
            relevant = answer.startswith("yes")
            confidence = 0.9 if relevant else 0.1

            # Convert to 0-1 score
            # Yes -> 0.95, No -> 0.05 (leave room for edge cases)
            score = 0.95 if relevant else 0.05

            return RerankScore(
                path=path,
                dataset_name=dataset_name,
                relevant=relevant,
                confidence=confidence,
                score=score,
                raw_response=response[:50],
            )

        except Exception as e:
            logger.warning(f"Rerank failed for {path}: {e}")
            # Return neutral score on error
            return RerankScore(
                path=path,
                dataset_name=dataset_name,
                relevant=False,
                confidence=0.5,
                score=0.5,
                raw_response=f"error: {e}",
            )

    async def get_rerank_scores(
        self,
        query: str,
        results: list[SearchResult],
    ) -> list[RerankScore]:
        """Get raw reranking scores for results.

        Args:
            query: Search query.
            results: Search results to rerank.

        Returns:
            List of RerankScore for each result.
        """
        scores = []

        for i, result in enumerate(results):
            # Get text to evaluate based on mode
            snippet_text = result.snippet.text if result.snippet else None
            if self._config.mode == "chunk" and snippet_text:
                text = snippet_text
            else:
                # Fallback: use path as placeholder
                # (full document fetch not implemented)
                text = snippet_text or f"[Document: {result.path}]"

            score = await self.score_single(
                query=query,
                text=text,
                path=result.path,
                dataset_name=result.dataset_name,
            )
            scores.append(score)

            rel_str = "Yes" if score.relevant else "No"
            logger.debug(
                f"[{i + 1}/{len(results)}] {result.path}: "
                f"{rel_str} (score={score.score:.2f})"
            )

        return scores

    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
    ) -> list[SearchResult]:
        """Rerank results with position-aware score blending.

        This is the main entry point for reranking. It:
        1. Gets LLM relevance scores for each result
        2. Blends with RRF scores using position-aware weights
        3. Re-sorts by blended score

        Args:
            query: Search query.
            results: Search results to rerank.

        Returns:
            Reranked results sorted by blended score.
        """
        if not results:
            return results

        import time

        start = time.perf_counter()
        logger.debug(f"Reranking {len(results)} results for query: {query[:50]!r}")

        # Get raw rerank scores
        rerank_scores = await self.get_rerank_scores(query, results)

        # Blend with position-aware weighting
        reranked = blend_scores(results, rerank_scores)

        elapsed = (time.perf_counter() - start) * 1000
        relevant_count = sum(1 for s in rerank_scores if s.relevant)
        logger.debug(
            f"Reranking complete: {relevant_count}/{len(results)} relevant, "
            f"{elapsed:.1f}ms"
        )

        return reranked


class RerankerProtocol(Protocol):
    """Protocol for reranker implementations that support caching.

    Defines the interface for rerankers that can be wrapped with CachedReranker.
    The rerank method operates on LlamaIndex NodeWithScore objects.
    """

    def rerank(
        self,
        nodes: list["NodeWithScore"],
        query: str,
        top_n: int | None = None,
    ) -> list["NodeWithScore"]:
        """Rerank nodes and return top_n results."""
        ...


class CachedReranker:
    """Wrapper around Reranker with LLM cache integration.

    Caches rerank scores by content hash to avoid redundant LLM calls for
    previously scored document chunks. Supports partial cache hits where
    only uncached nodes are sent to the underlying reranker.

    The cache key is constructed from:
    - query: The search query string
    - content_hash: From node.metadata["content_hash"] (fallback to node_id)
    - model_name: Identifier for the reranker model

    Attributes:
        reranker: The underlying reranker implementation.
        cache: LLMCache instance for persistent caching.
        model_name: Model identifier used in cache keys.

    Example:
        from catalog.store.llm_cache import LLMCache
        from catalog.search.rerank import Reranker

        with get_session() as session:
            cache = LLMCache(session)
            reranker = Reranker()
            cached = CachedReranker(reranker, cache, model_name="gpt-4o-mini")

            # First call: reranks all nodes, caches scores
            results = cached.rerank("search query", nodes, top_n=10)

            # Second call: uses cached scores for previously seen nodes
            results = cached.rerank("search query", nodes, top_n=10)
    """

    def __init__(
        self,
        reranker: RerankerProtocol,
        cache: "LLMCache",
        model_name: str = "default",
    ) -> None:
        """Initialize the CachedReranker.

        Args:
            reranker: The underlying reranker to wrap.
            cache: LLMCache instance for storing/retrieving scores.
            model_name: Model identifier for cache key construction.
                Defaults to "default".
        """
        self.reranker = reranker
        self.cache = cache
        self.model_name = model_name

    def _get_node_hash(self, node: "NodeWithScore") -> str:
        """Get content hash for a node, falling back to node_id.

        Args:
            node: The NodeWithScore to get hash for.

        Returns:
            Content hash from metadata or node_id as fallback.
        """
        content_hash = node.node.metadata.get("content_hash")
        if content_hash:
            return str(content_hash)
        return node.node.node_id or str(id(node))

    def rerank(
        self,
        query: str,
        nodes: list["NodeWithScore"],
        top_n: int | None = None,
    ) -> list["NodeWithScore"]:
        """Rerank nodes with cache integration.

        Checks the cache for previously computed scores, reranks only
        uncached nodes, stores new scores, and merges results.

        Args:
            query: The search query string.
            nodes: List of NodeWithScore objects to rerank.
            top_n: Number of top results to return. If None, returns all.

        Returns:
            List of NodeWithScore objects sorted by score, limited to top_n.
        """
        from llama_index.core.schema import NodeWithScore as NWS

        if not nodes:
            logger.debug("No nodes to rerank, returning empty list")
            return []

        # Separate cached and uncached nodes
        cached_nodes: list[NWS] = []
        uncached_nodes: list[NWS] = []
        cached_scores: dict[str, float] = {}

        for node in nodes:
            node_hash = self._get_node_hash(node)
            cached_score = self.cache.get_rerank(query, node_hash, self.model_name)

            if cached_score is not None:
                cached_scores[node_hash] = cached_score
                cached_nodes.append(node)
            else:
                uncached_nodes.append(node)

        cache_hits = len(cached_nodes)
        cache_misses = len(uncached_nodes)
        logger.debug(
            f"Rerank cache: {cache_hits} hits, {cache_misses} misses "
            f"for query '{query[:50]}...'"
        )

        # Rerank uncached nodes
        reranked_uncached: list[NWS] = []
        if uncached_nodes:
            reranked_uncached = self.reranker.rerank(
                nodes=uncached_nodes,
                query=query,
                top_n=None,  # Get all scores, we'll limit later
            )

            # Cache the new scores
            for node in reranked_uncached:
                node_hash = self._get_node_hash(node)
                score = node.score or 0.0
                self.cache.set_rerank(query, node_hash, self.model_name, score)

            logger.debug(f"Cached {len(reranked_uncached)} new rerank scores")

        # Update cached nodes with their cached scores
        updated_cached: list[NWS] = []
        for node in cached_nodes:
            node_hash = self._get_node_hash(node)
            cached_score = cached_scores[node_hash]
            # Create new NodeWithScore with cached score using model_copy
            updated_node = node.model_copy(update={"score": cached_score})
            updated_cached.append(updated_node)

        # Merge and sort all results
        all_results = reranked_uncached + updated_cached
        all_results.sort(key=lambda n: n.score or 0.0, reverse=True)

        # Limit to top_n
        if top_n is not None:
            all_results = all_results[:top_n]

        logger.debug(
            f"Rerank complete: {len(all_results)} results "
            f"(from {cache_hits} cached + {len(reranked_uncached)} reranked)"
        )

        return all_results
