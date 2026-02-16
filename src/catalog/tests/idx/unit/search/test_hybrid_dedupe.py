"""Tests for per-document deduplication in WeightedRRFRetriever."""

from unittest.mock import MagicMock

import pytest
from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode

from catalog.search.hybrid import WeightedRRFRetriever


def _make_node(node_id: str, text: str, score: float, source_doc_id: str) -> NodeWithScore:
    """Create a NodeWithScore with source_doc_id metadata."""
    node = TextNode(
        id_=node_id,
        text=text,
        metadata={"source_doc_id": source_doc_id},
    )
    return NodeWithScore(node=node, score=score)


class TestWeightedRRFDedupe:
    """Tests for per-doc dedupe in WeightedRRFRetriever."""

    def test_dedupe_disabled_keeps_duplicates(self) -> None:
        """With dedupe disabled, duplicate docs are preserved."""
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = [
            _make_node("n1", "chunk1", 0.9, "obsidian:doc.md"),
            _make_node("n2", "chunk2", 0.8, "obsidian:doc.md"),
            _make_node("n3", "chunk3", 0.7, "obsidian:other.md"),
        ]

        rrf = WeightedRRFRetriever(
            retrievers=[mock_retriever],
            weights=[1.0],
            enable_dedupe=False,
        )

        results = rrf._retrieve(QueryBundle(query_str="test"))
        doc_ids = [r.node.metadata.get("source_doc_id") for r in results]
        assert doc_ids.count("obsidian:doc.md") == 2

    def test_dedupe_enabled_collapses_duplicates(self) -> None:
        """With dedupe enabled, only best chunk per doc is kept."""
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = [
            _make_node("n1", "chunk1", 0.9, "obsidian:doc.md"),
            _make_node("n2", "chunk2", 0.8, "obsidian:doc.md"),
            _make_node("n3", "chunk3", 0.7, "obsidian:other.md"),
        ]

        rrf = WeightedRRFRetriever(
            retrievers=[mock_retriever],
            weights=[1.0],
            enable_dedupe=True,
        )

        results = rrf._retrieve(QueryBundle(query_str="test"))
        doc_ids = [r.node.metadata.get("source_doc_id") for r in results]
        # Each doc should appear only once
        assert doc_ids.count("obsidian:doc.md") == 1
        assert doc_ids.count("obsidian:other.md") == 1
        assert len(results) == 2

    def test_dedupe_keeps_best_scoring_chunk(self) -> None:
        """Dedupe keeps the highest-scoring chunk per doc."""
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = [
            _make_node("n1", "best", 0.9, "obsidian:doc.md"),
            _make_node("n2", "worse", 0.3, "obsidian:doc.md"),
        ]

        rrf = WeightedRRFRetriever(
            retrievers=[mock_retriever],
            weights=[1.0],
            enable_dedupe=True,
        )

        results = rrf._retrieve(QueryBundle(query_str="test"))
        assert len(results) == 1
        # The kept node should be n1 (higher rank = higher RRF score)
        assert results[0].node.node_id == "n1"

    def test_dedupe_no_duplicates_no_change(self) -> None:
        """Dedupe with all unique docs returns all results."""
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = [
            _make_node("n1", "a", 0.9, "obsidian:a.md"),
            _make_node("n2", "b", 0.8, "obsidian:b.md"),
            _make_node("n3", "c", 0.7, "obsidian:c.md"),
        ]

        rrf = WeightedRRFRetriever(
            retrievers=[mock_retriever],
            weights=[1.0],
            enable_dedupe=True,
        )

        results = rrf._retrieve(QueryBundle(query_str="test"))
        assert len(results) == 3

    def test_dedupe_empty_results(self) -> None:
        """Dedupe with empty results returns empty list."""
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = []

        rrf = WeightedRRFRetriever(
            retrievers=[mock_retriever],
            weights=[1.0],
            enable_dedupe=True,
        )

        results = rrf._retrieve(QueryBundle(query_str="test"))
        assert results == []
