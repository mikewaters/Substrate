"""catalog.search.postprocessors - RRF postprocessors for RAG v2.

Provides LlamaIndex-compatible postprocessors for hybrid search result refinement:
- TopRankBonusPostprocessor: Add bonus scores to top-ranked results
- KeywordChunkSelector: Select best chunk per document based on keyword hits
- PerDocDedupePostprocessor: Collapse multiple chunks per document
- ScoreNormalizerPostprocessor: Normalize scores to 0-1 range

Example usage:
    from catalog.search.postprocessors import (
        TopRankBonusPostprocessor,
        KeywordChunkSelector,
        PerDocDedupePostprocessor,
        ScoreNormalizerPostprocessor,
    )
    from llama_index.core.schema import NodeWithScore, QueryBundle

    # Chain postprocessors
    nodes = top_rank_bonus.postprocess_nodes(nodes, query)
    nodes = keyword_selector.postprocess_nodes(nodes, query)
    nodes = deduper.postprocess_nodes(nodes, query)
"""

import re
from collections import defaultdict
from typing import Optional

from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.schema import NodeWithScore, QueryBundle
from loguru import logger

from catalog.core.settings import get_settings

__all__ = [
    "KeywordChunkSelector",
    "PerDocDedupePostprocessor",
    "ScoreNormalizerPostprocessor",
    "TopRankBonusPostprocessor",
]


class TopRankBonusPostprocessor(BaseNodePostprocessor):
    """Add bonus scores to top-ranked results after RRF fusion.

    Applies a score bonus to the highest-ranked results to further differentiate
    them from lower-ranked results. This is useful after RRF fusion where scores
    tend to cluster together.

    The rank 1 result receives a larger bonus than ranks 2-3, which receive
    a smaller bonus. Results at rank 4 and below receive no bonus.

    Attributes:
        rank_1_bonus: Score bonus for the rank 1 result.
        rank_2_3_bonus: Score bonus for ranks 2 and 3.
    """

    rank_1_bonus: float = 0.05
    rank_2_3_bonus: float = 0.02

    def __init__(
        self,
        rank_1_bonus: float | None = None,
        rank_2_3_bonus: float | None = None,
    ) -> None:
        """Initialize the TopRankBonusPostprocessor.

        Args:
            rank_1_bonus: Score bonus for rank 1 result. If None, reads from
                settings.rag_v2.rrf_rank1_bonus.
            rank_2_3_bonus: Score bonus for ranks 2-3. If None, reads from
                settings.rag_v2.rrf_rank23_bonus.
        """
        settings = get_settings()
        super().__init__(
            rank_1_bonus=rank_1_bonus
            if rank_1_bonus is not None
            else settings.rag_v2.rrf_rank1_bonus,
            rank_2_3_bonus=rank_2_3_bonus
            if rank_2_3_bonus is not None
            else settings.rag_v2.rrf_rank23_bonus,
        )

    def _postprocess_nodes(
        self,
        nodes: list[NodeWithScore],
        query_bundle: Optional[QueryBundle] = None,
    ) -> list[NodeWithScore]:
        """Apply rank-based bonus scores to nodes.

        Args:
            nodes: List of NodeWithScore objects, assumed to be already sorted
                by score in descending order.
            query_bundle: Optional query bundle (not used).

        Returns:
            List of NodeWithScore with bonus scores applied to top ranks.
        """
        if not nodes:
            return nodes

        result_nodes: list[NodeWithScore] = []
        for i, node_with_score in enumerate(nodes):
            rank = i + 1  # 1-indexed rank
            current_score = node_with_score.score or 0.0

            if rank == 1:
                bonus = self.rank_1_bonus
            elif rank <= 3:
                bonus = self.rank_2_3_bonus
            else:
                bonus = 0.0

            new_score = current_score + bonus

            result_nodes.append(
                NodeWithScore(node=node_with_score.node, score=new_score)
            )

            if bonus > 0:
                logger.debug(
                    f"Rank {rank} bonus: {current_score:.4f} -> {new_score:.4f} (+{bonus})"
                )

        return result_nodes


class KeywordChunkSelector(BaseNodePostprocessor):
    """Select best chunk per document based on keyword hits.

    Groups nodes by their source document and selects the chunk with the most
    query term matches for each document. This helps surface the most relevant
    chunk from multi-chunk documents.

    If multiple chunks have the same number of keyword hits, the one with the
    highest original score is selected.
    """

    def _postprocess_nodes(
        self,
        nodes: list[NodeWithScore],
        query_bundle: Optional[QueryBundle] = None,
    ) -> list[NodeWithScore]:
        """Select best chunk per document based on keyword hits.

        Args:
            nodes: List of NodeWithScore objects to process.
            query_bundle: Query bundle containing the search query.

        Returns:
            List of NodeWithScore with one chunk per source document,
            ordered by the original score of the selected chunk.
        """
        if not nodes or not query_bundle:
            return nodes

        query_str = query_bundle.query_str
        # Extract query terms (alphanumeric tokens, lowercased)
        query_terms = set(re.findall(r"\w+", query_str.lower()))

        if not query_terms:
            return nodes

        # Group nodes by source_doc_id
        doc_chunks: dict[str, list[tuple[NodeWithScore, int]]] = defaultdict(list)

        for node_with_score in nodes:
            source_doc_id = node_with_score.node.metadata.get("source_doc_id", "")
            if not source_doc_id:
                # No source_doc_id, use node ID as fallback
                source_doc_id = node_with_score.node.id_ or ""

            # Count keyword hits in chunk text
            chunk_text = (node_with_score.node.text or "").lower()
            chunk_tokens = set(re.findall(r"\w+", chunk_text))
            hits = len(query_terms & chunk_tokens)

            doc_chunks[source_doc_id].append((node_with_score, hits))

        # Select best chunk per document
        selected_nodes: list[NodeWithScore] = []
        for source_doc_id, chunks in doc_chunks.items():
            # Sort by hits (descending), then by score (descending)
            best_chunk = max(
                chunks, key=lambda x: (x[1], x[0].score or 0.0)
            )
            selected_nodes.append(best_chunk[0])

            if len(chunks) > 1:
                logger.debug(
                    f"Doc {source_doc_id}: selected chunk with {best_chunk[1]} hits "
                    f"(score={best_chunk[0].score:.4f}) from {len(chunks)} chunks"
                )

        # Sort by original score (descending)
        selected_nodes.sort(key=lambda x: x.score or 0.0, reverse=True)

        logger.debug(
            f"KeywordChunkSelector: {len(nodes)} nodes -> {len(selected_nodes)} (1 per doc)"
        )

        return selected_nodes


