"""Tests for catalog.search.query_expansion module."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import sessionmaker

from catalog.llm.prompts import QUERY_EXPANSION_PROMPT, QUERY_EXPANSION_SYSTEM
from catalog.search.query_expansion import QueryExpansionResult, QueryExpansionTransform
from catalog.store.database import Base, create_engine_for_path


class TestQueryExpansionResult:
    """Tests for the QueryExpansionResult dataclass."""

    def test_dataclass_fields(self) -> None:
        """QueryExpansionResult has expected fields."""
        result = QueryExpansionResult(
            original="python async",
            lex_expansions=["asyncio python", "python concurrent"],
            vec_expansions=["asynchronous programming in python"],
            hyde_passage="Python supports asynchronous programming...",
        )

        assert result.original == "python async"
        assert result.lex_expansions == ["asyncio python", "python concurrent"]
        assert result.vec_expansions == ["asynchronous programming in python"]
        assert result.hyde_passage == "Python supports asynchronous programming..."

    def test_default_values(self) -> None:
        """QueryExpansionResult has sensible defaults."""
        result = QueryExpansionResult(original="test query")

        assert result.original == "test query"
        assert result.lex_expansions == []
        assert result.vec_expansions == []
        assert result.hyde_passage is None

    def test_all_queries_property(self) -> None:
        """all_queries returns original plus all expansions."""
        result = QueryExpansionResult(
            original="test",
            lex_expansions=["lex1", "lex2"],
            vec_expansions=["vec1"],
        )

        queries = result.all_queries
        assert queries[0] == "test"  # Original first
        assert "lex1" in queries
        assert "lex2" in queries
        assert "vec1" in queries
        assert len(queries) == 4

    def test_all_queries_original_only(self) -> None:
        """all_queries works with no expansions."""
        result = QueryExpansionResult(original="test")

        assert result.all_queries == ["test"]

    def test_has_expansions_true(self) -> None:
        """has_expansions returns True when expansions exist."""
        result_lex = QueryExpansionResult(original="test", lex_expansions=["a"])
        result_vec = QueryExpansionResult(original="test", vec_expansions=["b"])
        result_hyde = QueryExpansionResult(original="test", hyde_passage="passage")

        assert result_lex.has_expansions is True
        assert result_vec.has_expansions is True
        assert result_hyde.has_expansions is True

    def test_has_expansions_false(self) -> None:
        """has_expansions returns False when no expansions."""
        result = QueryExpansionResult(original="test")

        assert result.has_expansions is False


class TestQueryExpansionPrompts:
    """Tests for query expansion prompt constants."""

    def test_system_prompt_exists(self) -> None:
        """System prompt is defined and non-empty."""
        assert QUERY_EXPANSION_SYSTEM
        assert isinstance(QUERY_EXPANSION_SYSTEM, str)
        assert "lex" in QUERY_EXPANSION_SYSTEM.lower()
        assert "vec" in QUERY_EXPANSION_SYSTEM.lower()

    def test_prompt_has_placeholders(self) -> None:
        """Query expansion prompt has required placeholders."""
        assert "{query}" in QUERY_EXPANSION_PROMPT
        assert "{max_lex}" in QUERY_EXPANSION_PROMPT
        assert "{max_vec}" in QUERY_EXPANSION_PROMPT
        assert "{include_hyde}" in QUERY_EXPANSION_PROMPT

    def test_prompt_formatting(self) -> None:
        """Prompt can be formatted with expected parameters."""
        formatted = QUERY_EXPANSION_PROMPT.format(
            query="test query",
            max_lex=3,
            max_vec=3,
            include_hyde="yes",
        )

        assert "test query" in formatted
        assert "3" in formatted


class TestQueryExpansionParsing:
    """Tests for parsing LLM response into expansions."""

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
    def transform(self, db_session) -> QueryExpansionTransform:
        """Create a transform instance."""
        return QueryExpansionTransform(db_session, model_name="test-model")

    def test_parse_lex_expansions(self, transform: QueryExpansionTransform) -> None:
        """Parses lex: tagged lines correctly."""
        response = """lex: python asyncio
lex: async python programming
lex: concurrent python"""

        result = transform._parse_response("python async", response)

        assert len(result.lex_expansions) == 3
        assert "python asyncio" in result.lex_expansions
        assert "async python programming" in result.lex_expansions

    def test_parse_vec_expansions(self, transform: QueryExpansionTransform) -> None:
        """Parses vec: tagged lines correctly."""
        response = """vec: asynchronous programming in python
vec: how to use python for concurrent execution"""

        result = transform._parse_response("python async", response)

        assert len(result.vec_expansions) == 2
        assert "asynchronous programming in python" in result.vec_expansions

    def test_parse_hyde_passage(self, transform: QueryExpansionTransform) -> None:
        """Parses hyde: block correctly."""
        response = """lex: python asyncio
