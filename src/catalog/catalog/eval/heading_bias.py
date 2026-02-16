"""catalog.eval.heading_bias - Heading bias metrics for search evaluation.

Computes metrics that detect heading-dominated retrieval results,
where heading-heavy chunks outrank body-content chunks due to BM25
keyword density in heading text.

Example usage:
    from catalog.eval.heading_bias import compute_heading_bias_metrics
    
    metrics = compute_heading_bias_metrics(search_results, k=10)
    assert metrics.heading_only_hit_rate < 0.20
"""

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from agentlayer.logging import get_logger

if TYPE_CHECKING:
    from llama_index.core.schema import NodeWithScore

__all__ = [
    "HEADING_BIAS_THRESHOLDS",
    "HeadingBiasMetrics",
    "compute_heading_bias_metrics",
]

logger = get_logger(__name__)

# Maximum acceptable rates for heading bias indicators
HEADING_BIAS_THRESHOLDS: dict[str, float] = {
    "heading_only_hit_rate": 0.20,
    "duplicate_doc_rate": 0.30,
    "heading_dominance_rate": 0.15,
}


@dataclass
class HeadingBiasMetrics:
    """Heading bias metrics computed from search results.

    Attributes:
        heading_only_hit_rate: Fraction of top-k results where body_text is empty.
        duplicate_doc_rate: Fraction of top-k results that are duplicates
            (same source_doc_id as another result).
        heading_dominance_rate: Fraction of multi-chunk docs where the
            highest-ranked chunk has empty body_text.
        k: The k value used for evaluation.
    """

    heading_only_hit_rate: float
    duplicate_doc_rate: float
    heading_dominance_rate: float
    k: int


def compute_heading_bias_metrics(
    nodes: list["NodeWithScore"],
    k: int = 10,
) -> HeadingBiasMetrics:
    """Compute heading bias metrics from search result nodes.

    Args:
        nodes: List of NodeWithScore objects from search results.
        k: Number of top results to evaluate.

    Returns:
        HeadingBiasMetrics with computed rates.
    """
    top_k = nodes[:k]

    if not top_k:
        return HeadingBiasMetrics(
            heading_only_hit_rate=0.0,
            duplicate_doc_rate=0.0,
            heading_dominance_rate=0.0,
            k=k,
        )

    n = len(top_k)

    # 1. heading_only_hit_rate: fraction with empty body_text
    heading_only_count = sum(
        1
        for nws in top_k
        if not nws.node.metadata.get("body_text", "").strip()
    )
    heading_only_hit_rate = heading_only_count / n

    # 2. duplicate_doc_rate: fraction of results that share a source_doc_id
    doc_ids = [nws.node.metadata.get("source_doc_id", "") for nws in top_k]
    doc_counts = Counter(doc_ids)
    # Count entries beyond the first occurrence of each doc
    duplicate_entries = sum(count - 1 for count in doc_counts.values() if count > 1)
    duplicate_doc_rate = duplicate_entries / n

    # 3. heading_dominance_rate: among docs with multiple chunks,
    #    fraction where the highest-ranked chunk has empty body_text
    multi_chunk_docs: dict[str, list[int]] = {}
    for i, nws in enumerate(top_k):
        doc_id = nws.node.metadata.get("source_doc_id", "")
        if doc_counts[doc_id] > 1:
            if doc_id not in multi_chunk_docs:
                multi_chunk_docs[doc_id] = []
            multi_chunk_docs[doc_id].append(i)

    if multi_chunk_docs:
        heading_dominant_count = 0
        for doc_id, indices in multi_chunk_docs.items():
            # Highest-ranked = lowest index (results are sorted by rank)
            best_idx = min(indices)
            best_node = top_k[best_idx]
            if not best_node.node.metadata.get("body_text", "").strip():
                heading_dominant_count += 1
        heading_dominance_rate = heading_dominant_count / len(multi_chunk_docs)
    else:
        heading_dominance_rate = 0.0

    logger.debug(
        f"Heading bias metrics @{k}: "
        f"heading_only={heading_only_hit_rate:.2f}, "
        f"duplicate_doc={duplicate_doc_rate:.2f}, "
        f"heading_dominance={heading_dominance_rate:.2f}"
    )

    return HeadingBiasMetrics(
        heading_only_hit_rate=heading_only_hit_rate,
        duplicate_doc_rate=duplicate_doc_rate,
        heading_dominance_rate=heading_dominance_rate,
        k=k,
    )
