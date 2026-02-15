"""catalog.search.rerank - LLM-as-judge reranking for search results.

Supports two providers controlled by settings.rag.rerank_provider:
- "mlx": Local MLX inference via MLXProvider (default)
- "openai": OpenAI gpt-4o-mini via LlamaIndex LLMRerank

Example usage:
    from catalog.search.rerank import Reranker
    from llama_index.core.schema import NodeWithScore, TextNode

    reranker = Reranker()
    reranked_nodes = reranker.rerank(
        nodes=nodes_with_scores,
        query="machine learning concepts",
        top_n=5,
    )
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from agentlayer.logging import get_logger

from catalog.core.settings import get_settings

if TYPE_CHECKING:
    from llama_index.core.schema import NodeWithScore

__all__ = ["Reranker"]

logger = get_logger(__name__)


class Reranker:
    """LLM-as-judge reranker with pluggable provider (MLX or OpenAI).

    Provider is selected from settings.rag.rerank_provider at init time.
    Both paths produce the same interface: rerank(nodes, query, top_n).

    Attributes:
        _provider: The configured provider name ("mlx" or "openai").
        _default_top_n: Default number of top results to return.
    """

    def __init__(
        self,
        default_top_n: int = 10,
        choice_batch_size: int = 5,
    ) -> None:
        """Initialize the Reranker.

        Args:
            default_top_n: Default number of top results to return when
                top_n is not specified in rerank(). Defaults to 10.
            choice_batch_size: Nodes per LLM call (OpenAI path only).
        """
        self._default_top_n = default_top_n
        self._choice_batch_size = choice_batch_size
        self._provider = get_settings().rag.rerank_provider

        # Lazy-loaded internals
        self._mlx_provider = None
        self._openai_llm = None
        self._openai_reranker = None

    def rerank(
        self,
        nodes: list[NodeWithScore],
        query: str,
        top_n: int | None = None,
    ) -> list[NodeWithScore]:
        """Rerank nodes using LLM-as-judge relevance scoring.

        Args:
            nodes: List of NodeWithScore objects to rerank.
            query: The search query string for relevance evaluation.
            top_n: Number of top results to return. If None, uses default_top_n.

        Returns:
            List of NodeWithScore objects reordered by LLM relevance,
            limited to top_n results.
        """
        if not nodes:
            logger.debug("No nodes to rerank, returning empty list")
            return []

        effective_top_n = top_n if top_n is not None else self._default_top_n

        logger.debug(
            f"Reranking {len(nodes)} nodes via {self._provider}, top_n={effective_top_n}"
        )

        if self._provider == "mlx":
            result = self._rerank_mlx(nodes, query, effective_top_n)
        else:
            result = self._rerank_openai(nodes, query, effective_top_n)

        logger.debug(f"Reranking complete: {len(nodes)} -> {len(result)} nodes")
        return result

    # -- MLX path ----------------------------------------------------------

    def _ensure_mlx(self):
        """Lazy-load MLXProvider."""
        if self._mlx_provider is None:
            from catalog.llm.provider import MLXProvider

            self._mlx_provider = MLXProvider()
        return self._mlx_provider

    def _rerank_mlx(
        self,
        nodes: list[NodeWithScore],
        query: str,
        top_n: int,
    ) -> list[NodeWithScore]:
        """Score each node with MLXProvider and return top_n by relevance."""
        from llama_index.core.schema import NodeWithScore as NWS

        from catalog.llm.prompts import RERANK_SYSTEM, format_rerank_prompt

        provider = self._ensure_mlx()

        async def _score_all():
            scores = []
            for node in nodes:
                text = node.node.get_content()
                prompt = format_rerank_prompt(query, text)
                try:
                    response = await provider.generate(
                        prompt,
                        system=RERANK_SYSTEM,
                        max_tokens=5,
                        temperature=0.0,
                    )
                    # "Yes" -> 1.0, anything else -> 0.0
                    is_relevant = response.strip().lower().startswith("yes")
                    scores.append(1.0 if is_relevant else 0.0)
                except Exception as e:
                    logger.warning(f"MLX rerank scoring failed for node: {e}")
                    scores.append(0.0)
            return scores

        # Run async scoring in sync context
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                scores = pool.submit(lambda: asyncio.run(_score_all())).result()
        else:
            scores = asyncio.run(_score_all())

        # Pair nodes with scores, sort descending, take top_n
        scored = sorted(zip(nodes, scores), key=lambda x: x[1], reverse=True)
        result = []
        for node, score in scored[:top_n]:
            result.append(NWS(node=node.node, score=score))

        return result

    # -- OpenAI path -------------------------------------------------------

    def _rerank_openai(
        self,
        nodes: list[NodeWithScore],
        query: str,
        top_n: int,
    ) -> list[NodeWithScore]:
        """Rerank using LlamaIndex LLMRerank with OpenAI.

        Falls back to MLX if OpenAI init or call fails (missing/expired key, etc.).
        """
        try:
            return self._rerank_openai_inner(nodes, query, top_n)
        except Exception as e:
            logger.warning(f"OpenAI reranking failed, falling back to MLX: {e}")
            return self._rerank_mlx(nodes, query, top_n)

    def _rerank_openai_inner(
        self,
        nodes: list[NodeWithScore],
        query: str,
        top_n: int,
    ) -> list[NodeWithScore]:
        """OpenAI reranking implementation (may raise on auth/network errors)."""
        from llama_index.core.schema import QueryBundle

        if self._openai_reranker is None or self._openai_reranker.top_n != top_n:
            from llama_index.core.postprocessor import LLMRerank

            if self._openai_llm is None:
                from llama_index.llms.openai import OpenAI as OpenAILLM

                logger.debug("Initializing OpenAI LLM for reranking")
                self._openai_llm = OpenAILLM(model="gpt-4o-mini", temperature=0.0)

            self._openai_reranker = LLMRerank(
                llm=self._openai_llm,
                choice_batch_size=self._choice_batch_size,
                top_n=top_n,
            )

        query_bundle = QueryBundle(query_str=query)
        return self._openai_reranker.postprocess_nodes(
            nodes=nodes,
            query_bundle=query_bundle,
        )
