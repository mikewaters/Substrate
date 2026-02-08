"""Tests for catalog.search.postprocessors module.

Tests for RRF postprocessors: TopRankBonusPostprocessor, KeywordChunkSelector,
PerDocDedupePostprocessor, and ScoreNormalizerPostprocessor.
"""

from unittest.mock import MagicMock, patch

import pytest
from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode

from catalog.search.postprocessors import (
    KeywordChunkSelector,
    PerDocDedupePostprocessor,
    ScoreNormalizerPostprocessor,
    TopRankBonusPostprocessor,
)


def make_node(
    node_id: str,
    text: str,
    source_doc_id: str,
    score: float,
) -> NodeWithScore:
    """Helper to create a NodeWithScore for testing."""
    node = TextNode(
        id_=node_id,
        text=text,
        metadata={"source_doc_id": source_doc_id},
    )
    return NodeWithScore(node=node, score=score)


class TestTopRankBonusPostprocessor:
    """Tests for TopRankBonusPostprocessor."""

    def test_init_default_from_settings(self) -> None:
        """Test initialization reads defaults from settings."""
        with patch("catalog.search.postprocessors.get_settings") as mock_settings:
            mock_rag = MagicMock()
            mock_rag.rrf_rank1_bonus = 0.1
            mock_rag.rrf_rank23_bonus = 0.05
            mock_settings.return_value.rag = mock_rag

            postprocessor = TopRankBonusPostprocessor()

            assert postprocessor.rank_1_bonus == 0.1
            assert postprocessor.rank_2_3_bonus == 0.05

    def test_init_custom_values(self) -> None:
        """Test initialization with custom values."""
        with patch("catalog.search.postprocessors.get_settings") as mock_settings:
            mock_rag = MagicMock()
            mock_rag.rrf_rank1_bonus = 0.1
            mock_rag.rrf_rank23_bonus = 0.05
            mock_settings.return_value.rag = mock_rag

            postprocessor = TopRankBonusPostprocessor(
                rank_1_bonus=0.2,
                rank_2_3_bonus=0.08,
            )

            assert postprocessor.rank_1_bonus == 0.2
            assert postprocessor.rank_2_3_bonus == 0.08

    def test_rank_1_gets_bonus(self) -> None:
        """Test rank 1 result receives rank_1_bonus."""
        with patch("catalog.search.postprocessors.get_settings") as mock_settings:
            mock_rag = MagicMock()
            mock_rag.rrf_rank1_bonus = 0.05
            mock_rag.rrf_rank23_bonus = 0.02
            mock_settings.return_value.rag = mock_rag

            postprocessor = TopRankBonusPostprocessor()
            nodes = [make_node("1", "text", "doc:1", 0.5)]

            result = postprocessor.postprocess_nodes(nodes)

            assert len(result) == 1
            assert result[0].score == pytest.approx(0.55)  # 0.5 + 0.05

    def test_ranks_2_3_get_bonus(self) -> None:
        """Test ranks 2-3 receive rank_2_3_bonus."""
        with patch("catalog.search.postprocessors.get_settings") as mock_settings:
            mock_rag = MagicMock()
            mock_rag.rrf_rank1_bonus = 0.05
            mock_rag.rrf_rank23_bonus = 0.02
            mock_settings.return_value.rag = mock_rag

            postprocessor = TopRankBonusPostprocessor()
            nodes = [
                make_node("1", "text", "doc:1", 0.5),
                make_node("2", "text", "doc:2", 0.4),
                make_node("3", "text", "doc:3", 0.3),
            ]

            result = postprocessor.postprocess_nodes(nodes)

            assert len(result) == 3
            assert result[0].score == pytest.approx(0.55)  # rank 1: 0.5 + 0.05
            assert result[1].score == pytest.approx(0.42)  # rank 2: 0.4 + 0.02
            assert result[2].score == pytest.approx(0.32)  # rank 3: 0.3 + 0.02

    def test_rank_4_and_below_no_bonus(self) -> None:
        """Test rank 4+ receive no bonus."""
        with patch("catalog.search.postprocessors.get_settings") as mock_settings:
            mock_rag = MagicMock()
            mock_rag.rrf_rank1_bonus = 0.05
            mock_rag.rrf_rank23_bonus = 0.02
            mock_settings.return_value.rag = mock_rag

            postprocessor = TopRankBonusPostprocessor()
            nodes = [
                make_node("1", "text", "doc:1", 0.5),
                make_node("2", "text", "doc:2", 0.4),
                make_node("3", "text", "doc:3", 0.3),
                make_node("4", "text", "doc:4", 0.2),
                make_node("5", "text", "doc:5", 0.1),
            ]

            result = postprocessor.postprocess_nodes(nodes)

            assert result[3].score == pytest.approx(0.2)  # rank 4: no bonus
            assert result[4].score == pytest.approx(0.1)  # rank 5: no bonus

    def test_empty_nodes(self) -> None:
        """Test empty node list returns empty."""
        with patch("catalog.search.postprocessors.get_settings") as mock_settings:
            mock_rag = MagicMock()
            mock_rag.rrf_rank1_bonus = 0.05
            mock_rag.rrf_rank23_bonus = 0.02
            mock_settings.return_value.rag = mock_rag

            postprocessor = TopRankBonusPostprocessor()
            result = postprocessor.postprocess_nodes([])

            assert result == []


