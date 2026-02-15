"""Tests for catalog.search.vector module."""

from unittest.mock import MagicMock

from catalog.search.vector import VectorSearch
from catalog.store.vector import VectorQueryHit


class TestVectorSearch:
    """Tests for vector search service behavior."""

    def test_delegates_semantic_query_to_vector_manager(self) -> None:
        """VectorSearch delegates semantic retrieval to VectorStoreManager."""
        manager = MagicMock()
        manager.semantic_query.return_value = [
            VectorQueryHit(
                node_id="chunk-a",
                score=0.9,
                metadata={
                    "source_doc_id": "obsidian:path/a.md",
                    "chunk_seq": 0,
                    "chunk_pos": 12,
                },
            )
        ]
        manager.get_vector_store.return_value = MagicMock()

        search = VectorSearch(vector_manager=manager)
        search._lookup_chunk_text = MagicMock(return_value={"chunk-a": "alpha content"})

        results = search.search(
            query="find me",
            top_k=5,
            dataset_name="obsidian",
        )

        manager.semantic_query.assert_called_once_with(
            query="find me",
            top_k=5,
            dataset_name="obsidian",
        )
        assert len(results) == 1
        assert results[0].dataset_name == "obsidian"
        assert results[0].path == "path/a.md"
        assert results[0].metadata["node_id"] == "chunk-a"

    def test_returns_empty_when_manager_returns_no_hits(self) -> None:
        """Empty semantic hits produce an empty result list."""
        manager = MagicMock()
        manager.semantic_query.return_value = []
        manager.get_vector_store.return_value = MagicMock()

        search = VectorSearch(vector_manager=manager)
        results = search.search(query="none", top_k=3)

        assert results == []
