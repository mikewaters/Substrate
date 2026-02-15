"""catalog.search.hybrid - Weighted RRF hybrid retriever.

Provides a custom RRF retriever with per-query weighting for combining
FTS and vector retrieval results. Uses configurable weights to tune
the contribution of each retriever in the final ranking.

Example usage:
    from catalog.search.hybrid import HybridRetriever
    from catalog.store.database import get_session
    from catalog.store.session_context import use_session

    with get_session() as session:
        with use_session(session):
            factory = HybridRetriever(session)
            retriever = factory.build(dataset_name="obsidian")
            nodes = retriever.retrieve("machine learning concepts")
"""

from collections import defaultdict
from typing import TYPE_CHECKING

from agentlayer.logging import get_logger
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode

from catalog.core.settings import get_settings
from catalog.search.fts_chunk import FTSChunkRetriever
from catalog.search.vector import VectorSearch
from catalog.store.vector import VectorStoreManager

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

__all__ = [
    "HybridRetriever",
    "WeightedRRFRetriever",
]

logger = get_logger(__name__)


class WeightedRRFRetriever(BaseRetriever):
    """Custom RRF retriever with per-query weighting.

    Implements Reciprocal Rank Fusion with configurable weights for each
    sub-retriever. The weighted RRF score for a document is computed as:

        score = sum(weight_i / (k + rank_i + 1))

    where weight_i is the weight for retriever i, k is the RRF constant,
    and rank_i is the 0-based rank of the document in retriever i's results.

    Attributes:
        retrievers: List of sub-retrievers to fuse.
        weights: Weight for each retriever (must match length of retrievers).
        k: RRF constant k (higher values give more weight to lower ranks).
        top_n: Number of results to return after fusion.

    Example:
        # Equal weighting
        retriever = WeightedRRFRetriever(
            retrievers=[fts_retriever, vector_retriever],
            weights=[1.0, 1.0],
            k=60,
            top_n=30,
        )

        # Weight FTS higher
        retriever = WeightedRRFRetriever(
            retrievers=[fts_retriever, vector_retriever],
            weights=[2.0, 1.0],
            k=60,
            top_n=30,
        )
    """

    def __init__(
        self,
        retrievers: list[BaseRetriever],
        weights: list[float],
        k: int = 60,
        top_n: int = 30,
    ) -> None:
        """Initialize the WeightedRRFRetriever.

        Args:
            retrievers: List of sub-retrievers to fuse results from.
            weights: Weight for each retriever. Must have same length as retrievers.
            k: RRF constant k. Higher values give more weight to lower-ranked
                results. Defaults to 60 (standard RRF).
            top_n: Maximum number of fused results to return. Defaults to 30.

        Raises:
            ValueError: If retrievers and weights have different lengths,
                or if any weight is negative.
        """
        super().__init__()
        if len(retrievers) != len(weights):
            raise ValueError(
                f"Number of retrievers ({len(retrievers)}) must match "
                f"number of weights ({len(weights)})"
            )
        if any(w < 0 for w in weights):
            raise ValueError("All weights must be non-negative")

        self._retrievers = retrievers
        self._weights = weights
        self._k = k
        self._top_n = top_n

        logger.debug(
            f"WeightedRRFRetriever initialized: k={k}, top_n={top_n}, "
            f"weights={weights}"
        )

    @property
    def retrievers(self) -> list[BaseRetriever]:
        """Get the list of sub-retrievers."""
        return self._retrievers

    @property
    def weights(self) -> list[float]:
        """Get the weights for each retriever."""
        return self._weights

    @property
    def k(self) -> int:
        """Get the RRF constant k."""
        return self._k

    @property
    def top_n(self) -> int:
        """Get the number of results to return."""
        return self._top_n

    def _retrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
        """Retrieve and fuse results from all sub-retrievers using weighted RRF.

        Runs all sub-retrievers, collects their results, computes weighted RRF
        scores for each unique document, and returns the top_n documents sorted
        by descending RRF score.

        Args:
            query_bundle: LlamaIndex query bundle containing the search query.

        Returns:
            List of NodeWithScore objects sorted by weighted RRF score (highest first).
            Each NodeWithScore.score contains the weighted RRF score.
        """
        # Collect results from all retrievers
        all_results: list[list[NodeWithScore]] = []
        for i, retriever in enumerate(self._retrievers):
            try:
                results = retriever.retrieve(query_bundle)
                all_results.append(results)
                logger.debug(
                    f"Retriever {i} returned {len(results)} results "
                    f"(weight={self._weights[i]})"
                )
            except Exception as e:
                logger.warning(f"Retriever {i} failed: {e}")
                all_results.append([])

        # Compute weighted RRF scores
        # node_id -> (accumulated_score, best_node)
        scores: dict[str, float] = defaultdict(float)
        best_nodes: dict[str, NodeWithScore] = {}

        for retriever_idx, results in enumerate(all_results):
            weight = self._weights[retriever_idx]
            if weight == 0:
                continue

            for rank, node_with_score in enumerate(results):
                node_id = node_with_score.node.node_id
                # Weighted RRF formula: weight / (k + rank + 1)
                rrf_contribution = weight / (self._k + rank + 1)
                scores[node_id] += rrf_contribution

                # Keep the node with the highest original score as the canonical version
                if node_id not in best_nodes or (
                    node_with_score.score is not None
                    and (
                        best_nodes[node_id].score is None
                        or node_with_score.score > best_nodes[node_id].score
                    )
                ):
                    best_nodes[node_id] = node_with_score

        # Sort by RRF score descending and take top_n
        sorted_node_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        top_node_ids = sorted_node_ids[: self._top_n]

        # Build final result list with RRF scores
        fused_results: list[NodeWithScore] = []
        for node_id in top_node_ids:
            original_nws = best_nodes[node_id]
            # Create new NodeWithScore with RRF score
            fused_nws = NodeWithScore(
                node=original_nws.node,
                score=scores[node_id],
            )
            fused_results.append(fused_nws)

        logger.debug(
            f"Weighted RRF fusion: {len(scores)} unique nodes -> "
            f"{len(fused_results)} results"
        )

        return fused_results