class TestKeywordChunkSelector:
    """Tests for KeywordChunkSelector."""

    def test_selects_chunk_with_most_keyword_hits(self) -> None:
        """Test selects chunk with most query term matches."""
        selector = KeywordChunkSelector()

        # Two chunks from same doc - chunk 2 has more keyword hits
        nodes = [
            make_node("1", "Introduction to the topic", "doc:file.md", 0.5),
            make_node("2", "Python and machine learning basics", "doc:file.md", 0.4),
        ]
        query = QueryBundle(query_str="python machine learning")

        result = selector.postprocess_nodes(nodes, query)

        # Should select chunk 2 (3 hits: python, machine, learning)
        assert len(result) == 1
        assert result[0].node.id_ == "2"

    def test_multiple_docs_each_get_best_chunk(self) -> None:
        """Test each document keeps its best chunk."""
        selector = KeywordChunkSelector()

        nodes = [
            make_node("1", "Python intro", "doc:a.md", 0.5),
            make_node("2", "Python advanced concepts", "doc:a.md", 0.4),
            make_node("3", "Java basics", "doc:b.md", 0.6),
            make_node("4", "Java Python comparison", "doc:b.md", 0.3),
        ]
        query = QueryBundle(query_str="python programming")

        result = selector.postprocess_nodes(nodes, query)

        # Should have 2 results (one per doc)
        assert len(result) == 2

        # Get results by source_doc_id
        result_by_doc = {r.node.metadata["source_doc_id"]: r for r in result}

        # doc:a.md should keep chunk 2 (python, advanced, concepts - 1 hit)
        # Actually chunk 1 and 2 both have 1 hit (python), so highest score wins
        assert result_by_doc["doc:a.md"].node.id_ == "1"  # higher score

        # doc:b.md should keep chunk 4 (java, python - 1 hit vs 0)
        assert result_by_doc["doc:b.md"].node.id_ == "4"

    def test_tiebreaker_uses_score(self) -> None:
        """Test equal keyword hits uses score as tiebreaker."""
        selector = KeywordChunkSelector()

        # Both chunks have same keyword hits
        nodes = [
            make_node("1", "Python code", "doc:file.md", 0.3),
            make_node("2", "Python script", "doc:file.md", 0.7),
        ]
        query = QueryBundle(query_str="python")

        result = selector.postprocess_nodes(nodes, query)

        # Should select chunk 2 (higher score)
        assert len(result) == 1
        assert result[0].node.id_ == "2"

    def test_empty_query_returns_original(self) -> None:
        """Test empty query returns original nodes."""
        selector = KeywordChunkSelector()

        nodes = [make_node("1", "text", "doc:file.md", 0.5)]
        query = QueryBundle(query_str="")

        result = selector.postprocess_nodes(nodes, query)

        assert result == nodes

    def test_no_query_bundle_returns_original(self) -> None:
        """Test missing query bundle returns original nodes."""
        selector = KeywordChunkSelector()

        nodes = [make_node("1", "text", "doc:file.md", 0.5)]

        result = selector.postprocess_nodes(nodes, query_bundle=None)

        assert result == nodes

    def test_empty_nodes(self) -> None:
        """Test empty node list returns empty."""
        selector = KeywordChunkSelector()
        query = QueryBundle(query_str="test")

        result = selector.postprocess_nodes([], query)

        assert result == []

    def test_results_ordered_by_score(self) -> None:
        """Test final results are ordered by score descending."""
        selector = KeywordChunkSelector()

        nodes = [
            make_node("1", "Python", "doc:a.md", 0.3),
            make_node("2", "Python", "doc:b.md", 0.8),
            make_node("3", "Python", "doc:c.md", 0.5),
        ]
        query = QueryBundle(query_str="python")

        result = selector.postprocess_nodes(nodes, query)

        scores = [r.score for r in result]
        assert scores == [0.8, 0.5, 0.3]


