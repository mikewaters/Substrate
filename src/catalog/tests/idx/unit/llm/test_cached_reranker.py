"""Tests for CachedReranker in catalog.llm.reranker module."""

from unittest.mock import MagicMock, patch

import pytest

from catalog.llm.reranker import CachedReranker


def make_mock_node(
    node_id: str,
    text: str = "sample text",
    score: float = 0.5,
    content_hash: str | None = None,
    metadata: dict | None = None,
) -> MagicMock:
    """Create a mock NodeWithScore for testing.

    Args:
        node_id: The node ID.
        text: The node text content.
        score: The node score.
        content_hash: Optional content hash for metadata.
        metadata: Additional metadata to include.

    Returns:
        Mock NodeWithScore object.
    """
    node = MagicMock()
    node.node_id = node_id
    node.text = text

    node_metadata = metadata or {}
    if content_hash:
        node_metadata["content_hash"] = content_hash
    node.metadata = node_metadata

    mock_nws = MagicMock()
    mock_nws.node = node
    mock_nws.score = score

    # Mock model_copy to return a new mock with updated score
    def model_copy_impl(update: dict | None = None) -> MagicMock:
        new_mock = make_mock_node(
            node_id=node_id,
            text=text,
            score=update.get("score", score) if update else score,
            content_hash=content_hash,
            metadata=metadata,
        )
        return new_mock

    mock_nws.model_copy = model_copy_impl

    return mock_nws


class TestCachedRerankerInit:
    """Tests for CachedReranker initialization."""

    def test_stores_reranker(self) -> None:
        """Stores the reranker instance."""
        mock_reranker = MagicMock()
        mock_cache = MagicMock()

        cached = CachedReranker(mock_reranker, mock_cache)

        assert cached.reranker is mock_reranker

    def test_stores_cache(self) -> None:
        """Stores the cache instance."""
        mock_reranker = MagicMock()
        mock_cache = MagicMock()

        cached = CachedReranker(mock_reranker, mock_cache)

        assert cached.cache is mock_cache

    def test_default_model_name(self) -> None:
        """Uses default model name when not specified."""
        mock_reranker = MagicMock()
        mock_cache = MagicMock()

        cached = CachedReranker(mock_reranker, mock_cache)

        assert cached.model_name == "default"

    def test_custom_model_name(self) -> None:
        """Uses custom model name when specified."""
        mock_reranker = MagicMock()
        mock_cache = MagicMock()

        cached = CachedReranker(mock_reranker, mock_cache, model_name="gpt-4o-mini")

        assert cached.model_name == "gpt-4o-mini"


class TestCachedRerankerGetNodeHash:
    """Tests for _get_node_hash method."""

    def test_uses_content_hash_from_metadata(self) -> None:
        """Uses content_hash from node metadata when available."""
        mock_reranker = MagicMock()
        mock_cache = MagicMock()
        cached = CachedReranker(mock_reranker, mock_cache)

        node = make_mock_node(
            node_id="node-123",
            content_hash="abc123hash",
        )

        result = cached._get_node_hash(node)

        assert result == "abc123hash"

    def test_falls_back_to_node_id(self) -> None:
        """Falls back to node_id when content_hash not in metadata."""
        mock_reranker = MagicMock()
        mock_cache = MagicMock()
        cached = CachedReranker(mock_reranker, mock_cache)

        node = make_mock_node(node_id="node-456")

        result = cached._get_node_hash(node)

        assert result == "node-456"

    def test_falls_back_to_object_id_when_no_node_id(self) -> None:
        """Falls back to object id when node_id is None."""
        mock_reranker = MagicMock()
        mock_cache = MagicMock()
        cached = CachedReranker(mock_reranker, mock_cache)

        node = make_mock_node(node_id="")  # Empty string is falsy
        node.node.node_id = None

        result = cached._get_node_hash(node)

        # Should be a string representation of the object id
        assert isinstance(result, str)
        assert result.isdigit()


