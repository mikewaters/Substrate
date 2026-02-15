"""catalog.store.vector - Vector store management using Qdrant.

Provides vector storage and retrieval capabilities using Qdrant in local
persistent mode via LlamaIndex's QdrantVectorStore integration.

Example usage:
    from catalog.store.vector import VectorStoreManager

    manager = VectorStoreManager()
    index = manager.load_or_create()
    manager.insert_nodes([node1, node2])
    retriever = manager.get_retriever(similarity_top_k=10)
"""

from pathlib import Path
from functools import lru_cache
from typing import TYPE_CHECKING

import qdrant_client
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, VectorParams
from agentlayer.logging import get_logger
from llama_index.vector_stores.qdrant import QdrantVectorStore

from catalog.core.settings import get_settings

if TYPE_CHECKING:
    from llama_index.core import VectorStoreIndex
    from llama_index.core.embeddings import BaseEmbedding
    from llama_index.core.retrievers import VectorIndexRetriever
    from llama_index.core.schema import TextNode

__all__ = ["VectorStoreManager"]

logger = get_logger(__name__)


@lru_cache(maxsize=8)
def _build_embed_model(
    backend: str,
    model_name: str,
    batch_size: int,
):
    """Build and cache embedding models per process.

    The catalog CLI often creates multiple ``VectorStoreManager`` instances
    during a single run (e.g. comparing fts/vector/hybrid modes). Loading the
    embedding model each time dominates latency, so this cache keeps one model
    instance per unique backend/model/batch configuration in the current
    process. Delegates to ``catalog.embedding.build_embed_model`` so backend
    dispatch and constructor logic live in one place.

    Args:
        backend: Embedding backend name (``mlx`` or ``huggingface``).
        model_name: Embedding model identifier.
        batch_size: Embedding batch size.

    Returns:
        Configured embedding model.
    """
    from catalog.embedding import build_embed_model

    return build_embed_model(backend=backend, model_name=model_name, batch_size=batch_size)


