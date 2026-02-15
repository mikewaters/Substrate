"""Tests for catalog.search.hybrid module.

Tests for WeightedRRFRetriever and HybridRetriever classes.
"""

from unittest.mock import MagicMock, patch

import pytest
from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode

from catalog.search.hybrid import HybridRetriever, WeightedRRFRetriever


class TestWeightedRRFRetriever:
    """Tests for WeightedRRFRetriever class."""

    @pytest.fixture
    def mock_retriever_a(self) -> MagicMock:
        """Create mock retriever A."""
        retriever = MagicMock()
        return retriever

    @pytest.fixture
    def mock_retriever_b(self) -> MagicMock:
        """Create mock retriever B."""
        retriever = MagicMock()
        return retriever

    def _make_node_with_score(
        self, node_id: str, text: str, score: float
    ) -> NodeWithScore:
        """Create a NodeWithScore for testing."""
        node = TextNode(id_=node_id, text=text)
        return NodeWithScore(node=node, score=score)

    def test_init_basic(
        self, mock_retriever_a: MagicMock, mock_retriever_b: MagicMock
    ) -> None:
        """Test basic initialization."""
        retriever = WeightedRRFRetriever(
            retrievers=[mock_retriever_a, mock_retriever_b],
            weights=[1.0, 1.0],
            k=60,
            top_n=30,
        )

        assert len(retriever.retrievers) == 2
        assert retriever.weights == [1.0, 1.0]
        assert retriever.k == 60
        assert retriever.top_n == 30

    def test_init_default_values(
        self, mock_retriever_a: MagicMock, mock_retriever_b: MagicMock
    ) -> None:
        """Test initialization with default values."""
        retriever = WeightedRRFRetriever(
            retrievers=[mock_retriever_a, mock_retriever_b],
            weights=[1.0, 1.0],
        )

        assert retriever.k == 60
        assert retriever.top_n == 30

    def test_init_mismatched_lengths(
        self, mock_retriever_a: MagicMock, mock_retriever_b: MagicMock
    ) -> None:
        """Test initialization fails with mismatched retriever/weight lengths."""
        with pytest.raises(ValueError, match="must match"):
            WeightedRRFRetriever(
                retrievers=[mock_retriever_a, mock_retriever_b],
                weights=[1.0],  # Only one weight for two retrievers
            )

    def test_init_negative_weight(
        self, mock_retriever_a: MagicMock, mock_retriever_b: MagicMock
    ) -> None:
        """Test initialization fails with negative weight."""
        with pytest.raises(ValueError, match="non-negative"):
            WeightedRRFRetriever(
                retrievers=[mock_retriever_a, mock_retriever_b],
                weights=[1.0, -0.5],
            )

    def test_rrf_calculation_single_retriever(
        self, mock_retriever_a: MagicMock
    ) -> None:
        """Test RRF calculation with a single retriever."""
        # Retriever A returns 3 results
        mock_retriever_a.retrieve.return_value = [
            self._make_node_with_score("node1", "text1", 0.9),
            self._make_node_with_score("node2", "text2", 0.8),
            self._make_node_with_score("node3", "text3", 0.7),
        ]

        retriever = WeightedRRFRetriever(
            retrievers=[mock_retriever_a],
            weights=[1.0],
            k=60,
            top_n=10,
        )

        query = QueryBundle(query_str="test query")
        results = retriever._retrieve(query)

        # With k=60, weight=1.0:
        # node1: 1.0 / (60 + 0 + 1) = 1/61
        # node2: 1.0 / (60 + 1 + 1) = 1/62
        # node3: 1.0 / (60 + 2 + 1) = 1/63
        assert len(results) == 3
        assert results[0].node.node_id == "node1"
        assert results[1].node.node_id == "node2"
        assert results[2].node.node_id == "node3"

        # Verify scores are correct
        assert abs(results[0].score - (1.0 / 61)) < 1e-10
        assert abs(results[1].score - (1.0 / 62)) < 1e-10
        assert abs(results[2].score - (1.0 / 63)) < 1e-10

    def test_rrf_calculation_two_retrievers_no_overlap(
        self, mock_retriever_a: MagicMock, mock_retriever_b: MagicMock
    ) -> None:
        """Test RRF calculation with two retrievers, no overlapping results."""
        mock_retriever_a.retrieve.return_value = [
            self._make_node_with_score("node1", "text1", 0.9),
            self._make_node_with_score("node2", "text2", 0.8),
        ]
        mock_retriever_b.retrieve.return_value = [
            self._make_node_with_score("node3", "text3", 0.95),
            self._make_node_with_score("node4", "text4", 0.85),
        ]

        retriever = WeightedRRFRetriever(
            retrievers=[mock_retriever_a, mock_retriever_b],
            weights=[1.0, 1.0],
            k=60,
            top_n=10,
        )

        query = QueryBundle(query_str="test query")
        results = retriever._retrieve(query)

        # All 4 nodes should be returned
        assert len(results) == 4
        node_ids = [r.node.node_id for r in results]
        assert set(node_ids) == {"node1", "node2", "node3", "node4"}

    def test_rrf_calculation_two_retrievers_with_overlap(
        self, mock_retriever_a: MagicMock, mock_retriever_b: MagicMock
    ) -> None:
        """Test RRF calculation with overlapping results (node appears in both)."""
        # Both retrievers return node1, with node1 at rank 0 in A and rank 1 in B
        mock_retriever_a.retrieve.return_value = [
            self._make_node_with_score("node1", "text1", 0.9),
            self._make_node_with_score("node2", "text2", 0.8),
        ]
        mock_retriever_b.retrieve.return_value = [
            self._make_node_with_score("node3", "text3", 0.95),
            self._make_node_with_score("node1", "text1", 0.85),
        ]

        retriever = WeightedRRFRetriever(
            retrievers=[mock_retriever_a, mock_retriever_b],
            weights=[1.0, 1.0],
            k=60,
            top_n=10,
        )

        query = QueryBundle(query_str="test query")
        results = retriever._retrieve(query)

        # 3 unique nodes should be returned
        assert len(results) == 3

        # node1 should have highest score (appears in both retrievers)
        # node1 score: 1/(60+0+1) + 1/(60+1+1) = 1/61 + 1/62
        expected_node1_score = (1.0 / 61) + (1.0 / 62)

        # Find node1 in results
        node1_result = next(r for r in results if r.node.node_id == "node1")
        assert abs(node1_result.score - expected_node1_score) < 1e-10

        # node1 should be ranked first due to combined score
        assert results[0].node.node_id == "node1"

    def test_weight_application(
        self, mock_retriever_a: MagicMock, mock_retriever_b: MagicMock
    ) -> None:
        """Test that weights are correctly applied to RRF scores."""
        mock_retriever_a.retrieve.return_value = [
            self._make_node_with_score("node1", "text1", 0.9),
        ]
        mock_retriever_b.retrieve.return_value = [
            self._make_node_with_score("node2", "text2", 0.9),
        ]

        # Weight retriever A at 2.0, B at 1.0
        retriever = WeightedRRFRetriever(
            retrievers=[mock_retriever_a, mock_retriever_b],
            weights=[2.0, 1.0],
            k=60,
            top_n=10,
        )

        query = QueryBundle(query_str="test query")
        results = retriever._retrieve(query)

        assert len(results) == 2

        # node1 should have score 2.0 / 61 (higher weight)
        # node2 should have score 1.0 / 61 (lower weight)
        node1_result = next(r for r in results if r.node.node_id == "node1")
        node2_result = next(r for r in results if r.node.node_id == "node2")

        assert abs(node1_result.score - (2.0 / 61)) < 1e-10
        assert abs(node2_result.score - (1.0 / 61)) < 1e-10

        # node1 should rank higher due to higher weight
        assert results[0].node.node_id == "node1"
        assert results[1].node.node_id == "node2"

    def test_top_n_limiting(
        self, mock_retriever_a: MagicMock
    ) -> None:
        """Test that top_n limits the number of results."""
        # Return 5 results
        mock_retriever_a.retrieve.return_value = [
            self._make_node_with_score(f"node{i}", f"text{i}", 1.0 - i * 0.1)
            for i in range(5)
        ]

        retriever = WeightedRRFRetriever(
            retrievers=[mock_retriever_a],
            weights=[1.0],
            k=60,
            top_n=3,  # Limit to 3
        )

        query = QueryBundle(query_str="test query")
        results = retriever._retrieve(query)

        # Should only return 3 results
        assert len(results) == 3
        # Should be the top 3 by RRF score
        assert results[0].node.node_id == "node0"
        assert results[1].node.node_id == "node1"
        assert results[2].node.node_id == "node2"

    def test_zero_weight_retriever_ignored(
        self, mock_retriever_a: MagicMock, mock_retriever_b: MagicMock
    ) -> None:
        """Test that a retriever with weight 0 contributes nothing."""
        mock_retriever_a.retrieve.return_value = [
            self._make_node_with_score("node1", "text1", 0.9),
        ]
        mock_retriever_b.retrieve.return_value = [
            self._make_node_with_score("node2", "text2", 0.95),
        ]

        retriever = WeightedRRFRetriever(
            retrievers=[mock_retriever_a, mock_retriever_b],
            weights=[1.0, 0.0],  # B has weight 0
            k=60,
            top_n=10,
        )

        query = QueryBundle(query_str="test query")
        results = retriever._retrieve(query)

        # Only node1 appears since node2 has zero weight and contributes nothing
        assert len(results) == 1
        assert results[0].node.node_id == "node1"
        assert results[0].score > 0

    def test_empty_results(
        self, mock_retriever_a: MagicMock, mock_retriever_b: MagicMock
    ) -> None:
        """Test handling of empty results from retrievers."""
        mock_retriever_a.retrieve.return_value = []
        mock_retriever_b.retrieve.return_value = []

        retriever = WeightedRRFRetriever(
            retrievers=[mock_retriever_a, mock_retriever_b],
            weights=[1.0, 1.0],
            k=60,
            top_n=10,
        )

        query = QueryBundle(query_str="test query")
        results = retriever._retrieve(query)

        assert results == []

    def test_retriever_failure_handled(
        self, mock_retriever_a: MagicMock, mock_retriever_b: MagicMock
    ) -> None:
        """Test that retriever failures are handled gracefully."""
        mock_retriever_a.retrieve.side_effect = RuntimeError("Network error")
        mock_retriever_b.retrieve.return_value = [
            self._make_node_with_score("node1", "text1", 0.9),
        ]

        retriever = WeightedRRFRetriever(
            retrievers=[mock_retriever_a, mock_retriever_b],
            weights=[1.0, 1.0],
            k=60,
            top_n=10,
        )

        query = QueryBundle(query_str="test query")
        results = retriever._retrieve(query)

        # Should still return results from B
        assert len(results) == 1
        assert results[0].node.node_id == "node1"

    def test_different_k_values(
        self, mock_retriever_a: MagicMock
    ) -> None:
        """Test that different k values affect scoring."""
        mock_retriever_a.retrieve.return_value = [
            self._make_node_with_score("node1", "text1", 0.9),
            self._make_node_with_score("node2", "text2", 0.8),
        ]

        # With k=10 (small k gives more weight to top ranks)
        retriever_small_k = WeightedRRFRetriever(
            retrievers=[mock_retriever_a],
            weights=[1.0],
            k=10,
            top_n=10,
        )

        # With k=100 (large k flattens the ranking)
        retriever_large_k = WeightedRRFRetriever(
            retrievers=[mock_retriever_a],
            weights=[1.0],
            k=100,
            top_n=10,
        )

        query = QueryBundle(query_str="test query")

        results_small = retriever_small_k._retrieve(query)
        results_large = retriever_large_k._retrieve(query)

        # With small k, difference between rank 0 and rank 1 is larger
        diff_small = results_small[0].score - results_small[1].score
        diff_large = results_large[0].score - results_large[1].score

        # Small k: 1/11 - 1/12 = (12-11)/(11*12) = 1/132
        # Large k: 1/101 - 1/102 = (102-101)/(101*102) = 1/10302
        assert diff_small > diff_large