class TestCachedRerankerCacheLookup:
    """Tests for cache lookup behavior."""

    def test_cache_hit_uses_cached_score(self) -> None:
        """Uses cached score when cache hit occurs."""
        mock_reranker = MagicMock()
        mock_cache = MagicMock()
        mock_cache.get_rerank.return_value = 0.85  # Cache hit

        cached = CachedReranker(mock_reranker, mock_cache, model_name="test-model")

        node = make_mock_node(node_id="node-1", content_hash="hash1", score=0.5)

        result = cached.rerank("test query", [node], top_n=10)

        # Should not call underlying reranker (all cached)
        mock_reranker.rerank.assert_not_called()

        # Should have looked up in cache
        mock_cache.get_rerank.assert_called_once_with("test query", "hash1", "test-model")

        # Result should have cached score
        assert len(result) == 1
        assert result[0].score == 0.85

    def test_cache_miss_calls_reranker(self) -> None:
        """Calls underlying reranker when cache miss occurs."""
        mock_reranker = MagicMock()
        mock_cache = MagicMock()
        mock_cache.get_rerank.return_value = None  # Cache miss

        reranked_node = make_mock_node(node_id="node-1", content_hash="hash1", score=0.9)
        mock_reranker.rerank.return_value = [reranked_node]

        cached = CachedReranker(mock_reranker, mock_cache)

        node = make_mock_node(node_id="node-1", content_hash="hash1", score=0.5)

        result = cached.rerank("test query", [node], top_n=10)

        # Should call underlying reranker
        mock_reranker.rerank.assert_called_once()
        call_kwargs = mock_reranker.rerank.call_args[1]
        assert call_kwargs["query"] == "test query"
        assert call_kwargs["top_n"] is None  # Get all scores

    def test_cache_miss_stores_new_score(self) -> None:
        """Stores new score in cache after reranking."""
        mock_reranker = MagicMock()
        mock_cache = MagicMock()
        mock_cache.get_rerank.return_value = None  # Cache miss

        reranked_node = make_mock_node(node_id="node-1", content_hash="hash1", score=0.9)
        mock_reranker.rerank.return_value = [reranked_node]

        cached = CachedReranker(mock_reranker, mock_cache, model_name="test-model")

        node = make_mock_node(node_id="node-1", content_hash="hash1", score=0.5)

        cached.rerank("test query", [node], top_n=10)

        # Should store new score in cache
        mock_cache.set_rerank.assert_called_once_with(
            "test query", "hash1", "test-model", 0.9
        )


class TestCachedRerankerPartialCacheHits:
    """Tests for partial cache hit handling."""

    def test_partial_cache_hit_reranks_only_uncached(self) -> None:
        """Only reranks uncached nodes when partial cache hit."""
        mock_reranker = MagicMock()
        mock_cache = MagicMock()

        # node-1 is cached, node-2 is not
        def get_rerank_side_effect(query: str, doc_hash: str, model: str) -> float | None:
            if doc_hash == "hash1":
                return 0.8  # Cached
            return None  # Not cached

        mock_cache.get_rerank.side_effect = get_rerank_side_effect

        # Reranker returns score for node-2
        reranked_node2 = make_mock_node(node_id="node-2", content_hash="hash2", score=0.7)
        mock_reranker.rerank.return_value = [reranked_node2]

        cached = CachedReranker(mock_reranker, mock_cache)

        node1 = make_mock_node(node_id="node-1", content_hash="hash1", score=0.5)
        node2 = make_mock_node(node_id="node-2", content_hash="hash2", score=0.5)

        result = cached.rerank("test query", [node1, node2], top_n=10)

        # Should only rerank node2 (uncached)
        call_kwargs = mock_reranker.rerank.call_args[1]
        assert len(call_kwargs["nodes"]) == 1
        assert call_kwargs["nodes"][0].node.node_id == "node-2"

    def test_partial_cache_hit_merges_results(self) -> None:
        """Merges cached and reranked results correctly."""
        mock_reranker = MagicMock()
        mock_cache = MagicMock()

        def get_rerank_side_effect(query: str, doc_hash: str, model: str) -> float | None:
            if doc_hash == "hash1":
                return 0.6  # Cached score
            return None

        mock_cache.get_rerank.side_effect = get_rerank_side_effect

        # Reranker returns higher score for node-2
        reranked_node2 = make_mock_node(node_id="node-2", content_hash="hash2", score=0.9)
        mock_reranker.rerank.return_value = [reranked_node2]

        cached = CachedReranker(mock_reranker, mock_cache)

        node1 = make_mock_node(node_id="node-1", content_hash="hash1", score=0.5)
        node2 = make_mock_node(node_id="node-2", content_hash="hash2", score=0.5)

        result = cached.rerank("test query", [node1, node2], top_n=10)

        # Results should be sorted by score
        assert len(result) == 2
        # node-2 (0.9) should be first, node-1 (0.6) should be second
        assert result[0].score == 0.9
        assert result[1].score == 0.6