class VectorStoreManager:
    """Manages vector storage using Qdrant in local persistent mode.

    Provides lazy initialization of the Qdrant client, vector store, and index.
    Uses local file-based persistence for the vector database.

    Key features:
    - Auto-creates collection with correct dimensions on first use
    - Qdrant auto-persists data (no manual persist needed)
    - delete_by_dataset uses Qdrant's filter-based deletion

    Attributes:
        persist_dir: Directory path for Qdrant's local storage.
    """

    def __init__(self, persist_dir: Path | None = None) -> None:
        """Initialize the VectorStoreManager.

        Args:
            persist_dir: Directory for Qdrant's local storage.
                If None, uses settings.vector_store_path.
        """
        settings = get_settings()
        self._persist_dir = persist_dir or settings.vector_store_path
        self._embed_settings = settings.embedding
        self._qdrant_settings = settings.qdrant

        # Lazy-initialized components
        self._client: qdrant_client.QdrantClient | None = None
        self._index: "VectorStoreIndex | None" = None
        self._embed_model: "BaseEmbedding | None" = None
        self._vector_store: QdrantVectorStore | None = None

        logger.debug(
            f"VectorStoreManager initialized with persist_dir={self._persist_dir}"
        )

    @property
    def persist_dir(self) -> Path:
        """Get the persistence directory path."""
        return self._persist_dir

    def _get_client(self) -> qdrant_client.QdrantClient:
        """Get or create the Qdrant client (lazy initialization).

        Returns:
            QdrantClient configured for local persistent storage.
        """
        if self._client is None:
            self._persist_dir.mkdir(parents=True, exist_ok=True)
            self._client = qdrant_client.QdrantClient(
                path=str(self._persist_dir)
            )
            logger.debug(f"Qdrant client initialized at {self._persist_dir}")

        return self._client

    def _ensure_collection(self) -> None:
        """Ensure the collection exists with correct configuration.

        Creates the collection if it doesn't exist, with:
        - Vector size from embedding settings
        - Cosine distance metric
        - Keyword index on dataset_name for efficient filtering
        """
        client = self._get_client()
        collection_name = self._qdrant_settings.collection_name

        collections = client.get_collections().collections
        exists = any(c.name == collection_name for c in collections)

        if not exists:
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=self._embed_settings.embedding_dim,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(
                f"Created Qdrant collection: {collection_name} "
                f"(dim={self._embed_settings.embedding_dim})"
            )

            # Create payload index for efficient dataset filtering
            client.create_payload_index(
                collection_name=collection_name,
                field_name="dataset_name",
                field_schema="keyword",
            )
            logger.debug(f"Created payload index on 'dataset_name'")

    def _get_embed_model(self) -> "BaseEmbedding":
        """Get or create the embedding model (lazy initialization).

        Returns the configured embedding model based on settings.embedding.backend:
        - "mlx": MLXEmbedding for Apple Silicon
        - "huggingface": HuggingFaceEmbedding for general use

        Returns:
            BaseEmbedding instance configured from settings.
        """
        if self._embed_model is None:
            self._embed_model = _build_embed_model(
                backend=self._embed_settings.backend,
                model_name=self._embed_settings.model_name,
                batch_size=self._embed_settings.batch_size,
            )

        return self._embed_model

    def load_or_create(self) -> "VectorStoreIndex":
        """Load or create a VectorStoreIndex backed by Qdrant.

        Creates the collection if it doesn't exist, then returns
        a VectorStoreIndex that uses the Qdrant vector store.

        Returns:
            VectorStoreIndex ready for use.
        """
        if self._index is not None:
            return self._index

        from llama_index.core import StorageContext, VectorStoreIndex

        vector_store = self.get_vector_store()
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        self._index = VectorStoreIndex.from_vector_store(
            vector_store=vector_store,
            storage_context=storage_context,
            embed_model=self._get_embed_model(),
        )

        logger.info("VectorStoreIndex created from Qdrant")
        return self._index

    def get_vector_store(self) -> QdrantVectorStore:
        """Get or create the QdrantVectorStore for pipeline integration.

        Returns the underlying QdrantVectorStore instance, creating it if needed.
        This is used to pass the vector store to IngestionPipeline's vector_store
        parameter for native integration.

        Returns:
            QdrantVectorStore instance for pipeline use.
        """
        if self._vector_store is not None:
            return self._vector_store

        self._ensure_collection()
        client = self._get_client()

        self._vector_store = QdrantVectorStore(
            client=client,
            collection_name=self._qdrant_settings.collection_name,
        )
        logger.info("QdrantVectorStore initialized")
        return self._vector_store

    def persist(self) -> None:
        """Persist is a no-op for Qdrant (auto-persisted).

        Qdrant in local mode automatically persists all changes to disk.
        This method exists for API compatibility with the previous SimpleVectorStore.
        """
        logger.debug("Qdrant auto-persists; explicit persist() is no-op")

    def persist_vector_store(self, persist_dir: Path | None = None) -> None:
        """Persist is a no-op for Qdrant (auto-persisted).

        Qdrant in local mode automatically persists all changes to disk.
        This method exists for API compatibility with the previous SimpleVectorStore.

        Args:
            persist_dir: Ignored (Qdrant uses the path from initialization).
        """
        logger.debug("Qdrant auto-persists; explicit persist_vector_store() is no-op")

    def insert_nodes(self, nodes: list["TextNode"]) -> None:
        """Add nodes to the index with automatic embedding generation.

        Nodes will have their embeddings computed if not already present.
        Existing nodes with the same ID will be updated.

        Args:
            nodes: List of TextNode objects to insert.

        Raises:
            RuntimeError: If the index hasn't been loaded or created yet.
        """
        if not nodes:
            logger.debug("No nodes to insert")
            return

        if self._index is None:
            raise RuntimeError(
                "No index loaded. Call load_or_create() first."
            )

        logger.debug(f"Inserting {len(nodes)} nodes into vector store")
        self._index.insert_nodes(nodes)
        logger.info(f"Inserted {len(nodes)} nodes into vector store")

    def delete_nodes(self, node_ids: list[str]) -> None:
        """Delete specific nodes from the index by their IDs.

        Args:
            node_ids: List of node IDs to delete.

        Raises:
            RuntimeError: If the index hasn't been loaded or created yet.
        """
        if not node_ids:
            logger.debug("No node IDs to delete")
            return

        if self._index is None:
            raise RuntimeError(
                "No index loaded. Call load_or_create() first."
            )

        logger.debug(f"Deleting {len(node_ids)} nodes from vector store")
        self._index.delete_nodes(node_ids)
        logger.info(f"Deleted {len(node_ids)} nodes from vector store")

    def delete_ref_doc(self, ref_doc_id: str) -> None:
        """Delete all nodes associated with a reference document.

        This removes all chunks/nodes that were derived from the
        specified source document.

        Args:
            ref_doc_id: Reference document ID (source_doc_id).

        Raises:
            RuntimeError: If the index hasn't been loaded or created yet.
        """
        if self._index is None:
            raise RuntimeError(
                "No index loaded. Call load_or_create() first."
            )

        logger.debug(f"Deleting nodes for ref_doc_id: {ref_doc_id}")
        self._index.delete_ref_doc(ref_doc_id)
        logger.info(f"Deleted nodes for ref_doc_id: {ref_doc_id}")

    def delete_by_dataset(self, dataset_name: str) -> int:
        """Delete all vectors associated with a dataset.

        Uses Qdrant's filter-based deletion to remove all points
        whose dataset_name payload field matches the given value.

        Args:
            dataset_name: Name of the dataset to clear vectors for.

        Returns:
            Number of points deleted.
        """
        client = self._get_client()
        collection_name = self._qdrant_settings.collection_name

        # Check if collection exists
        collections = client.get_collections().collections
        if not any(c.name == collection_name for c in collections):
            logger.debug(f"Collection {collection_name} does not exist, nothing to delete")
            return 0

        # Count points before deletion
        count_filter = Filter(
            must=[
                FieldCondition(
                    key="dataset_name",
                    match=MatchValue(value=dataset_name),
                )
            ]
        )

        count_result = client.count(
            collection_name=collection_name,
            count_filter=count_filter,
            exact=True,
        )
        count = count_result.count

        if count > 0:
            # Delete using filter
            from qdrant_client.models import FilterSelector

            client.delete(
                collection_name=collection_name,
                points_selector=FilterSelector(filter=count_filter),
            )
            logger.info(f"Deleted {count} vectors for dataset '{dataset_name}'")
        else:
            logger.debug(f"No vectors found for dataset '{dataset_name}'")

        return count

    def get_retriever(
        self,
        similarity_top_k: int = 10,
    ) -> "VectorIndexRetriever":
        """Get a retriever for similarity search.

        Args:
            similarity_top_k: Number of most similar nodes to retrieve.

        Returns:
            VectorIndexRetriever configured for the index.

        Raises:
            RuntimeError: If the index hasn't been loaded or created yet.
        """
        if self._index is None:
            raise RuntimeError(
                "No index loaded. Call load_or_create() first."
            )

        logger.debug(f"Creating retriever with similarity_top_k={similarity_top_k}")
        return self._index.as_retriever(similarity_top_k=similarity_top_k)

    def clear(self) -> None:
        """Clear the in-memory caches.

        This forces the index and vector store to be reloaded on next access.
        Does not delete persisted data from Qdrant.
        Note: The client connection is preserved for reuse.
        """
        self._index = None
        self._vector_store = None
        logger.debug("Vector store index cache cleared")

    @property
    def is_loaded(self) -> bool:
        """Check if an index is currently loaded in memory."""
        return self._index is not None
