"""Tests for ResilientEmbedding wrapper."""

import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from llama_index.core.embeddings import BaseEmbedding
from loguru import logger


class MockEmbedding(BaseEmbedding):
    """Mock embedding model for testing."""

    model_name: str = "mock-model"
    _embedding_dim: int = 384

    def __init__(self, embedding_dim: int = 384, **kwargs):
        super().__init__(**kwargs)
        self._embedding_dim = embedding_dim

    @classmethod
    def class_name(cls) -> str:
        return "MockEmbedding"

    def _get_text_embedding(self, text: str) -> list[float]:
        return [0.1] * self._embedding_dim

    def _get_query_embedding(self, query: str) -> list[float]:
        return [0.2] * self._embedding_dim

    def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * self._embedding_dim for _ in texts]

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return self._get_query_embedding(query)

    async def _aget_text_embedding(self, text: str) -> list[float]:
        return self._get_text_embedding(text)

    async def _aget_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        return self._get_text_embeddings(texts)


class FailingBatchEmbedding(MockEmbedding):
    """Mock embedding that fails on batch but succeeds on single."""

    def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("Batch embedding failed")

    async def _aget_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("Async batch embedding failed")


class TestResilientEmbedding:
    """Tests for ResilientEmbedding class."""

    def test_init(self):
        """Test initialization with wrapped model."""
        from catalog.embedding.resilient import ResilientEmbedding

        base_model = MockEmbedding()
        resilient = ResilientEmbedding(embed_model=base_model, batch_size=16)

        assert resilient.model_name == "resilient:mock-model"
        assert resilient._batch_size == 16
        assert resilient._embed_model is base_model

    def test_class_name(self):
        """Test class name for serialization."""
        from catalog.embedding.resilient import ResilientEmbedding

        assert ResilientEmbedding.class_name() == "ResilientEmbedding"

    def test_single_text_embedding(self):
        """Test single text embedding delegates to wrapped model."""
        from catalog.embedding.resilient import ResilientEmbedding

        base_model = MockEmbedding()
        resilient = ResilientEmbedding(embed_model=base_model)

        embedding = resilient._get_text_embedding("test text")

        assert len(embedding) == 384
        assert all(x == 0.1 for x in embedding)

    def test_query_embedding(self):
        """Test query embedding delegates to wrapped model."""
        from catalog.embedding.resilient import ResilientEmbedding

        base_model = MockEmbedding()
        resilient = ResilientEmbedding(embed_model=base_model)

        embedding = resilient._get_query_embedding("test query")

        assert len(embedding) == 384
        assert all(x == 0.2 for x in embedding)

    def test_batch_embedding_success(self):
        """Test batch embedding works when wrapped model succeeds."""
        from catalog.embedding.resilient import ResilientEmbedding

        base_model = MockEmbedding()
        resilient = ResilientEmbedding(embed_model=base_model)

        texts = ["text1", "text2", "text3"]
        embeddings = resilient._get_text_embeddings(texts)

        assert len(embeddings) == 3
        for emb in embeddings:
            assert len(emb) == 384
            assert all(x == 0.1 for x in emb)

    def test_batch_embedding_empty_list(self):
        """Test batch embedding with empty list."""
        from catalog.embedding.resilient import ResilientEmbedding

        base_model = MockEmbedding()
        resilient = ResilientEmbedding(embed_model=base_model)

        embeddings = resilient._get_text_embeddings([])

        assert embeddings == []

    def test_batch_embedding_fallback(self):
        """Test fallback to single-item embedding on batch failure."""
        from catalog.embedding.resilient import ResilientEmbedding

        base_model = FailingBatchEmbedding()
        resilient = ResilientEmbedding(embed_model=base_model)

        texts = ["text1", "text2"]
        embeddings = resilient._get_text_embeddings(texts)

        # Should fall back to individual embeddings
        assert len(embeddings) == 2
        for emb in embeddings:
            assert len(emb) == 384

    def test_batch_embedding_fallback_logs_warning(self):
        """Test that fallback to single-item logs a warning."""
        from catalog.embedding.resilient import ResilientEmbedding

        base_model = FailingBatchEmbedding()
        resilient = ResilientEmbedding(embed_model=base_model)

        # Capture loguru output
        log_output = StringIO()
        handler_id = logger.add(log_output, format="{message}", level="WARNING")

        try:
            texts = ["text1", "text2"]
            resilient._get_text_embeddings(texts)

            # Check that warning was logged
            log_contents = log_output.getvalue()
            assert "falling back to individual embedding" in log_contents
        finally:
            logger.remove(handler_id)


