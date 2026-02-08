"""Tests for catalog.store.llm_cache module."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from catalog.store.database import Base, create_engine_for_path
from catalog.store.llm_cache import LLMCache, LLMCacheEntry


class TestLLMCacheEntry:
    """Tests for the LLMCacheEntry SQLAlchemy model."""

    def test_model_creates_table(self, tmp_path: Path) -> None:
        """LLMCacheEntry model creates llm_cache_v2 table."""
        db_path = tmp_path / "test.db"
        engine = create_engine_for_path(db_path)
        Base.metadata.create_all(engine)

        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='llm_cache_v2'"
                )
            )
            assert result.scalar() == "llm_cache_v2"

    def test_model_repr(self, tmp_path: Path) -> None:
        """LLMCacheEntry has informative repr."""
        entry = LLMCacheEntry(
            cache_key="a" * 64,
            cache_type="expansion",
            result_json='{"test": true}',
            created_at=datetime.utcnow(),
        )
        repr_str = repr(entry)
        assert "LLMCacheEntry" in repr_str
        assert "expansion" in repr_str


class TestLLMCacheKeyGeneration:
    """Tests for cache key generation."""

    @pytest.fixture
    def db_session(self, tmp_path: Path):
        """Create a test database session."""
        db_path = tmp_path / "test.db"
        engine = create_engine_for_path(db_path)
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        session = factory()
        yield session
        session.close()

    @pytest.fixture
    def cache(self, db_session) -> LLMCache:
        """Create an LLM cache with 1 week TTL."""
        return LLMCache(db_session, ttl_hours=168)

    def test_key_is_sha256_hex(self, cache: LLMCache) -> None:
        """Cache key is a 64-character hex string (SHA-256)."""
        key = cache._make_key("expansion", "test query", "gpt-4")
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)

    def test_key_is_deterministic(self, cache: LLMCache) -> None:
        """Same inputs produce the same cache key."""
        key1 = cache._make_key("expansion", "test query", "gpt-4")
        key2 = cache._make_key("expansion", "test query", "gpt-4")
        assert key1 == key2

    def test_different_types_produce_different_keys(self, cache: LLMCache) -> None:
        """Different cache types produce different keys."""
        expansion_key = cache._make_key("expansion", "query", "model")
        rerank_key = cache._make_key("rerank", "query", "model")
        assert expansion_key != rerank_key

    def test_different_queries_produce_different_keys(self, cache: LLMCache) -> None:
        """Different queries produce different keys."""
        key1 = cache._make_key("expansion", "query one", "gpt-4")
        key2 = cache._make_key("expansion", "query two", "gpt-4")
        assert key1 != key2

    def test_different_models_produce_different_keys(self, cache: LLMCache) -> None:
        """Different models produce different keys."""
        key1 = cache._make_key("expansion", "query", "gpt-4")
        key2 = cache._make_key("expansion", "query", "gpt-3.5-turbo")
        assert key1 != key2

    def test_key_collision_resistance(self, cache: LLMCache) -> None:
        """Keys with different number of parts are different."""
        # Test that different argument counts produce different keys
        key1 = cache._make_key("expansion", "query", "model", "extra")
        key2 = cache._make_key("expansion", "query", "model")
        assert key1 != key2

        # Test that empty strings in parts still differentiate keys
        key3 = cache._make_key("expansion", "query", "", "model")
        key4 = cache._make_key("expansion", "query", "model")
        assert key3 != key4


class TestLLMCacheExpansion:
    """Tests for expansion caching operations."""

    @pytest.fixture
    def db_session(self, tmp_path: Path):
        """Create a test database session."""
        db_path = tmp_path / "test.db"
        engine = create_engine_for_path(db_path)
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        session = factory()
        yield session
        session.close()

    @pytest.fixture
    def cache(self, db_session) -> LLMCache:
        """Create an LLM cache with 24 hour TTL."""
        return LLMCache(db_session, ttl_hours=24)

    def test_get_expansion_miss(self, cache: LLMCache) -> None:
        """get_expansion returns None for missing entry."""
        result = cache.get_expansion("nonexistent query", "gpt-4")
        assert result is None

    def test_set_and_get_expansion(self, cache: LLMCache, db_session) -> None:
        """set_expansion stores and get_expansion retrieves."""
        expansion_result = {
            "lexical_terms": ["python", "programming"],
            "semantic_queries": ["python tutorials", "learn python"],
            "hyde": "Python is a programming language...",
        }

        cache.set_expansion("python tutorial", "gpt-4", expansion_result)
        db_session.flush()

        retrieved = cache.get_expansion("python tutorial", "gpt-4")
        assert retrieved == expansion_result

    def test_set_expansion_updates_existing(self, cache: LLMCache, db_session) -> None:
        """set_expansion updates an existing entry."""
        cache.set_expansion("query", "gpt-4", {"version": 1})
        db_session.flush()

        cache.set_expansion("query", "gpt-4", {"version": 2})
        db_session.flush()

        result = cache.get_expansion("query", "gpt-4")
        assert result == {"version": 2}

    def test_expansion_different_models_isolated(
        self, cache: LLMCache, db_session
    ) -> None:
        """Different models have isolated cache entries."""
        cache.set_expansion("query", "gpt-4", {"model": "gpt-4"})
        cache.set_expansion("query", "gpt-3.5-turbo", {"model": "gpt-3.5-turbo"})
        db_session.flush()

        assert cache.get_expansion("query", "gpt-4") == {"model": "gpt-4"}
        assert cache.get_expansion("query", "gpt-3.5-turbo") == {
            "model": "gpt-3.5-turbo"
        }


class TestLLMCacheRerank:
    """Tests for rerank caching operations."""

    @pytest.fixture
    def db_session(self, tmp_path: Path):
        """Create a test database session."""
        db_path = tmp_path / "test.db"
        engine = create_engine_for_path(db_path)
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        session = factory()
        yield session
        session.close()

    @pytest.fixture
    def cache(self, db_session) -> LLMCache:
        """Create an LLM cache with 24 hour TTL."""
        return LLMCache(db_session, ttl_hours=24)

    def test_get_rerank_miss(self, cache: LLMCache) -> None:
        """get_rerank returns None for missing entry."""
        result = cache.get_rerank("query", "doc123", "cross-encoder")
        assert result is None

    def test_set_and_get_rerank(self, cache: LLMCache, db_session) -> None:
        """set_rerank stores and get_rerank retrieves."""
        cache.set_rerank("python tutorial", "doc_abc123", "cross-encoder", 0.95)
        db_session.flush()

        score = cache.get_rerank("python tutorial", "doc_abc123", "cross-encoder")
        assert score == 0.95

    def test_set_rerank_updates_existing(self, cache: LLMCache, db_session) -> None:
        """set_rerank updates an existing entry."""
        cache.set_rerank("query", "doc1", "model", 0.5)
        db_session.flush()

        cache.set_rerank("query", "doc1", "model", 0.9)
        db_session.flush()

        score = cache.get_rerank("query", "doc1", "model")
        assert score == 0.9

    def test_rerank_different_docs_isolated(self, cache: LLMCache, db_session) -> None:
        """Different documents have isolated cache entries."""
        cache.set_rerank("query", "doc1", "model", 0.8)
        cache.set_rerank("query", "doc2", "model", 0.6)
        db_session.flush()

        assert cache.get_rerank("query", "doc1", "model") == 0.8
        assert cache.get_rerank("query", "doc2", "model") == 0.6

    def test_rerank_preserves_precision(self, cache: LLMCache, db_session) -> None:
        """Rerank scores preserve floating point precision."""
        precise_score = 0.123456789
        cache.set_rerank("query", "doc", "model", precise_score)
        db_session.flush()

        retrieved = cache.get_rerank("query", "doc", "model")
        assert retrieved == pytest.approx(precise_score)


class TestLLMCacheTTL:
    """Tests for TTL-based expiration."""

    @pytest.fixture
    def db_session(self, tmp_path: Path):
        """Create a test database session."""
        db_path = tmp_path / "test.db"
        engine = create_engine_for_path(db_path)
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        session = factory()
        yield session
        session.close()

    def test_fresh_entry_not_expired(self, db_session) -> None:
        """Recently created entry is not expired."""
        cache = LLMCache(db_session, ttl_hours=24)
        cache.set_expansion("query", "model", {"fresh": True})
        db_session.flush()

        result = cache.get_expansion("query", "model")
        assert result == {"fresh": True}

    def test_expired_entry_returns_none(self, db_session) -> None:
        """Expired entry returns None."""
        cache = LLMCache(db_session, ttl_hours=1)

        # Manually create an expired entry
        cache_key = cache._make_key("expansion", "query", "model")
        old_time = datetime.utcnow() - timedelta(hours=2)
        entry = LLMCacheEntry(
            cache_key=cache_key,
            cache_type="expansion",
            result_json='{"expired": true}',
            created_at=old_time,
        )
        db_session.add(entry)
        db_session.flush()

        result = cache.get_expansion("query", "model")
        assert result is None

    def test_expired_entry_is_deleted(self, db_session) -> None:
        """Accessing an expired entry deletes it from the database."""
        cache = LLMCache(db_session, ttl_hours=1)

        # Manually create an expired entry
        cache_key = cache._make_key("expansion", "query", "model")
        old_time = datetime.utcnow() - timedelta(hours=2)
        entry = LLMCacheEntry(
            cache_key=cache_key,
            cache_type="expansion",
            result_json='{"expired": true}',
            created_at=old_time,
        )
        db_session.add(entry)
        db_session.flush()

        # Access it (should return None and delete)
        cache.get_expansion("query", "model")
        db_session.flush()

        # Verify it's deleted
        from sqlalchemy import select

        stmt = select(LLMCacheEntry).where(LLMCacheEntry.cache_key == cache_key)
        remaining = db_session.execute(stmt).scalar_one_or_none()
        assert remaining is None

    def test_update_refreshes_ttl(self, db_session) -> None:
        """Updating an entry refreshes its created_at timestamp."""
        cache = LLMCache(db_session, ttl_hours=24)

        # Create initial entry
        cache.set_expansion("query", "model", {"version": 1})
        db_session.flush()

        # Get initial timestamp
        cache_key = cache._make_key("expansion", "query", "model")
        from sqlalchemy import select

        stmt = select(LLMCacheEntry).where(LLMCacheEntry.cache_key == cache_key)
        initial_entry = db_session.execute(stmt).scalar_one()
        initial_time = initial_entry.created_at

        # Wait a tiny bit and update
        import time

        time.sleep(0.01)
        cache.set_expansion("query", "model", {"version": 2})
        db_session.flush()

        # Verify timestamp was updated
        db_session.expire(initial_entry)
        updated_entry = db_session.execute(stmt).scalar_one()
        assert updated_entry.created_at >= initial_time

    def test_ttl_defaults_to_settings(self, db_session, monkeypatch) -> None:
        """TTL defaults to settings value when not provided."""
        # Mock get_settings to return a known TTL
        from catalog.core.settings import RAGSettings, Settings
        import catalog.core.settings as settings_module

        mock_settings = Settings(rag=RAGSettings(cache_ttl_hours=72))

        monkeypatch.setattr(settings_module, "get_settings", lambda: mock_settings)

        cache = LLMCache(db_session)
        assert cache._ttl_hours == 72


class TestLLMCacheIntegration:
    """Integration tests for LLMCache with database session."""

    @pytest.fixture
    def db_session(self, tmp_path: Path):
        """Create a test database session."""
        db_path = tmp_path / "test.db"
        engine = create_engine_for_path(db_path)
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        session = factory()
        yield session
        session.close()

    def test_multiple_cache_types_coexist(self, db_session) -> None:
        """Expansion and rerank caches work together."""
        cache = LLMCache(db_session, ttl_hours=24)

        cache.set_expansion("query", "model", {"terms": ["a", "b"]})
        cache.set_rerank("query", "doc1", "model", 0.9)
        db_session.flush()

        assert cache.get_expansion("query", "model") == {"terms": ["a", "b"]}
        assert cache.get_rerank("query", "doc1", "model") == 0.9

    def test_cache_survives_session_close(self, tmp_path: Path) -> None:
        """Cached data persists across sessions."""
        db_path = tmp_path / "persist.db"
        engine = create_engine_for_path(db_path)
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False)

        # First session: write data
        session1 = factory()
        cache1 = LLMCache(session1, ttl_hours=24)
        cache1.set_expansion("query", "model", {"persisted": True})
        session1.commit()
        session1.close()

        # Second session: read data
        session2 = factory()
        cache2 = LLMCache(session2, ttl_hours=24)
        result = cache2.get_expansion("query", "model")
        session2.close()

        assert result == {"persisted": True}

    def test_complex_json_roundtrip(self, db_session) -> None:
        """Complex JSON structures are preserved."""
        cache = LLMCache(db_session, ttl_hours=24)

        complex_data = {
            "lexical_terms": ["python", "machine learning", "neural networks"],
            "semantic_queries": [
                "how to learn python programming",
                "python data science tutorial",
            ],
            "hyde": "Python is a versatile programming language...",
            "metadata": {
                "model": "gpt-4",
                "timestamp": "2024-01-01T00:00:00Z",
                "confidence": 0.95,
            },
            "nested": {"deeply": {"nested": {"value": 42}}},
        }

        cache.set_expansion("query", "model", complex_data)
        db_session.flush()

        result = cache.get_expansion("query", "model")
        assert result == complex_data