class VectorSearchRetriever(BaseRetriever):
    """LlamaIndex retriever wrapper around catalog VectorSearch.

    This keeps hybrid retrieval model-aware by delegating vector retrieval to
    ``VectorSearch``, which resolves query embedding models from stored vector
    payload metadata.
    """

    def __init__(
        self,
        vector_search: VectorSearch,
        similarity_top_k: int,
        dataset_name: str | None = None,
    ) -> None:
        """Initialize the vector retriever wrapper."""
        super().__init__()
        self._vector_search = vector_search
        self._similarity_top_k = similarity_top_k
        self._dataset_name = dataset_name

    def _retrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
        """Retrieve vector matches as LlamaIndex NodeWithScore objects."""
        search_results = self._vector_search.search(
            query=query_bundle.query_str,
            top_k=self._similarity_top_k,
            dataset_name=self._dataset_name,
        )

        nodes_with_scores: list[NodeWithScore] = []
        for result in search_results:
            metadata = dict(result.metadata or {})
            source_doc_id = f"{result.dataset_name}:{result.path}"
            metadata["source_doc_id"] = source_doc_id
            if result.chunk_seq is not None:
                metadata["chunk_seq"] = result.chunk_seq
            if result.chunk_pos is not None:
                metadata["chunk_pos"] = result.chunk_pos

            node_id = metadata.get("node_id")
            if not node_id:
                node_id = source_doc_id

            text = result.snippet.text if result.snippet is not None else ""
            node = TextNode(
                id_=str(node_id),
                text=text,
                metadata=metadata,
            )
            nodes_with_scores.append(
                NodeWithScore(
                    node=node,
                    score=result.score,
                )
            )

        return nodes_with_scores


class HybridRetriever:
    """Factory for building hybrid retrieval pipeline.

    Creates a WeightedRRFRetriever configured with FTS and vector retrievers,
    using settings from get_settings().rag for RRF parameters.

    Attributes:
        session: SQLAlchemy session for database access.
        vector_manager: VectorStoreManager for vector retrieval.

    Example:
        factory = HybridRetriever(session)
        retriever = factory.build(dataset_name="obsidian")
        nodes = retriever.retrieve(QueryBundle("machine learning"))
    """

    def __init__(
        self,
        session: "Session",
        vector_manager: VectorStoreManager | None = None,
    ) -> None:
        """Initialize the HybridRetriever factory.

        Args:
            session: SQLAlchemy session for database access (used by FTS).
            vector_manager: VectorStoreManager for vector retrieval. If None,
                creates a new VectorStoreManager with default settings.
        """
        self._session = session
        self._vector_manager = vector_manager or VectorStoreManager()
        self._settings = get_settings().rag

        logger.debug(
            f"HybridRetriever initialized with rag settings: "
            f"rrf_k={self._settings.rrf_k}, "
            f"original_weight={self._settings.rrf_original_weight}"
        )

    def build(
        self,
        dataset_name: str | None = None,
        fts_top_k: int | None = None,
        vector_top_k: int | None = None,
        fusion_top_k: int | None = None,
    ) -> WeightedRRFRetriever:
        """Build a WeightedRRFRetriever with FTS and vector retrievers.

        Creates FTS and vector retrievers configured for the specified dataset,
        then wraps them in a WeightedRRFRetriever with settings from rag.

        Args:
            dataset_name: Optional dataset name filter. When provided, both
                retrievers filter results to that dataset.
            fts_top_k: Number of results from FTS retriever. If None, uses
                settings.rag.fts_top_k.
            vector_top_k: Number of results from vector retriever. If None,
                uses settings.rag.vector_top_k.
            fusion_top_k: Number of results after RRF fusion. If None, uses
                settings.rag.fusion_top_k.

        Returns:
            WeightedRRFRetriever configured with FTS and vector retrievers.
        """
        # Get top_k values from settings if not provided
        fts_k = fts_top_k if fts_top_k is not None else self._settings.fts_top_k
        vector_k = vector_top_k if vector_top_k is not None else self._settings.vector_top_k
        fusion_k = fusion_top_k if fusion_top_k is not None else self._settings.fusion_top_k

        # Create FTS retriever
        fts_retriever = FTSChunkRetriever(
            similarity_top_k=fts_k,
            dataset_name=dataset_name,
        )

        vector_retriever = VectorSearchRetriever(
            vector_search=VectorSearch(vector_manager=self._vector_manager),
            similarity_top_k=vector_k,
            dataset_name=dataset_name,
        )

        # Create weighted RRF retriever with settings
        # Both retrievers get the original weight since we're not doing query expansion here
        hybrid_retriever = WeightedRRFRetriever(
            retrievers=[fts_retriever, vector_retriever],
            weights=[self._settings.rrf_original_weight, self._settings.rrf_original_weight],
            k=self._settings.rrf_k,
            top_n=fusion_k,
        )

        logger.debug(
            f"Built HybridRetriever: fts_k={fts_k}, vector_k={vector_k}, "
            f"fusion_k={fusion_k}, dataset={dataset_name}"
        )

        return hybrid_retriever