class TestCachedRerankerScoreOrdering:
    """Tests for score ordering behavior."""

    def test_results_sorted_by_score_descending(self) -> None:
        """Results are sorted by score in descending order."""
        mock_reranker = MagicMock()
        mock_cache = MagicMock()
        mock_cache.get_rerank.return_value = None  # All cache misses

        # Reranker returns nodes in non-sorted order
        nodes_reranked = [
            make_mock_node(node_id="node-1", content_hash="hash1", score=0.3),
            make_mock_node(node_id="node-2", content_hash="hash2", score=0.9),
            make_mock_node(node_id="node-3", content_hash="hash3", score=0.6),
        ]
        mock_reranker.rerank.return_value = nodes_reranked

        cached = CachedReranker(mock_reranker, mock_cache)

        input_nodes = [
            make_mock_node(node_id="node-1", content_hash="hash1"),
            make_mock_node(node_id="node-2", content_hash="hash2"),
            make_mock_node(node_id="node-3", content_hash="hash3"),
        ]

        result = cached.rerank("test query", input_nodes, top_n=10)

        # Should be sorted: 0.9, 0.6, 0.3
        assert result[0].score == 0.9
        assert result[1].score == 0.6
        assert result[2].score == 0.3

    def test_respects_top_n_limit(self) -> None:
        """Limits results to top_n after sorting."""
        mock_reranker = MagicMock()
        mock_cache = MagicMock()
        mock_cache.get_rerank.return_value = None

        nodes_reranked = [
            make_mock_node(node_id=f"node-{i}", content_hash=f"hash{i}", score=0.1 * i)
            for i in range(1, 6)
        ]
        mock_reranker.rerank.return_value = nodes_reranked

        cached = CachedReranker(mock_reranker, mock_cache)

        input_nodes = [
            make_mock_node(node_id=f"node-{i}", content_hash=f"hash{i}")
            for i in range(1, 6)
        ]

        result = cached.rerank("test query", input_nodes, top_n=3)

        # Should return only top 3
        assert len(result) == 3
        # Highest scores: 0.5, 0.4, 0.3 (using pytest.approx for float comparison)
        assert result[0].score == pytest.approx(0.5)
        assert result[1].score == pytest.approx(0.4)
        assert result[2].score == pytest.approx(0.3)

    def test_top_n_none_returns_all(self) -> None:
        """Returns all results when top_n is None."""
        mock_reranker = MagicMock()
        mock_cache = MagicMock()
        mock_cache.get_rerank.return_value = None

        nodes_reranked = [
            make_mock_node(node_id=f"node-{i}", content_hash=f"hash{i}", score=0.1 * i)
            for i in range(1, 6)
        ]
        mock_reranker.rerank.return_value = nodes_reranked

        cached = CachedReranker(mock_reranker, mock_cache)

        input_nodes = [
            make_mock_node(node_id=f"node-{i}", content_hash=f"hash{i}")
            for i in range(1, 6)
        ]

        result = cached.rerank("test query", input_nodes, top_n=None)

        # Should return all 5 results
        assert len(result) == 5


class TestCachedRerankerEdgeCases:
    """Tests for edge cases."""

    def test_empty_nodes_returns_empty_list(self) -> None:
        """Returns empty list when no nodes provided."""
        mock_reranker = MagicMock()
        mock_cache = MagicMock()

        cached = CachedReranker(mock_reranker, mock_cache)

        result = cached.rerank("test query", [], top_n=10)

        assert result == []
        mock_reranker.rerank.assert_not_called()
        mock_cache.get_rerank.assert_not_called()

    def test_all_cache_hits_skips_reranker(self) -> None:
        """Skips reranker entirely when all nodes are cached."""
        mock_reranker = MagicMock()
        mock_cache = MagicMock()
        mock_cache.get_rerank.return_value = 0.75  # All cached

        cached = CachedReranker(mock_reranker, mock_cache)

        nodes = [
            make_mock_node(node_id=f"node-{i}", content_hash=f"hash{i}")
            for i in range(3)
        ]

        result = cached.rerank("test query", nodes, top_n=10)

        # Reranker should not be called
        mock_reranker.rerank.assert_not_called()

        # All results should have cached score
        assert len(result) == 3
        for node in result:
            assert node.score == 0.75

    def test_handles_zero_score(self) -> None:
        """Handles nodes with zero score correctly."""
        mock_reranker = MagicMock()
        mock_cache = MagicMock()
        mock_cache.get_rerank.return_value = None

        reranked_node = make_mock_node(node_id="node-1", content_hash="hash1", score=0.0)
        mock_reranker.rerank.return_value = [reranked_node]

        cached = CachedReranker(mock_reranker, mock_cache)

        node = make_mock_node(node_id="node-1", content_hash="hash1")

        result = cached.rerank("test query", [node], top_n=10)

        assert len(result) == 1
        assert result[0].score == 0.0

        # Should still cache zero score
        mock_cache.set_rerank.assert_called_once_with("test query", "hash1", "default", 0.0)

    def test_handles_none_score_as_zero(self) -> None:
        """Handles None score as 0.0."""
        mock_reranker = MagicMock()
        mock_cache = MagicMock()
        mock_cache.get_rerank.return_value = None

        reranked_node = make_mock_node(node_id="node-1", content_hash="hash1")
        reranked_node.score = None  # Explicitly None
        mock_reranker.rerank.return_value = [reranked_node]

        cached = CachedReranker(mock_reranker, mock_cache)

        node = make_mock_node(node_id="node-1", content_hash="hash1")

        result = cached.rerank("test query", [node], top_n=10)

        # Should cache 0.0 for None score
        mock_cache.set_rerank.assert_called_once_with("test query", "hash1", "default", 0.0)