class TestPerDocDedupePostprocessor:
    """Tests for PerDocDedupePostprocessor."""

    def test_keeps_best_score_per_doc(self) -> None:
        """Test keeps highest-scoring chunk per document."""
        deduper = PerDocDedupePostprocessor()

        nodes = [
            make_node("1", "chunk 1", "doc:file.md", 0.3),
            make_node("2", "chunk 2", "doc:file.md", 0.8),
            make_node("3", "chunk 3", "doc:file.md", 0.5),
        ]

        result = deduper.postprocess_nodes(nodes)

        assert len(result) == 1
        assert result[0].node.id_ == "2"
        assert result[0].score == 0.8

    def test_multiple_docs_each_get_best(self) -> None:
        """Test each document keeps only its best chunk."""
        deduper = PerDocDedupePostprocessor()

        nodes = [
            make_node("1", "chunk 1", "doc:a.md", 0.3),
            make_node("2", "chunk 2", "doc:a.md", 0.5),
            make_node("3", "chunk 1", "doc:b.md", 0.9),
            make_node("4", "chunk 2", "doc:b.md", 0.2),
        ]

        result = deduper.postprocess_nodes(nodes)

        assert len(result) == 2

        # Results should be ordered by score
        assert result[0].node.id_ == "3"  # score 0.9
        assert result[1].node.id_ == "2"  # score 0.5

    def test_results_sorted_by_score(self) -> None:
        """Test results are sorted by score descending."""
        deduper = PerDocDedupePostprocessor()

        nodes = [
            make_node("1", "text", "doc:a.md", 0.2),
            make_node("2", "text", "doc:b.md", 0.9),
            make_node("3", "text", "doc:c.md", 0.5),
        ]

        result = deduper.postprocess_nodes(nodes)

        scores = [r.score for r in result]
        assert scores == [0.9, 0.5, 0.2]

    def test_empty_nodes(self) -> None:
        """Test empty node list returns empty."""
        deduper = PerDocDedupePostprocessor()

        result = deduper.postprocess_nodes([])

        assert result == []

    def test_fallback_to_node_id(self) -> None:
        """Test uses node ID when source_doc_id is missing."""
        deduper = PerDocDedupePostprocessor()

        # Create nodes without source_doc_id
        node1 = TextNode(id_="node-1", text="text 1", metadata={})
        node2 = TextNode(id_="node-2", text="text 2", metadata={})

        nodes = [
            NodeWithScore(node=node1, score=0.5),
            NodeWithScore(node=node2, score=0.8),
        ]

        result = deduper.postprocess_nodes(nodes)

        # Should keep both (different fallback IDs)
        assert len(result) == 2


