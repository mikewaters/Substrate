"""catalog.search.fts_chunk - LlamaIndex retriever for FTS5 chunk search.

Provides a LlamaIndex-compatible retriever that queries the chunks_fts
virtual table via FTSChunkManager.

Example usage:
    from catalog.search.fts_chunk import FTSChunkRetriever
    from catalog.store.database import get_session
    from catalog.store.session_context import use_session

    with get_session() as session:
        with use_session(session):
            retriever = FTSChunkRetriever(similarity_top_k=10, dataset_name="obsidian")
            nodes = retriever.retrieve("machine learning concepts")
"""

from agentlayer.logging import get_logger
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode

from catalog.search.intent import QueryIntent
from catalog.store.fts_chunk import FTSChunkManager

__all__ = [
    "FTSChunkRetriever",
]

logger = get_logger(__name__)


class FTSChunkRetriever(BaseRetriever):
    """LlamaIndex retriever using FTS5 full-text search on document chunks.

    Queries the chunks_fts virtual table via FTSChunkManager and converts
    results to LlamaIndex NodeWithScore objects.

    Uses ambient session via contextvars. The session must be set
    via `use_session()` before calling retrieve methods.

    Attributes:
        fts_manager: The FTSChunkManager instance for database operations.
        similarity_top_k: Maximum number of results to return.
        dataset_name: Optional dataset filter (e.g., "obsidian").

    Example:
        with get_session() as session:
            with use_session(session):
                retriever = FTSChunkRetriever(
                    similarity_top_k=10,
                    dataset_name="obsidian"
                )
                nodes = retriever.retrieve("python async patterns")
    """

    def __init__(
        self,
        fts_manager: FTSChunkManager | None = None,
        similarity_top_k: int = 10,
        dataset_name: str | None = None,
        query_intent: QueryIntent | None = None,
    ) -> None:
        """Initialize the FTS chunk retriever.

        Args:
            fts_manager: Optional FTSChunkManager instance. If None, creates
                a new instance using the ambient session.
            similarity_top_k: Maximum number of results to return. Defaults to 10.
            dataset_name: Optional dataset name filter. If provided, only chunks
                from documents in this dataset will be returned. The filter is
                applied via source_doc_id prefix matching (e.g., "obsidian:").
            query_intent: Optional query intent for BM25 weight routing.
        """
        super().__init__()
        self._fts_manager = fts_manager if fts_manager is not None else FTSChunkManager()
        self._similarity_top_k = similarity_top_k
        self._dataset_name = dataset_name
        self._query_intent = query_intent

    @property
    def similarity_top_k(self) -> int:
        """Get the maximum number of results to return."""
        return self._similarity_top_k

    @similarity_top_k.setter
    def similarity_top_k(self, value: int) -> None:
        """Set the maximum number of results to return."""
        self._similarity_top_k = value

    @property
    def dataset_name(self) -> str | None:
        """Get the dataset name filter."""
        return self._dataset_name

    @dataset_name.setter
    def dataset_name(self, value: str | None) -> None:
        """Set the dataset name filter."""
        self._dataset_name = value

    @property
    def query_intent(self) -> QueryIntent | None:
        """Get the query intent for BM25 weight routing."""
        return self._query_intent

    @query_intent.setter
    def query_intent(self, value: QueryIntent | None) -> None:
        """Set the query intent for BM25 weight routing."""
        self._query_intent = value

    def _retrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
        """Retrieve nodes matching the query using FTS5 search.

        Args:
            query_bundle: LlamaIndex query bundle containing the search query.

        Returns:
            List of NodeWithScore objects sorted by relevance (highest score first).
        """
        query_str = query_bundle.query_str

        # Build source_doc_id prefix from dataset_name
        source_doc_id_prefix: str | None = None
        if self._dataset_name:
            source_doc_id_prefix = f"{self._dataset_name}:"

        # Resolve BM25 weights from intent
        bm25_weights: str | None = None
        if self._query_intent is not None:
            from catalog.core.settings import get_settings
            settings = get_settings().rag
            if self._query_intent == "navigational":
                heading_w = settings.bm25_heading_weight_navigational
            else:
                heading_w = settings.bm25_heading_weight_informational
            bm25_weights = f"0.0, {heading_w}, 1.0, 0.0"

        # Execute FTS search
        fts_results = self._fts_manager.search_with_scores(
            query=query_str,
            limit=self._similarity_top_k,
            source_doc_id_prefix=source_doc_id_prefix,
            bm25_weights=bm25_weights,
        )

        logger.debug(
            f"FTS chunk search '{query_str}' returned {len(fts_results)} results"
        )

        # Convert FTSChunkResult to NodeWithScore
        nodes_with_scores: list[NodeWithScore] = []
        for result in fts_results:
            node = TextNode(
                id_=result.node_id,
                text=result.text,
                metadata={"source_doc_id": result.source_doc_id},
            )
            nodes_with_scores.append(NodeWithScore(node=node, score=result.score))

        return nodes_with_scores
