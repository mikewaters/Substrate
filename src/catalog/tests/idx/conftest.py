"""Shared fixtures for idx tests.

Provides common mocks for embedding models and vector stores to avoid
loading real models during testing.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from llama_index.core.embeddings import BaseEmbedding


class MockEmbedding(BaseEmbedding):
    """Mock embedding model that extends LlamaIndex BaseEmbedding.

    Returns deterministic fake embeddings without loading any ML models.
    Compatible with LlamaIndex's IngestionPipeline transformations.
    """

    embed_dim: int = 384
    _call_count: int = 0

    def __init__(self, embed_dim: int = 384, **kwargs: Any):
        """Initialize with embedding dimension."""
        super().__init__(
            model_name="mock-embedding",
            embed_batch_size=32,
            **kwargs,
        )
        self.embed_dim = embed_dim
        self._call_count = 0

    def _get_text_embedding(self, text: str) -> list[float]:
        """Get embedding for a single text."""
        hash_val = hash(text) % 1000
        return [0.1 + (hash_val / 10000.0)] * self.embed_dim

    def _get_query_embedding(self, query: str) -> list[float]:
        """Get embedding for a query."""
        return self._get_text_embedding(query)

    async def _aget_text_embedding(self, text: str) -> list[float]:
        """Async version of get_text_embedding."""
        return self._get_text_embedding(text)

    async def _aget_query_embedding(self, query: str) -> list[float]:
        """Async version of get_query_embedding."""
        return self._get_query_embedding(query)


@pytest.fixture
def mock_embed_model():
    """Create a mock embedding model that returns fake embeddings."""
    return MockEmbedding(embed_dim=384)


@pytest.fixture
def in_memory_qdrant_vector_store(tmp_path):
    """Create a real QdrantVectorStore with in-memory storage.

    This satisfies Pydantic validation in LlamaIndex's IngestionPipeline.
    """
    import qdrant_client
    from llama_index.vector_stores.qdrant import QdrantVectorStore

    # Use in-memory mode for fast tests
    client = qdrant_client.QdrantClient(location=":memory:")

    # Create collection with correct dimensions
    from qdrant_client.models import Distance, VectorParams
    client.create_collection(
        collection_name="test_collection",
        vectors_config=VectorParams(size=384, distance=Distance.COSINE),
    )

    return QdrantVectorStore(
        client=client,
        collection_name="test_collection",
    )


@pytest.fixture
def mock_vector_store(in_memory_qdrant_vector_store):
    """Provide a real in-memory QdrantVectorStore for tests.

    This is needed because LlamaIndex's IngestionPipeline validates
    that vector_store is an instance of BasePydanticVectorStore.
    """
    return in_memory_qdrant_vector_store


@pytest.fixture
def mock_vector_manager(mock_vector_store, tmp_path):
    """Create a mock VectorStoreManager with real in-memory vector store."""
    mock = MagicMock()
    mock_index = MagicMock()
    mock.load_or_create.return_value = mock_index
    mock.get_vector_store.return_value = mock_vector_store
    mock.delete_by_dataset.return_value = 0
    mock.persist_vector_store.return_value = None
    mock.persist.return_value = None
    mock._persist_dir = tmp_path / "vector_store"
    mock._persist_dir.mkdir(parents=True, exist_ok=True)
    return mock


@pytest.fixture
def patched_embedding(mock_embed_model, mock_vector_manager):
    """Patch embedding and vector store for tests.

    Patches catalog.embedding.get_embed_model and
    catalog.ingest.pipelines.VectorStoreManager to use mocks,
    avoiding loading real models.
    """
    with patch("catalog.embedding.get_embed_model", return_value=mock_embed_model):
        # Patch where VectorStoreManager is imported and used, not where it's defined
        with patch("catalog.ingest.pipelines.VectorStoreManager", return_value=mock_vector_manager):
            with patch("catalog.ingest.pipelines_v2.VectorStoreManager", return_value=mock_vector_manager):
                yield {
                    "embed_model": mock_embed_model,
                    "vector_manager": mock_vector_manager,
                }


@pytest.fixture
def in_memory_qdrant_manager(tmp_path):
    """Create a VectorStoreManager with temporary local Qdrant for integration tests.

    Uses a temporary directory that simulates local storage but is
    cleaned up after the test.
    """
    from catalog.store.vector import VectorStoreManager

    # Use tmp_path to create an isolated Qdrant instance
    vector_dir = tmp_path / "vector_store"
    vector_dir.mkdir(parents=True, exist_ok=True)

    manager = VectorStoreManager(persist_dir=vector_dir)
    return manager
