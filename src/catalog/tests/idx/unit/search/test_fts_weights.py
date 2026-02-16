"""Tests for BM25 weight routing by intent in FTSChunkRetriever."""

from unittest.mock import MagicMock, patch

import pytest
from llama_index.core.schema import QueryBundle

from catalog.search.fts_chunk import FTSChunkRetriever
from catalog.store.fts_chunk import FTSChunkResult


class TestFTSWeightRouting:
    """Tests for intent-based BM25 weight routing in FTSChunkRetriever."""

    @pytest.fixture
    def mock_fts_manager(self) -> MagicMock:
        """Create a mock FTSChunkManager."""
        manager = MagicMock()
        manager.search_with_scores.return_value = [
            FTSChunkResult(
                node_id="abc:0",
                text="test body content",
                source_doc_id="obsidian:test.md",
                score=0.9,
            )
        ]
        return manager

    def test_no_intent_passes_none_weights(self, mock_fts_manager: MagicMock) -> None:
        """Without query_intent, bm25_weights is None."""
        retriever = FTSChunkRetriever(
            fts_manager=mock_fts_manager,
            similarity_top_k=10,
        )
        retriever._retrieve(QueryBundle(query_str="test query"))

        mock_fts_manager.search_with_scores.assert_called_once()
        call_kwargs = mock_fts_manager.search_with_scores.call_args.kwargs
        assert call_kwargs.get("bm25_weights") is None

    def test_informational_intent_uses_low_heading_weight(
        self, mock_fts_manager: MagicMock
    ) -> None:
        """Informational intent uses low heading weight from settings."""
        mock_rag = MagicMock()
        mock_rag.bm25_heading_weight_informational = 0.25

        with patch("catalog.core.settings.get_settings") as mock_gs:
            mock_gs.return_value.rag = mock_rag

            retriever = FTSChunkRetriever(
                fts_manager=mock_fts_manager,
                similarity_top_k=10,
                query_intent="informational",
            )
            retriever._retrieve(QueryBundle(query_str="how does async work"))

        call_kwargs = mock_fts_manager.search_with_scores.call_args.kwargs
        assert call_kwargs["bm25_weights"] == "0.0, 0.25, 1.0, 0.0"

    def test_navigational_intent_uses_high_heading_weight(
        self, mock_fts_manager: MagicMock
    ) -> None:
        """Navigational intent uses high heading weight from settings."""
        mock_rag = MagicMock()
        mock_rag.bm25_heading_weight_navigational = 0.80

        with patch("catalog.core.settings.get_settings") as mock_gs:
            mock_gs.return_value.rag = mock_rag

            retriever = FTSChunkRetriever(
                fts_manager=mock_fts_manager,
                similarity_top_k=10,
                query_intent="navigational",
            )
            retriever._retrieve(QueryBundle(query_str="MyDocument"))

        call_kwargs = mock_fts_manager.search_with_scores.call_args.kwargs
        assert call_kwargs["bm25_weights"] == "0.0, 0.8, 1.0, 0.0"

    def test_intent_property_getter_setter(self) -> None:
        """query_intent property can be get and set."""
        retriever = FTSChunkRetriever(
            fts_manager=MagicMock(),
            similarity_top_k=10,
        )
        assert retriever.query_intent is None

        retriever.query_intent = "navigational"
        assert retriever.query_intent == "navigational"

        retriever.query_intent = "informational"
        assert retriever.query_intent == "informational"

    def test_custom_heading_weight_from_settings(
        self, mock_fts_manager: MagicMock
    ) -> None:
        """Custom heading weight values from settings are used."""
        mock_rag = MagicMock()
        mock_rag.bm25_heading_weight_informational = 0.50

        with patch("catalog.core.settings.get_settings") as mock_gs:
            mock_gs.return_value.rag = mock_rag

            retriever = FTSChunkRetriever(
                fts_manager=mock_fts_manager,
                similarity_top_k=10,
                query_intent="informational",
            )
            retriever._retrieve(QueryBundle(query_str="test"))

        call_kwargs = mock_fts_manager.search_with_scores.call_args.kwargs
        assert call_kwargs["bm25_weights"] == "0.0, 0.5, 1.0, 0.0"