class TestScoreNormalizerPostprocessor:
    """Tests for ScoreNormalizerPostprocessor."""

    def test_init_default_retriever_type(self) -> None:
        """Test default retriever_type is bm25."""
        normalizer = ScoreNormalizerPostprocessor()
        assert normalizer.retriever_type == "bm25"

    def test_init_custom_retriever_type(self) -> None:
        """Test custom retriever_type."""
        normalizer = ScoreNormalizerPostprocessor(retriever_type="vector")
        assert normalizer.retriever_type == "vector"

    def test_normalizes_to_0_1_range(self) -> None:
        """Test scores are normalized to [0, 1] range."""
        normalizer = ScoreNormalizerPostprocessor()

        nodes = [
            make_node("1", "text", "doc:1", 10.0),
            make_node("2", "text", "doc:2", 5.0),
            make_node("3", "text", "doc:3", 0.0),
        ]

        result = normalizer.postprocess_nodes(nodes)

        assert len(result) == 3
        assert result[0].score == pytest.approx(1.0)  # max -> 1.0
        assert result[1].score == pytest.approx(0.5)  # mid -> 0.5
        assert result[2].score == pytest.approx(0.0)  # min -> 0.0

    def test_negative_scores_handled(self) -> None:
        """Test negative scores are normalized correctly."""
        normalizer = ScoreNormalizerPostprocessor()

        nodes = [
            make_node("1", "text", "doc:1", 10.0),
            make_node("2", "text", "doc:2", -5.0),
            make_node("3", "text", "doc:3", -10.0),
        ]

        result = normalizer.postprocess_nodes(nodes)

        # Range is -10 to 10 = 20
        assert result[0].score == pytest.approx(1.0)  # (10 - (-10)) / 20 = 1.0
        assert result[1].score == pytest.approx(0.25)  # (-5 - (-10)) / 20 = 0.25
        assert result[2].score == pytest.approx(0.0)  # (-10 - (-10)) / 20 = 0.0

    def test_all_equal_scores_return_1(self) -> None:
        """Test all equal scores become 1.0."""
        normalizer = ScoreNormalizerPostprocessor()

        nodes = [
            make_node("1", "text", "doc:1", 5.0),
            make_node("2", "text", "doc:2", 5.0),
            make_node("3", "text", "doc:3", 5.0),
        ]

        result = normalizer.postprocess_nodes(nodes)

        assert all(r.score == 1.0 for r in result)

    def test_single_node_becomes_1(self) -> None:
        """Test single node gets score 1.0."""
        normalizer = ScoreNormalizerPostprocessor()

        nodes = [make_node("1", "text", "doc:1", 42.0)]

        result = normalizer.postprocess_nodes(nodes)

        assert len(result) == 1
        assert result[0].score == 1.0

    def test_empty_nodes(self) -> None:
        """Test empty node list returns empty."""
        normalizer = ScoreNormalizerPostprocessor()

        result = normalizer.postprocess_nodes([])

        assert result == []

    def test_preserves_node_order(self) -> None:
        """Test normalization preserves original order."""
        normalizer = ScoreNormalizerPostprocessor()

        nodes = [
            make_node("1", "text", "doc:1", 5.0),
            make_node("2", "text", "doc:2", 10.0),
            make_node("3", "text", "doc:3", 0.0),
        ]

        result = normalizer.postprocess_nodes(nodes)

        # Order should be preserved
        assert result[0].node.id_ == "1"
        assert result[1].node.id_ == "2"
        assert result[2].node.id_ == "3"

    def test_preserves_node_metadata(self) -> None:
        """Test normalization preserves node content and metadata."""
        normalizer = ScoreNormalizerPostprocessor()

        original_node = TextNode(
            id_="test-id",
            text="test text",
            metadata={"source_doc_id": "doc:test", "custom": "value"},
        )
        nodes = [NodeWithScore(node=original_node, score=5.0)]

        result = normalizer.postprocess_nodes(nodes)

        assert result[0].node.id_ == "test-id"
        assert result[0].node.text == "test text"
        assert result[0].node.metadata["source_doc_id"] == "doc:test"
        assert result[0].node.metadata["custom"] == "value"