class TestResilientEmbeddingAsync:
    """Async tests for ResilientEmbedding class."""

    @pytest.mark.asyncio
    async def test_async_query_embedding(self):
        """Test async query embedding delegates to wrapped model."""
        from catalog.embedding.resilient import ResilientEmbedding

        base_model = MockEmbedding()
        resilient = ResilientEmbedding(embed_model=base_model)

        embedding = await resilient._aget_query_embedding("test query")

        assert len(embedding) == 384
        assert all(x == 0.2 for x in embedding)

    @pytest.mark.asyncio
    async def test_async_text_embedding(self):
        """Test async text embedding delegates to wrapped model."""
        from catalog.embedding.resilient import ResilientEmbedding

        base_model = MockEmbedding()
        resilient = ResilientEmbedding(embed_model=base_model)

        embedding = await resilient._aget_text_embedding("test text")

        assert len(embedding) == 384
        assert all(x == 0.1 for x in embedding)

    @pytest.mark.asyncio
    async def test_async_batch_embedding_success(self):
        """Test async batch embedding works when wrapped model succeeds."""
        from catalog.embedding.resilient import ResilientEmbedding

        base_model = MockEmbedding()
        resilient = ResilientEmbedding(embed_model=base_model)

        texts = ["text1", "text2", "text3"]
        embeddings = await resilient._aget_text_embeddings(texts)

        assert len(embeddings) == 3
        for emb in embeddings:
            assert len(emb) == 384

    @pytest.mark.asyncio
    async def test_async_batch_embedding_empty_list(self):
        """Test async batch embedding with empty list."""
        from catalog.embedding.resilient import ResilientEmbedding

        base_model = MockEmbedding()
        resilient = ResilientEmbedding(embed_model=base_model)

        embeddings = await resilient._aget_text_embeddings([])

        assert embeddings == []

    @pytest.mark.asyncio
    async def test_async_batch_embedding_fallback(self):
        """Test async fallback to single-item embedding on batch failure."""
        from catalog.embedding.resilient import ResilientEmbedding

        base_model = FailingBatchEmbedding()
        resilient = ResilientEmbedding(embed_model=base_model)

        texts = ["text1", "text2"]
        embeddings = await resilient._aget_text_embeddings(texts)

        # Should fall back to individual embeddings
        assert len(embeddings) == 2
        for emb in embeddings:
            assert len(emb) == 384


class TestGetEmbedModelResilient:
    """Tests for get_embed_model with resilient parameter."""

    def test_get_embed_model_not_resilient(self):
        """Test get_embed_model returns unwrapped model when resilient=False."""
        from catalog.embedding.resilient import ResilientEmbedding

        mock_model = MockEmbedding()

        with patch("catalog.embedding.get_settings") as mock_settings, patch(
            "catalog.embedding.MLXEmbedding", return_value=mock_model
        ):
            mock_settings.return_value.embedding.backend = "mlx"
            mock_settings.return_value.embedding.model_name = "test-model"
            mock_settings.return_value.embedding.batch_size = 32
            mock_settings.return_value.rag.embed_batch_size = 16

            # Import after patching
            from catalog.embedding import get_embed_model

            model = get_embed_model(resilient=False)

        assert model is mock_model
        assert not isinstance(model, ResilientEmbedding)

    def test_get_embed_model_resilient(self):
        """Test get_embed_model returns wrapped model when resilient=True."""
        from catalog.embedding.resilient import ResilientEmbedding

        mock_model = MockEmbedding()

        with patch("catalog.embedding.get_settings") as mock_settings, patch(
            "catalog.embedding.MLXEmbedding", return_value=mock_model
        ):
            mock_settings.return_value.embedding.backend = "mlx"
            mock_settings.return_value.embedding.model_name = "test-model"
            mock_settings.return_value.embedding.batch_size = 32
            mock_settings.return_value.rag.embed_batch_size = 16

            # Import after patching
            from catalog.embedding import get_embed_model

            model = get_embed_model(resilient=True)

        assert isinstance(model, ResilientEmbedding)
        assert model._embed_model is mock_model
        assert model._batch_size == 16

    def test_get_embed_model_default_not_resilient(self):
        """Test get_embed_model defaults to resilient=False."""
        from catalog.embedding.resilient import ResilientEmbedding

        mock_model = MockEmbedding()

        with patch("catalog.embedding.get_settings") as mock_settings, patch(
            "catalog.embedding.MLXEmbedding", return_value=mock_model
        ):
            mock_settings.return_value.embedding.backend = "mlx"
            mock_settings.return_value.embedding.model_name = "test-model"
            mock_settings.return_value.embedding.batch_size = 32
            mock_settings.return_value.rag.embed_batch_size = 16

            # Import after patching
            from catalog.embedding import get_embed_model

            model = get_embed_model()

        assert model is mock_model
        assert not isinstance(model, ResilientEmbedding)
