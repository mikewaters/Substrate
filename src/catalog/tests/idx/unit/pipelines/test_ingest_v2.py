"""Tests for catalog.ingest.pipelines_v2 module."""

import shutil
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import sessionmaker

from catalog.core.settings import get_settings
from catalog.ingest.pipelines_v2 import DatasetIngestPipelineV2
from catalog.ingest.directory import SourceDirectoryConfig
from catalog.store.database import Base, create_engine_for_path
from catalog.store.fts import FTSManager, create_fts_table
from catalog.store.fts_chunk import create_chunks_fts_table
from catalog.store.repositories import DatasetRepository, DocumentRepository
from catalog.store.vector import VectorStoreManager
from catalog.transform import EmbeddingPrefixTransform, ResilientSplitter


def _clear_pipeline_cache(dataset_names: list[str]) -> None:
    """Clear LlamaIndex pipeline cache for specific datasets."""
    settings = get_settings()
    pipeline_dir = settings.cache_path / "pipeline_storage"
    for name in dataset_names:
        cache_path = pipeline_dir / name
        if cache_path.exists():
            shutil.rmtree(cache_path)


class TestDatasetIngestPipelineV2:
    """Tests for DatasetIngestPipelineV2 class."""

    @pytest.fixture(autouse=True)
    def clear_cache(self) -> None:
        """Clear pipeline cache before and after each test."""
        _clear_pipeline_cache(["test-docs-v2", "test-vault-v2", "my-dataset-v2"])
        yield
        _clear_pipeline_cache(["test-docs-v2", "test-vault-v2", "my-dataset-v2"])

    @pytest.fixture(autouse=True)
    def use_mock_embedding(self, patched_embedding) -> None:
        """Use mock embedding model for all tests."""
        yield

    @pytest.fixture
    def test_db(self, tmp_path: Path):
        """Create a test database and patch get_session."""
        db_path = tmp_path / "test.db"
        engine = create_engine_for_path(db_path)
        Base.metadata.create_all(engine)
        create_fts_table(engine)
        create_chunks_fts_table(engine)

        factory = sessionmaker(bind=engine, expire_on_commit=False)

        @contextmanager
        def get_test_session():
            session = factory()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        with patch("catalog.ingest.pipelines_v2.get_session", get_test_session):
            yield get_test_session

    @pytest.fixture
    def db_session(self, test_db):
        """Create a test database session for verification."""
        with test_db() as session:
            yield session

    @pytest.fixture
    def sample_directory(self, tmp_path: Path) -> Path:
        """Create a sample directory with test files."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        # Create markdown files with titles in frontmatter
        (docs_dir / "readme.md").write_text(
            "---\ntitle: Readme\n---\n# Readme\n\nThis is a test document."
        )
        (docs_dir / "notes.md").write_text(
            "---\ntitle: Notes\n---\n# Notes\n\nSome notes here."
        )

        subdir = docs_dir / "subdir"
        subdir.mkdir()
        (subdir / "deep.md").write_text(
            "---\ntitle: Deep File\n---\n# Deep\n\nNested file content."
        )

        return docs_dir

    def test_v2_pipeline_initialization(self) -> None:
        """V2 pipeline can be initialized with defaults."""
        pipeline = DatasetIngestPipelineV2()
        assert pipeline.ingest_config is None
        assert pipeline.resilient_embedding is True

    def test_v2_pipeline_uses_rag_v2_settings(self) -> None:
        """V2 pipeline reads settings from RAGv2Settings."""
        pipeline = DatasetIngestPipelineV2()
        settings = pipeline._settings

        # These should match defaults from RAGv2Settings
        assert settings.chunk_size == 800
        assert settings.chunk_overlap == 120
        assert settings.chunk_fallback_enabled is True
        assert settings.embed_prefix_doc == "title: {title} | text: "

    def test_v2_pipeline_requires_config_for_ingest(self) -> None:
        """V2 pipeline raises ValueError if ingest_config not set."""
        pipeline = DatasetIngestPipelineV2()
        with pytest.raises(ValueError, match="ingest_config is required"):
            pipeline.ingest()

    def test_v2_ingest_creates_documents(
        self, test_db, db_session, sample_directory: Path
    ) -> None:
        """V2 pipeline creates documents in the database."""
        config = SourceDirectoryConfig(
            source_path=sample_directory,
            dataset_name="test-docs-v2",
        )
        pipeline = DatasetIngestPipelineV2(ingest_config=config)
        result = pipeline.ingest()

        assert result.documents_created == 3
        assert result.dataset_name == "test-docs-v2"

        # Verify documents in database
        doc_repo = DocumentRepository(db_session)
        docs = doc_repo.list_by_parent(result.dataset_id)
        assert len(docs) == 3

    def test_v2_build_pipeline_uses_resilient_splitter(
        self, test_db, sample_directory: Path
    ) -> None:
        """V2 pipeline uses ResilientSplitter transform."""
        config = SourceDirectoryConfig(
            source_path=sample_directory,
            dataset_name="test-docs-v2",
        )
        pipeline = DatasetIngestPipelineV2(ingest_config=config)

        # Use real VectorStoreManager but with test path
        vector_manager = VectorStoreManager()

        ingestion_pipeline = pipeline.build_pipeline(
            dataset_id=1,
            dataset_name="test-docs-v2",
            vector_manager=vector_manager,
            source_transforms=([], []),
        )

        # Check that ResilientSplitter is in transformations
        splitter_found = any(
            isinstance(t, ResilientSplitter)
            for t in ingestion_pipeline.transformations
        )
        assert splitter_found, "ResilientSplitter not found in transformations"

    def test_v2_build_pipeline_uses_embedding_prefix(
        self, test_db, sample_directory: Path
    ) -> None:
        """V2 pipeline uses EmbeddingPrefixTransform."""
        config = SourceDirectoryConfig(
            source_path=sample_directory,
            dataset_name="test-docs-v2",
        )
        pipeline = DatasetIngestPipelineV2(ingest_config=config)

        vector_manager = VectorStoreManager()

        ingestion_pipeline = pipeline.build_pipeline(
            dataset_id=1,
            dataset_name="test-docs-v2",
            vector_manager=vector_manager,
            source_transforms=([], []),
        )

        # Check that EmbeddingPrefixTransform is in transformations
        prefix_found = any(
            isinstance(t, EmbeddingPrefixTransform)
            for t in ingestion_pipeline.transformations
        )
        assert prefix_found, "EmbeddingPrefixTransform not found in transformations"

    def test_v2_ingest_dataset_method(
        self, test_db, db_session, sample_directory: Path
    ) -> None:
        """V2 ingest_dataset() method works correctly."""
        config = SourceDirectoryConfig(
            source_path=sample_directory,
            dataset_name="test-docs-v2",
        )
        pipeline = DatasetIngestPipelineV2()
        result = pipeline.ingest_dataset(config)

        assert result.documents_created == 3
        assert result.dataset_name == "test-docs-v2"

    def test_v2_respects_custom_embed_model(
        self, test_db, sample_directory: Path
    ) -> None:
        """V2 pipeline uses provided embed_model."""
        mock_embed = MagicMock()
        mock_embed.return_value = [[0.1] * 384]

        config = SourceDirectoryConfig(
            source_path=sample_directory,
            dataset_name="test-docs-v2",
        )
        pipeline = DatasetIngestPipelineV2(
            ingest_config=config,
            embed_model=mock_embed,
        )

        # Should use provided model
        assert pipeline._get_embed_model() is mock_embed


class TestV2PipelineResilientBehavior:
    """Tests for resilient behavior in V2 pipeline."""

    @pytest.fixture(autouse=True)
    def clear_cache(self) -> None:
        """Clear pipeline cache."""
        _clear_pipeline_cache(["resilient-test"])
        yield
        _clear_pipeline_cache(["resilient-test"])

    def test_resilient_embedding_enabled_by_default(self) -> None:
        """V2 pipeline has resilient_embedding enabled by default."""
        pipeline = DatasetIngestPipelineV2()
        assert pipeline.resilient_embedding is True

    def test_resilient_embedding_can_be_disabled(self) -> None:
        """V2 pipeline allows disabling resilient embedding."""
        pipeline = DatasetIngestPipelineV2(resilient_embedding=False)
        assert pipeline.resilient_embedding is False

    def test_get_embed_model_uses_resilient_flag(self) -> None:
        """_get_embed_model() passes resilient flag to factory."""
        with patch("catalog.ingest.pipelines_v2.get_embed_model") as mock_factory:
            mock_factory.return_value = MagicMock()

            pipeline = DatasetIngestPipelineV2(resilient_embedding=True)
            pipeline._get_embed_model()
            mock_factory.assert_called_once_with(resilient=True)

            mock_factory.reset_mock()

            pipeline2 = DatasetIngestPipelineV2(resilient_embedding=False)
            pipeline2._get_embed_model()
            mock_factory.assert_called_once_with(resilient=False)