hyde: Python's asyncio module provides a foundation for writing single-threaded concurrent code. It uses coroutines and an event loop to manage asynchronous operations."""

        result = transform._parse_response("python async", response)

        assert result.hyde_passage is not None
        assert "asyncio" in result.hyde_passage

    def test_parse_mixed_response(self, transform: QueryExpansionTransform) -> None:
        """Parses response with all expansion types."""
        response = """lex: python asyncio tutorial
lex: async await python
vec: how to write asynchronous code in python
vec: python concurrent programming guide
hyde: Asynchronous programming in Python allows for efficient I/O operations."""

        result = transform._parse_response("python async", response)

        assert len(result.lex_expansions) == 2
        assert len(result.vec_expansions) == 2
        assert result.hyde_passage is not None

    def test_parse_empty_response(self, transform: QueryExpansionTransform) -> None:
        """Handles empty response gracefully."""
        result = transform._parse_response("test query", "")

        assert result.lex_expansions == []
        assert result.vec_expansions == []
        assert result.hyde_passage is None

    def test_parse_case_insensitive_tags(self, transform: QueryExpansionTransform) -> None:
        """Parses tags regardless of case."""
        response = """LEX: python programming tutorial
Lex: test python basics
VEC: semantic python test
Vec: test python semantic"""

        result = transform._parse_response("python test", response)

        # Both lex expansions should pass quality filter (contain "python" or "test")
        assert len(result.lex_expansions) == 2
        assert len(result.vec_expansions) == 2


class TestQualityFiltering:
    """Tests for expansion quality filtering."""

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
    def transform(self, db_session) -> QueryExpansionTransform:
        """Create a transform instance."""
        return QueryExpansionTransform(db_session, model_name="test-model")

    def test_filters_no_overlap(self, transform: QueryExpansionTransform) -> None:
        """Filters expansions with no term overlap."""
        # "machine learning" has no overlap with "python async"
        assert transform._is_quality_expansion("python async", "machine learning") is False

    def test_accepts_partial_overlap(self, transform: QueryExpansionTransform) -> None:
        """Accepts expansions with at least one overlapping term."""
        assert transform._is_quality_expansion("python async", "python concurrent") is True
        assert transform._is_quality_expansion("python async", "async await syntax") is True

    def test_filters_identical_expansion(self, transform: QueryExpansionTransform) -> None:
        """Filters expansions identical to original."""
        assert transform._is_quality_expansion("python async", "python async") is False
        assert transform._is_quality_expansion("Python Async", "python async") is False

    def test_case_insensitive_overlap(self, transform: QueryExpansionTransform) -> None:
        """Overlap detection is case insensitive."""
        assert transform._is_quality_expansion("Python ASYNC", "python concurrent") is True
        assert transform._is_quality_expansion("python async", "ASYNC programming") is True

    def test_filtering_in_parse(self, transform: QueryExpansionTransform) -> None:
        """Parsing filters low-quality expansions."""
        response = """lex: python concurrent
lex: machine learning
lex: async programming python"""

        result = transform._parse_response("python async", response)

        # "machine learning" should be filtered out
        assert "machine learning" not in result.lex_expansions
        assert "python concurrent" in result.lex_expansions
        assert "async programming python" in result.lex_expansions


class TestFallbackBehavior:
    """Tests for graceful fallback on LLM failure."""

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

    @pytest.mark.asyncio
    async def test_fallback_on_llm_error(self, db_session) -> None:
        """Returns original query only on LLM failure."""
        transform = QueryExpansionTransform(db_session, model_name="test-model")

        # Mock the provider to raise an error
        with patch("catalog.llm.provider.MLXProvider") as mock_provider_cls:
            mock_provider = MagicMock()
            mock_provider.generate = AsyncMock(side_effect=Exception("LLM unavailable"))
            mock_provider_cls.return_value = mock_provider

            result = await transform.expand("test query")

        assert result.original == "test query"
        assert result.lex_expansions == []
        assert result.vec_expansions == []
        assert result.hyde_passage is None

    @pytest.mark.asyncio
    async def test_disabled_expansion_returns_original(self, db_session, monkeypatch) -> None:
        """Returns original only when expansion is disabled."""
        from catalog.core.settings import RAGSettings

        mock_rag = RAGSettings(expansion_enabled=False)
        monkeypatch.setattr(
            QueryExpansionTransform, "_settings", property(lambda self: mock_rag)
        )

        transform = QueryExpansionTransform(db_session, model_name="test-model")
        result = await transform.expand("test query")

        assert result.original == "test query"
        assert result.has_expansions is False


