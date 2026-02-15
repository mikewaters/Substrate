"""catalog.search.vector - Vector similarity search implementation.

Provides vector search using VectorStoreManager semantic query APIs with text
lookup from SQLite. Supports optional dataset filtering via metadata.

Example usage:
    from catalog.search.vector import VectorSearch
    from catalog.store.vector import VectorStoreManager

    vector_search = VectorSearch()
    results = vector_search.search("machine learning concepts", top_k=10)

    # With dataset filtering
    results = vector_search.search(
        "project notes",
        top_k=5,
        dataset_name="obsidian"
    )
"""

from typing import TYPE_CHECKING

from agentlayer.logging import get_logger

from catalog.search.formatting import build_snippet
from catalog.search.models import SearchResult, SnippetResult
from catalog.store.vector import VectorStoreManager

if TYPE_CHECKING:
    from llama_index.vector_stores.qdrant import QdrantVectorStore

__all__ = ["VectorSearch"]

logger = get_logger(__name__)


def _build_snippet_result(chunk_text: str | None, doc_path: str) -> SnippetResult | None:
    """Build a SnippetResult from chunk text, or None if empty."""
    if not chunk_text:
        return None
    s = build_snippet(chunk_text, doc_path)
    return SnippetResult(text=s.text, start_line=s.start_line, end_line=s.end_line, header=s.header)


class VectorSearch:
    """Vector similarity search using direct QdrantVectorStore queries.

    Delegates semantic retrieval to VectorStoreManager and looks up chunk text
    from SQLite. This approach works regardless of LlamaIndex's docstore state.

    Attributes:
        _vector_manager: VectorStoreManager instance for vector store access.
        _vector_store: Cached QdrantVectorStore, loaded lazily.

    Example:
        vector_search = VectorSearch()

        # Basic search
        results = vector_search.search("python tutorials")

        # Search within a specific dataset
        results = vector_search.search(
            "meeting notes",
            top_k=20,
            dataset_name="obsidian"
        )
    """

    def __init__(
        self,
        vector_manager: VectorStoreManager | None = None,
    ) -> None:
        """Initialize the VectorSearch.

        Args:
            vector_manager: VectorStoreManager instance for vector store access.
                If None, creates a new VectorStoreManager with default settings.
        """
        self._vector_manager = vector_manager or VectorStoreManager()
        self._vector_store: "QdrantVectorStore | None" = None

    def _ensure_vector_store(self) -> "QdrantVectorStore":
        """Ensure the vector store is loaded.

        Returns:
            QdrantVectorStore ready for queries.
        """
        if self._vector_store is None:
            logger.debug("Lazy-loading vector store")
            self._vector_store = self._vector_manager.get_vector_store()
            logger.info("Vector store loaded for search")
        return self._vector_store

    def _lookup_chunk_text(self, chunk_ids: list[str]) -> dict[str, str]:
        """Look up chunk text from SQLite FTS table.

        Args:
            chunk_ids: List of chunk IDs to look up.

        Returns:
            Dict mapping chunk_id to text content.
        """
        if not chunk_ids:
            return {}

        from sqlalchemy import text

        from catalog.store.database import get_engine

        engine = get_engine()
        # c0 = chunk_id, c1 = text
        # Use named parameters for SQLAlchemy
        placeholders = ",".join([f":id{i}" for i in range(len(chunk_ids))])
        params = {f"id{i}": cid for i, cid in enumerate(chunk_ids)}
        query = text(f"SELECT c0, c1 FROM chunks_fts_content WHERE c0 IN ({placeholders})")

        with engine.connect() as conn:
            result = conn.execute(query, params)
            return {row[0]: row[1] for row in result}

    def search(
        self,
        query: str,
        top_k: int = 10,
        dataset_name: str | None = None,
    ) -> list[SearchResult]:
        """Search vector store for similar documents.

        Performs semantic similarity search using the embedded query.
        Results include the similarity score in scores["vector"].

        Args:
            query: The search query string.
            top_k: Maximum number of results to return. Defaults to 10.
            dataset_name: Optional dataset name to filter results.
                When provided, only returns results from that dataset.
                Filters by matching source_doc_id prefix.

        Returns:
            List of SearchResult objects ordered by similarity (highest first).
            Each result includes:
            - path: Document path within the dataset
            - dataset_name: Source dataset name
            - score: Vector similarity score
            - chunk_text: The matched chunk text
            - chunk_seq: Chunk sequence number (if available)
            - chunk_pos: Byte position in document (if available)
            - metadata: Document metadata
            - scores: Dict with "vector" key containing similarity score
        """
        self._ensure_vector_store()
        hits = self._vector_manager.semantic_query(
            query=query,
            top_k=top_k,
            dataset_name=dataset_name
        )

        if not hits:
            logger.debug(f"Vector search '{query[:50]}...' returned 0 results")
            return []

        chunk_ids = [hit.node_id for hit in hits]
        chunk_texts = self._lookup_chunk_text(chunk_ids)

        results = []
        for hit in hits:
            node_id = hit.node_id
            score = hit.score
            metadata = hit.metadata or {}
            source_doc_id = metadata.get("source_doc_id", "")
            if ":" in source_doc_id:
                ds_name, path = source_doc_id.split(":", 1)
            else:
                ds_name = metadata.get("dataset_name", "")
                path = metadata.get("relative_path", "")

            chunk_text = chunk_texts.get(node_id, "")
            chunk_seq = metadata.get("chunk_seq")
            chunk_pos = metadata.get("chunk_pos")

            result_metadata = {
                k: v
                for k, v in metadata.items()
                if k
                not in (
                    "source_doc_id",
                    "chunk_seq",
                    "chunk_pos",
                    "doc_id",
                    "_node_type",
                    "document_id",
                    "ref_doc_id",
                    "dataset_name",
                )
            }
            result_metadata["node_id"] = node_id

            snippet = _build_snippet_result(chunk_text, path)
            results.append(
                SearchResult(
                    path=path,
                    dataset_name=ds_name,
                    score=score,
                    snippet=snippet,
                    chunk_seq=chunk_seq,
                    chunk_pos=chunk_pos,
                    metadata=result_metadata,
                    scores={"vector": score},
                )
            )

        logger.debug(
            f"Vector search '{query[:50]}...' returned {len(results)} results"
        )
        return results
