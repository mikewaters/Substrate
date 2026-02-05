"""catalog.llm - LLM provider abstractions.

Normalizes LLM providers (MLX via mlx-lm).
Provides LLM-as-judge reranking with position-aware score blending.

Example:
    from catalog.llm import Reranker, MLXProvider

    reranker = Reranker()
    results = await reranker.rerank(query, search_results)
"""

from catalog.llm.prompts import (
    QUERY_EXPANSION_PROMPT,
    QUERY_EXPANSION_SYSTEM,
    RERANK_PROMPT,
    RERANK_SYSTEM,
    format_rerank_prompt,
)
from catalog.llm.provider import LLMProviderError, MLXProvider
from catalog.llm.reranker import (
    CachedReranker,
    RerankConfig,
    Reranker,
    RerankScore,
    blend_scores,
    get_position_weight,
)

__all__ = [
    # Provider
    "LLMProviderError",
    "MLXProvider",
    # Reranker
    "CachedReranker",
    "RerankConfig",
    "RerankScore",
    "Reranker",
    "blend_scores",
    "get_position_weight",
    # Prompts
    "QUERY_EXPANSION_PROMPT",
    "QUERY_EXPANSION_SYSTEM",
    "RERANK_PROMPT",
    "RERANK_SYSTEM",
    "format_rerank_prompt",
]