class TestCacheIntegration:
    """Tests for cache integration."""

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

    @pytest.mark.asyncio
    async def test_caches_expansion_result(self, db_session) -> None:
        """Expansion results are cached after generation."""
        transform = QueryExpansionTransform(db_session, model_name="test-model")

        with patch("catalog.llm.provider.MLXProvider") as mock_provider_cls:
            mock_provider = MagicMock()
            mock_provider.generate = AsyncMock(
                return_value="lex: python programming test\nvec: semantic python test"
            )
            mock_provider_cls.return_value = mock_provider

            # First call generates and caches
            result1 = await transform.expand("python test")
            db_session.flush()

            # Verify cache was populated
            cached = transform._cache.get_expansion("python test", "test-model")
            assert cached is not None
            assert "lex_expansions" in cached

    @pytest.mark.asyncio
    async def test_uses_cached_result(self, db_session) -> None:
        """Uses cached result on subsequent calls."""
        transform = QueryExpansionTransform(db_session, model_name="test-model")

        # Pre-populate cache
        transform._cache.set_expansion(
            "python test",
            "test-model",
            {
                "lex_expansions": ["cached lex python"],
                "vec_expansions": ["cached vec test"],
                "hyde_passage": None,
            },
        )
        db_session.flush()

        # Should use cache, not call LLM
        with patch("catalog.llm.provider.MLXProvider") as mock_provider_cls:
            result = await transform.expand("python test")

            # Provider should not be instantiated
            mock_provider_cls.assert_not_called()

        assert "cached lex python" in result.lex_expansions
        assert "cached vec test" in result.vec_expansions


class TestSettingsIntegration:
    """Tests for settings integration."""

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

    def test_respects_max_lex_setting(self, db_session, monkeypatch) -> None:
        """Limits lex expansions to configured maximum."""
        from catalog.core.settings import RAGSettings, Settings, get_settings
        import catalog.search.query_expansion as query_expansion_module

        # Clear the lru_cache to allow new mock to take effect
        get_settings.cache_clear()

        mock_settings = Settings(rag=RAGSettings(expansion_max_lex=2))
        monkeypatch.setattr(query_expansion_module, "get_settings", lambda: mock_settings)

        transform = QueryExpansionTransform(db_session, model_name="test-model")

        response = """lex: python one
lex: python two
lex: python three
lex: python four"""

        result = transform._parse_response("python", response)

        assert len(result.lex_expansions) == 2

        # Restore cache
        get_settings.cache_clear()

    def test_respects_max_vec_setting(self, db_session, monkeypatch) -> None:
        """Limits vec expansions to configured maximum."""
        from catalog.core.settings import RAGSettings, Settings, get_settings
        import catalog.search.query_expansion as query_expansion_module

        # Clear the lru_cache to allow new mock to take effect
        get_settings.cache_clear()

        mock_settings = Settings(rag=RAGSettings(expansion_max_vec=1))
        monkeypatch.setattr(query_expansion_module, "get_settings", lambda: mock_settings)

        transform = QueryExpansionTransform(db_session, model_name="test-model")

        response = """vec: semantic python one
vec: semantic python two"""

        result = transform._parse_response("python", response)

        assert len(result.vec_expansions) == 1

        # Restore cache
        get_settings.cache_clear()

    def test_hyde_disabled_by_setting(self, db_session, monkeypatch) -> None:
        """HyDE is excluded when disabled in settings."""
        from catalog.core.settings import RAGSettings, Settings, get_settings
        import catalog.search.query_expansion as query_expansion_module

        # Clear the lru_cache to allow new mock to take effect
        get_settings.cache_clear()

        mock_settings = Settings(rag=RAGSettings(expansion_include_hyde=False))
        monkeypatch.setattr(query_expansion_module, "get_settings", lambda: mock_settings)

        transform = QueryExpansionTransform(db_session, model_name="test-model")

        response = """lex: python test
hyde: This is a hypothetical document about python."""

        result = transform._parse_response("python", response)

        assert result.hyde_passage is None

        # Restore cache
        get_settings.cache_clear()


class TestResultSerialization:
    """Tests for result serialization to/from dict."""

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

    def test_result_to_dict(self, db_session) -> None:
        """Result serializes to dict correctly."""
        transform = QueryExpansionTransform(db_session)
        result = QueryExpansionResult(
            original="test",
            lex_expansions=["lex1", "lex2"],
            vec_expansions=["vec1"],
            hyde_passage="hyde text",
        )

        data = transform._result_to_dict(result)

        assert data["lex_expansions"] == ["lex1", "lex2"]
        assert data["vec_expansions"] == ["vec1"]
        assert data["hyde_passage"] == "hyde text"
        assert "original" not in data  # Original is not cached

    def test_dict_to_result(self, db_session) -> None:
        """Dict deserializes to result correctly."""
        transform = QueryExpansionTransform(db_session)
        data = {
            "lex_expansions": ["lex1"],
            "vec_expansions": ["vec1", "vec2"],
            "hyde_passage": "hyde",
        }

        result = transform._dict_to_result("original query", data)

        assert result.original == "original query"
        assert result.lex_expansions == ["lex1"]
        assert result.vec_expansions == ["vec1", "vec2"]
        assert result.hyde_passage == "hyde"

    def test_roundtrip_serialization(self, db_session) -> None:
        """Result survives roundtrip through dict."""
        transform = QueryExpansionTransform(db_session)
        original = QueryExpansionResult(
            original="test query",
            lex_expansions=["a", "b"],
            vec_expansions=["c"],
            hyde_passage="passage",
        )

        data = transform._result_to_dict(original)
        restored = transform._dict_to_result("test query", data)

        assert restored.original == original.original
        assert restored.lex_expansions == original.lex_expansions
        assert restored.vec_expansions == original.vec_expansions
        assert restored.hyde_passage == original.hyde_passage
