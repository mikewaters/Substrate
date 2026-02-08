"""catalog.store.llm_cache - LLM result caching for RAG search.

Provides persistent caching of LLM results for query expansion and reranking
to reduce redundant API calls and improve response times.

The cache uses a SQLite table with TTL-based expiration. Cache keys are
SHA-256 hashes of the cache type and input parameters.
"""

import hashlib
import json
from datetime import datetime, timedelta

from sqlalchemy import DateTime, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from agentlayer.logging import get_logger
from catalog.store.models.catalog import CatalogBase

logger = get_logger(__name__)

__all__ = [
    "LLMCache",
    "LLMCacheEntry",
]


class LLMCacheEntry(CatalogBase):
    """SQLAlchemy model for LLM cache entries.

    Stores cached LLM results with TTL-based expiration support.
    The cache_key is a SHA-256 hash ensuring uniqueness and collision resistance.

    Attributes:
        cache_key: SHA-256 hash primary key (64 hex characters).
        cache_type: Type of cached result (e.g., "expansion", "rerank").
        result_json: JSON-serialized result data.
        created_at: Timestamp when the entry was created.
    """

    __tablename__ = "llm_cache_v2"

    cache_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    cache_type: Mapped[str] = mapped_column(Text, nullable=False)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<LLMCacheEntry(cache_key='{self.cache_key[:16]}...', "
            f"cache_type='{self.cache_type}')>"
        )


class LLMCache:
    """LLM result cache with TTL-based expiration.

    Caches query expansion and rerank results to reduce redundant LLM calls.
    Uses SHA-256 hashing for cache keys to ensure collision resistance.

    Args:
        session: SQLAlchemy session for database operations.
        ttl_hours: Cache entry time-to-live in hours. Defaults to settings value.

    Example:
        with get_session() as session:
            cache = LLMCache(session)

            # Cache expansion result
            cache.set_expansion("search query", "gpt-4", {"terms": ["a", "b"]})

            # Retrieve cached expansion
            result = cache.get_expansion("search query", "gpt-4")
    """

    def __init__(self, session: Session, ttl_hours: int | None = None) -> None:
        """Initialize the LLM cache.

        Args:
            session: SQLAlchemy session for database operations.
            ttl_hours: Cache TTL in hours. If None, uses settings default.
        """
        self._session = session
        if ttl_hours is None:
            from catalog.core.settings import get_settings

            ttl_hours = get_settings().rag.cache_ttl_hours
        self._ttl_hours = ttl_hours

    def _make_key(self, cache_type: str, *parts: str) -> str:
        """Generate a SHA-256 cache key from type and parts.

        Constructs a key string in the format "{cache_type}:{part1}:{part2}:..."
        and returns its SHA-256 hash as a hex string.

        Args:
            cache_type: The type of cached item (e.g., "expansion", "rerank").
            *parts: Variable parts to include in the key (query, model, etc.).

        Returns:
            64-character hex string SHA-256 hash.
        """
        key_string = ":".join([cache_type] + list(parts))
        return hashlib.sha256(key_string.encode("utf-8")).hexdigest()

    def _is_expired(self, entry: LLMCacheEntry) -> bool:
        """Check if a cache entry has expired.

        Args:
            entry: The cache entry to check.

        Returns:
            True if the entry is older than the TTL, False otherwise.
        """
        expiry_time = entry.created_at + timedelta(hours=self._ttl_hours)
        return datetime.utcnow() > expiry_time

    def _get_entry(self, cache_key: str) -> LLMCacheEntry | None:
        """Retrieve a cache entry by key, returning None if expired.

        Args:
            cache_key: The SHA-256 hash key.

        Returns:
            The cache entry if found and not expired, None otherwise.
        """
        stmt = select(LLMCacheEntry).where(LLMCacheEntry.cache_key == cache_key)
        entry = self._session.execute(stmt).scalar_one_or_none()

        if entry is None:
            return None

        if self._is_expired(entry):
            logger.debug("Cache entry expired", cache_key=cache_key[:16])
            self._session.delete(entry)
            return None

        return entry

    def _set_entry(
        self, cache_key: str, cache_type: str, result_json: str
    ) -> LLMCacheEntry:
        """Create or update a cache entry.

        Args:
            cache_key: The SHA-256 hash key.
            cache_type: The type of cached item.
            result_json: JSON-serialized result data.

        Returns:
            The created or updated cache entry.
        """
        stmt = select(LLMCacheEntry).where(LLMCacheEntry.cache_key == cache_key)
        entry = self._session.execute(stmt).scalar_one_or_none()

        if entry is not None:
            entry.result_json = result_json
            entry.created_at = datetime.utcnow()
            logger.debug("Updated cache entry", cache_key=cache_key[:16])
        else:
            entry = LLMCacheEntry(
                cache_key=cache_key,
                cache_type=cache_type,
                result_json=result_json,
                created_at=datetime.utcnow(),
            )
            self._session.add(entry)
            logger.debug("Created cache entry", cache_key=cache_key[:16])

        return entry

    def get_expansion(self, query: str, model: str) -> dict | None:
        """Retrieve a cached query expansion result.

        Args:
            query: The original search query.
            model: The LLM model identifier.

        Returns:
            The cached expansion result dict, or None if not found/expired.
        """
        cache_key = self._make_key("expansion", query, model)
        entry = self._get_entry(cache_key)

        if entry is None:
            logger.debug("Expansion cache miss", query=query[:50], model=model)
            return None

        logger.debug("Expansion cache hit", query=query[:50], model=model)
        return json.loads(entry.result_json)

    def set_expansion(self, query: str, model: str, result: dict) -> None:
        """Cache a query expansion result.

        Args:
            query: The original search query.
            model: The LLM model identifier.
            result: The expansion result to cache.
        """
        cache_key = self._make_key("expansion", query, model)
        result_json = json.dumps(result)
        self._set_entry(cache_key, "expansion", result_json)
        logger.debug("Cached expansion result", query=query[:50], model=model)

    def get_rerank(self, query: str, doc_hash: str, model: str) -> float | None:
        """Retrieve a cached rerank score.

        Args:
            query: The search query.
            doc_hash: Hash identifying the document/chunk.
            model: The reranker model identifier.

        Returns:
            The cached rerank score, or None if not found/expired.
        """
        cache_key = self._make_key("rerank", query, doc_hash, model)
        entry = self._get_entry(cache_key)

        if entry is None:
            logger.debug("Rerank cache miss", doc_hash=doc_hash[:16])
            return None

        logger.debug("Rerank cache hit", doc_hash=doc_hash[:16])
        return float(entry.result_json)

    def set_rerank(self, query: str, doc_hash: str, model: str, score: float) -> None:
        """Cache a rerank score.

        Args:
            query: The search query.
            doc_hash: Hash identifying the document/chunk.
            model: The reranker model identifier.
            score: The rerank score to cache.
        """
        cache_key = self._make_key("rerank", query, doc_hash, model)
        self._set_entry(cache_key, "rerank", str(score))
        logger.debug("Cached rerank score", doc_hash=doc_hash[:16], score=score)
