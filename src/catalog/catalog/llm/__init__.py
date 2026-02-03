"""catalog.llm - LLM provider abstractions.

Normalizes LLM providers (MLX via mlx-lm).
Provides LLM-as-judge reranking with position-aware score blending.

Example:
    from catalog.llm import Reranker, MLXProvider

    reranker = Reranker()
    results = await reranker.rerank(query, search_results)
"""

from catalog.llm.prompts import RERANK_PROMPT, RERANK_SYSTEM, format_rerank_prompt
from catalog.llm.provider import LLMProviderError, MLXProvider
from catalog.llm.reranker import (
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
    "RerankConfig",
    "RerankScore",
    "Reranker",
    "blend_scores",
    "get_position_weight",
    # Prompts
    "RERANK_PROMPT",
    "RERANK_SYSTEM",
    "format_rerank_prompt",
]
