"""catalog.search.query_expansion - Query expansion for RAG search.

Generates query expansions using an LLM to improve recall in hybrid search.
Produces three types of expansions:
- Lexical (lex): BM25-optimized keyword variants
- Semantic (vec): Reformulations for embedding similarity
- HyDE: Hypothetical document passage for dense retrieval

The expansions are parsed from structured LLM output and filtered for quality.
Results are cached via LLMCache to reduce redundant LLM calls.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from agentlayer.logging import get_logger
from sqlalchemy.orm import Session

from catalog.core.settings import get_settings
from catalog.llm.prompts import QUERY_EXPANSION_PROMPT, QUERY_EXPANSION_SYSTEM
from catalog.store.llm_cache import LLMCache

__all__ = [
    "QueryExpansionResult",
    "QueryExpansionTransform",
]

logger = get_logger(__name__)


@dataclass
class QueryExpansionResult:
    """Result of query expansion containing multiple query variants.

    Contains the original query plus expansions optimized for different
    retrieval methods (lexical/BM25 and semantic/vector).

    Attributes:
        original: The original search query.
        lex_expansions: BM25 keyword variants (1-3 expansions).
        vec_expansions: Semantic reformulations (1-3 expansions).
        hyde_passage: Hypothetical document passage (0-1).
    """

    original: str
    lex_expansions: list[str] = field(default_factory=list)
    vec_expansions: list[str] = field(default_factory=list)
    hyde_passage: str | None = None

    @property
    def all_queries(self) -> list[str]:
        """Return all queries including original and expansions.

        Returns:
            List with original query first, followed by lex and vec expansions.
        """
        return [self.original] + self.lex_expansions + self.vec_expansions

    @property
    def has_expansions(self) -> bool:
        """Check if any expansions were generated.

        Returns:
            True if any lex, vec, or hyde expansions exist.
        """
        return bool(self.lex_expansions or self.vec_expansions or self.hyde_passage)


class QueryExpansionTransform:
    """Transform that expands queries using an LLM.

    Uses structured prompts to generate lexical and semantic query variants.
    Integrates with LLMCache for persistent caching of results.

    Args:
        session: SQLAlchemy session for cache access.
        model_name: LLM model identifier for cache key generation.
            If None, defaults to "mlx-local".

    Example:
        with get_session() as session:
            transform = QueryExpansionTransform(session)
            result = await transform.expand("python async programming")
            print(result.lex_expansions)  # ["asyncio python", ...]
            print(result.vec_expansions)  # ["asynchronous programming in python", ...]
    """

    def __init__(
        self,
        session: Session,
        model_name: str | None = None,
    ) -> None:
        """Initialize the query expansion transform.

        Args:
            session: SQLAlchemy session for cache operations.
            model_name: Model identifier for cache keys. Defaults to "mlx-local".
        """
        self._session = session
        self._model_name = model_name or "mlx-local"
        self._cache = LLMCache(session)

    @property
    def _settings(self):
        """Lazy-load settings to allow test mocking."""
        return get_settings().rag

    async def expand(self, query: str) -> QueryExpansionResult:
        """Expand a query into multiple variants.

        Generates lexical and semantic expansions using an LLM.
        Returns cached results if available. Falls back to original
        query only on LLM failure.

        Args:
            query: The original search query.

        Returns:
            QueryExpansionResult with original and expanded queries.
        """
        if not self._settings.expansion_enabled:
            logger.debug("Query expansion disabled", query=query[:50])
            return QueryExpansionResult(original=query)

        # Check cache first
        cached = self._cache.get_expansion(query, self._model_name)
        if cached is not None:
            logger.debug("Query expansion cache hit", query=query[:50])
            return self._dict_to_result(query, cached)

        # Generate expansions via LLM
        try:
            result = await self._generate_expansions(query)
            # Cache the result
            self._cache.set_expansion(query, self._model_name, self._result_to_dict(result))
            return result
        except Exception as e:
            logger.warning("Query expansion failed, using original only", error=str(e))
            return QueryExpansionResult(original=query)

    async def _generate_expansions(self, query: str) -> QueryExpansionResult:
        """Generate expansions using the LLM.

        Args:
            query: The original search query.

        Returns:
            QueryExpansionResult with parsed expansions.
        """
        from catalog.llm.provider import MLXProvider

        provider = MLXProvider()

        prompt = QUERY_EXPANSION_PROMPT.format(
            query=query,
            max_lex=self._settings.expansion_max_lex,
            max_vec=self._settings.expansion_max_vec,
            include_hyde="yes" if self._settings.expansion_include_hyde else "no",
        )

        response = await provider.generate(
            prompt=prompt,
            system=QUERY_EXPANSION_SYSTEM,
            max_tokens=500,
            temperature=0.3,
        )

        result = self._parse_response(query, response)
        logger.debug(
            "Generated query expansions",
            query=query[:50],
            lex_count=len(result.lex_expansions),
            vec_count=len(result.vec_expansions),
            has_hyde=result.hyde_passage is not None,
        )
        return result

    def _parse_response(self, query: str, response: str) -> QueryExpansionResult:
        """Parse structured LLM response into QueryExpansionResult.

        Expects response format with lex:, vec:, and hyde: tags.

        Args:
            query: The original search query.
            response: Raw LLM response text.

        Returns:
            QueryExpansionResult with parsed and filtered expansions.
        """
        lex_expansions: list[str] = []
        vec_expansions: list[str] = []
        hyde_passage: str | None = None

        # Parse lex: lines
        lex_pattern = re.compile(r"^lex:\s*(.+)$", re.MULTILINE | re.IGNORECASE)
        for match in lex_pattern.finditer(response):
            expansion = match.group(1).strip()
            if expansion and self._is_quality_expansion(query, expansion):
                lex_expansions.append(expansion)

        # Parse vec: lines
        vec_pattern = re.compile(r"^vec:\s*(.+)$", re.MULTILINE | re.IGNORECASE)
        for match in vec_pattern.finditer(response):
            expansion = match.group(1).strip()
            if expansion and self._is_quality_expansion(query, expansion):
                vec_expansions.append(expansion)

        # Parse hyde: block (can be multiline)
        hyde_pattern = re.compile(r"^hyde:\s*(.+?)(?=^(?:lex:|vec:|$)|\Z)", re.MULTILINE | re.IGNORECASE | re.DOTALL)
        hyde_match = hyde_pattern.search(response)
        if hyde_match:
            hyde_text = hyde_match.group(1).strip()
            if hyde_text and self._settings.expansion_include_hyde:
                hyde_passage = hyde_text

        # Limit to configured maximums
        lex_expansions = lex_expansions[: self._settings.expansion_max_lex]
        vec_expansions = vec_expansions[: self._settings.expansion_max_vec]

        return QueryExpansionResult(
            original=query,
            lex_expansions=lex_expansions,
            vec_expansions=vec_expansions,
            hyde_passage=hyde_passage,
        )

    def _is_quality_expansion(self, original: str, expansion: str) -> bool:
        """Check if an expansion meets quality criteria.

        Expansions must contain at least one term from the original query
        to ensure relevance. This filters out completely unrelated expansions.

        Args:
            original: The original search query.
            expansion: The proposed expansion.

        Returns:
            True if the expansion passes quality filters.
        """
        # Normalize to lowercase for comparison
        original_lower = original.lower()
        expansion_lower = expansion.lower()

        # Extract terms (alphanumeric sequences)
        original_terms = set(re.findall(r"\b\w+\b", original_lower))
        expansion_terms = set(re.findall(r"\b\w+\b", expansion_lower))

        # Must have at least one overlapping term
        overlap = original_terms & expansion_terms
        if not overlap:
            logger.debug(
                "Filtered expansion: no term overlap",
                original=original[:30],
                expansion=expansion[:30],
            )
            return False

        # Expansion should not be identical to original
        if expansion_lower.strip() == original_lower.strip():
            logger.debug("Filtered expansion: identical to original")
            return False

        return True

    def _result_to_dict(self, result: QueryExpansionResult) -> dict:
        """Convert QueryExpansionResult to dict for caching.

        Args:
            result: The expansion result to serialize.

        Returns:
            Dictionary suitable for JSON serialization.
        """
        return {
            "lex_expansions": result.lex_expansions,
            "vec_expansions": result.vec_expansions,
            "hyde_passage": result.hyde_passage,
        }

    def _dict_to_result(self, query: str, data: dict) -> QueryExpansionResult:
        """Convert cached dict back to QueryExpansionResult.

        Args:
            query: The original search query.
            data: Cached dictionary data.

        Returns:
            Reconstructed QueryExpansionResult.
        """
        return QueryExpansionResult(
            original=query,
            lex_expansions=data.get("lex_expansions", []),
            vec_expansions=data.get("vec_expansions", []),
            hyde_passage=data.get("hyde_passage"),
        )