class PerDocDedupePostprocessor(BaseNodePostprocessor):
    """Collapse multiple chunks per document to best-scoring chunk.

    Groups nodes by their source document and keeps only the highest-scoring
    chunk for each document. This is a simpler alternative to KeywordChunkSelector
    that relies purely on score rather than keyword matching.
    """

    def _postprocess_nodes(
        self,
        nodes: list[NodeWithScore],
        query_bundle: Optional[QueryBundle] = None,
    ) -> list[NodeWithScore]:
        """Keep only the best-scoring chunk per document.

        Args:
            nodes: List of NodeWithScore objects to deduplicate.
            query_bundle: Optional query bundle (not used).

        Returns:
            List of NodeWithScore with one chunk per source document,
            ordered by score descending.
        """
        if not nodes:
            return nodes

        # Track best node per source_doc_id
        best_per_doc: dict[str, NodeWithScore] = {}

        for node_with_score in nodes:
            source_doc_id = node_with_score.node.metadata.get("source_doc_id", "")
            if not source_doc_id:
                # No source_doc_id, use node ID as fallback
                source_doc_id = node_with_score.node.id_ or ""

            current_score = node_with_score.score or 0.0

            if source_doc_id not in best_per_doc:
                best_per_doc[source_doc_id] = node_with_score
            else:
                existing_score = best_per_doc[source_doc_id].score or 0.0
                if current_score > existing_score:
                    best_per_doc[source_doc_id] = node_with_score

        # Sort by score descending
        result_nodes = sorted(
            best_per_doc.values(),
            key=lambda x: x.score or 0.0,
            reverse=True,
        )

        logger.debug(
            f"PerDocDedupePostprocessor: {len(nodes)} nodes -> {len(result_nodes)} unique docs"
        )

        return result_nodes


class ScoreNormalizerPostprocessor(BaseNodePostprocessor):
    """Normalize scores to 0-1 range for fair fusion.

    Different retrievers produce scores on different scales. This postprocessor
    normalizes scores to the 0-1 range using min-max normalization, enabling
    fair comparison and fusion of results from multiple retrievers.

    The retriever_type attribute is stored for debugging purposes to track
    which retriever the scores came from.

    Attributes:
        retriever_type: Identifier for the retriever type (e.g., "bm25", "vector").
    """

    retriever_type: str = "bm25"

    def __init__(self, retriever_type: str = "bm25") -> None:
        """Initialize the ScoreNormalizerPostprocessor.

        Args:
            retriever_type: Identifier for the retriever type, used for
                debugging and logging. Defaults to "bm25".
        """
        super().__init__(retriever_type=retriever_type)

    def _postprocess_nodes(
        self,
        nodes: list[NodeWithScore],
        query_bundle: Optional[QueryBundle] = None,
    ) -> list[NodeWithScore]:
        """Normalize node scores to 0-1 range using min-max normalization.

        Args:
            nodes: List of NodeWithScore objects to normalize.
            query_bundle: Optional query bundle (not used).

        Returns:
            List of NodeWithScore with scores normalized to [0, 1].
            If all scores are the same, all normalized scores will be 1.0.
        """
        if not nodes:
            return nodes

        # Extract scores
        scores = [n.score or 0.0 for n in nodes]
        min_score = min(scores)
        max_score = max(scores)
        score_range = max_score - min_score

        # Handle edge case where all scores are the same
        if score_range == 0:
            logger.debug(
                f"ScoreNormalizer ({self.retriever_type}): all scores equal "
                f"({min_score:.4f}), setting all to 1.0"
            )
            return [
                NodeWithScore(node=n.node, score=1.0)
                for n in nodes
            ]

        # Apply min-max normalization
        result_nodes: list[NodeWithScore] = []
        for node_with_score in nodes:
            old_score = node_with_score.score or 0.0
            new_score = (old_score - min_score) / score_range
            result_nodes.append(
                NodeWithScore(node=node_with_score.node, score=new_score)
            )

        logger.debug(
            f"ScoreNormalizer ({self.retriever_type}): normalized {len(nodes)} nodes "
            f"from [{min_score:.4f}, {max_score:.4f}] to [0, 1]"
        )

        return result_nodes