class TestHybridRetriever:
    """Tests for HybridRetriever factory class."""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """Create mock SQLAlchemy session."""
        return MagicMock()

    @pytest.fixture
    def mock_vector_manager(self) -> MagicMock:
        """Create mock VectorStoreManager."""
        manager = MagicMock()
        return manager

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock RAGSettings."""
        settings = MagicMock()
        settings.rrf_k = 60
        settings.rrf_original_weight = 2.0
        settings.fts_top_k = 20
        settings.vector_top_k = 20
        settings.fusion_top_k = 30
        return settings

    def test_init_default_vector_manager(self, mock_session: MagicMock) -> None:
        """Test HybridRetriever creates default VectorStoreManager."""
        with patch("catalog.search.hybrid.VectorStoreManager") as mock_vm_cls, \
             patch("catalog.search.hybrid.get_settings") as mock_get_settings:
            mock_vm_cls.return_value = MagicMock()
            mock_get_settings.return_value.rag = MagicMock()

            HybridRetriever(mock_session)

            mock_vm_cls.assert_called_once()

    def test_init_custom_vector_manager(
        self, mock_session: MagicMock, mock_vector_manager: MagicMock
    ) -> None:
        """Test HybridRetriever accepts custom VectorStoreManager."""
        with patch("catalog.search.hybrid.get_settings") as mock_get_settings:
            mock_get_settings.return_value.rag = MagicMock()

            factory = HybridRetriever(mock_session, mock_vector_manager)

            assert factory._vector_manager is mock_vector_manager

    def test_build_returns_weighted_rrf_retriever(
        self,
        mock_session: MagicMock,
        mock_vector_manager: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test build() returns a WeightedRRFRetriever."""
        with patch("catalog.search.hybrid.get_settings") as mock_get_settings, \
             patch("catalog.search.hybrid.FTSChunkRetriever"):
            mock_get_settings.return_value.rag = mock_settings

            factory = HybridRetriever(mock_session, mock_vector_manager)
            retriever = factory.build()

            assert isinstance(retriever, WeightedRRFRetriever)

    def test_build_uses_settings_values(
        self,
        mock_session: MagicMock,
        mock_vector_manager: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test build() uses values from rag settings."""
        with patch("catalog.search.hybrid.get_settings") as mock_get_settings, \
             patch("catalog.search.hybrid.FTSChunkRetriever") as mock_fts_cls:
            mock_get_settings.return_value.rag = mock_settings

            factory = HybridRetriever(mock_session, mock_vector_manager)
            retriever = factory.build()

            # Check that FTS retriever was created with correct top_k
            mock_fts_cls.assert_called_once()
            call_kwargs = mock_fts_cls.call_args.kwargs
            assert call_kwargs["similarity_top_k"] == mock_settings.fts_top_k

            # Check RRF retriever has correct settings
            assert retriever.k == mock_settings.rrf_k
            assert retriever.top_n == mock_settings.fusion_top_k
            assert retriever.weights == [
                mock_settings.rrf_original_weight,
                mock_settings.rrf_original_weight,
            ]

    def test_build_with_custom_top_k_values(
        self,
        mock_session: MagicMock,
        mock_vector_manager: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test build() accepts custom top_k overrides."""
        with patch("catalog.search.hybrid.get_settings") as mock_get_settings, \
             patch("catalog.search.hybrid.FTSChunkRetriever") as mock_fts_cls:
            mock_get_settings.return_value.rag = mock_settings

            factory = HybridRetriever(mock_session, mock_vector_manager)
            retriever = factory.build(
                fts_top_k=50,
                vector_top_k=50,
                fusion_top_k=40,
            )

            # FTS should use custom value
            mock_fts_cls.assert_called_once()
            call_kwargs = mock_fts_cls.call_args.kwargs
            assert call_kwargs["similarity_top_k"] == 50

            # Fusion should use custom value
            assert retriever.top_n == 40

    def test_build_with_dataset_filter(
        self,
        mock_session: MagicMock,
        mock_vector_manager: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test build() passes dataset filter to retrievers."""
        with patch("catalog.search.hybrid.get_settings") as mock_get_settings, \
             patch("catalog.search.hybrid.FTSChunkRetriever") as mock_fts_cls:
            mock_get_settings.return_value.rag = mock_settings

            factory = HybridRetriever(mock_session, mock_vector_manager)
            retriever = factory.build(dataset_name="obsidian")

            # FTS should have dataset filter
            mock_fts_cls.assert_called_once()
            call_kwargs = mock_fts_cls.call_args.kwargs
            assert call_kwargs["dataset_name"] == "obsidian"

            # Vector retriever should carry dataset filter
            vector_retriever = retriever.retrievers[1]
            assert vector_retriever._dataset_name == "obsidian"

    def test_build_without_dataset_filter(
        self,
        mock_session: MagicMock,
        mock_vector_manager: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test build() passes no filter when dataset_name is None."""
        with patch("catalog.search.hybrid.get_settings") as mock_get_settings, \
             patch("catalog.search.hybrid.FTSChunkRetriever") as mock_fts_cls:
            mock_get_settings.return_value.rag = mock_settings

            factory = HybridRetriever(mock_session, mock_vector_manager)
            retriever = factory.build(dataset_name=None)

            # FTS should have no dataset filter
            mock_fts_cls.assert_called_once()
            call_kwargs = mock_fts_cls.call_args.kwargs
            assert call_kwargs["dataset_name"] is None

            # Vector retriever should have no dataset filter
            vector_retriever = retriever.retrievers[1]
            assert vector_retriever._dataset_name is None

    def test_build_creates_two_retrievers(
        self,
        mock_session: MagicMock,
        mock_vector_manager: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test build() creates FTS and vector retrievers."""
        with patch("catalog.search.hybrid.get_settings") as mock_get_settings, \
             patch("catalog.search.hybrid.FTSChunkRetriever"):
            mock_get_settings.return_value.rag = mock_settings

            factory = HybridRetriever(mock_session, mock_vector_manager)
            retriever = factory.build()

            # Should have exactly 2 retrievers
            assert len(retriever.retrievers) == 2
            # Should have exactly 2 weights
            assert len(retriever.weights) == 2
