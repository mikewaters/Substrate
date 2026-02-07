"""Tests for incremental ingestion support.

Tests the incremental flag resolution, docstore strategy downgrade,
deletion sync skip, and last_ingested_at stamping.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from llama_index.core.ingestion import DocstoreStrategy
from sqlalchemy.orm import sessionmaker

from catalog.ingest.job import SourceConfig
from catalog.ingest.pipelines_v2 import DatasetIngestPipelineV2
from catalog.ingest.directory import SourceDirectoryConfig
from catalog.store.database import Base, create_engine_for_path
from catalog.store.fts import create_fts_table
from catalog.store.fts_chunk import create_chunks_fts_table
from catalog.store.repositories import DatasetRepository, DocumentRepository
from catalog.store.vector import VectorStoreManager


class TestIncrementalConfig:
    """Tests for incremental flag on config models."""

    def test_source_config_incremental_defaults_false(self, tmp_path: Path):
        """incremental defaults to False on SourceConfig."""
        cfg = SourceConfig(type="obsidian", source_path=tmp_path)
        assert cfg.incremental is False

    def test_source_config_incremental_true(self, tmp_path: Path):
        """incremental can be set to True on SourceConfig."""
        cfg = SourceConfig(
            type="obsidian", source_path=tmp_path, incremental=True,
        )
        assert cfg.incremental is True

    def test_incremental_wired_through_obsidian_factory(self, tmp_path: Path):
        """incremental passes through the obsidian factory."""
        from catalog.ingest.sources import create_ingest_config
        from catalog.integrations.obsidian.source import SourceObsidianConfig

        vault_dir = tmp_path / "vault"
        vault_dir.mkdir()
        (vault_dir / ".obsidian").mkdir()

        cfg = SourceConfig(
            type="obsidian",
            source_path=vault_dir,
            dataset_name="test",
            incremental=True,
        )
        config = create_ingest_config(cfg)
        assert isinstance(config, SourceObsidianConfig)
        assert config.incremental is True

    def test_incremental_wired_through_heptabase_factory(self, tmp_path: Path):
        """incremental passes through the heptabase factory."""
        from catalog.ingest.sources import create_ingest_config
        from catalog.integrations.heptabase.source import SourceHeptabaseConfig

        (tmp_path / "note.md").write_text("# Test")

        cfg = SourceConfig(
            type="heptabase",
            source_path=tmp_path,
            dataset_name="test",
            incremental=True,
        )
        config = create_ingest_config(cfg)
        assert isinstance(config, SourceHeptabaseConfig)
        assert config.incremental is True


class TestBuildPipelineDocstoreStrategy:
    """Tests for docstore strategy selection in build_pipeline."""

    @pytest.fixture(autouse=True)
    def use_mock_embedding(self, patched_embedding) -> None:
        """Use mock embedding model for all tests."""
        yield

    def test_full_run_uses_upserts_and_delete(self):
        """Non-incremental build uses UPSERTS_AND_DELETE strategy."""
        pipeline = DatasetIngestPipelineV2()
        vector_manager = VectorStoreManager()

        ingestion_pipeline = pipeline.build_pipeline(
            dataset_id=1,
            dataset_name="test",
            vector_manager=vector_manager,
            source_transforms=([], []),
            incremental=False,
        )
        assert ingestion_pipeline.docstore_strategy == DocstoreStrategy.UPSERTS_AND_DELETE

    def test_incremental_uses_upserts(self):
        """Incremental build uses UPSERTS strategy."""
        pipeline = DatasetIngestPipelineV2()
        vector_manager = VectorStoreManager()

        ingestion_pipeline = pipeline.build_pipeline(
            dataset_id=1,
            dataset_name="test",
            vector_manager=vector_manager,
            source_transforms=([], []),
            incremental=True,
        )
        assert ingestion_pipeline.docstore_strategy == DocstoreStrategy.UPSERTS


class TestIncrementalIngestion:
    """Tests for incremental resolution, deletion sync, and timestamp stamping."""

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
    def sample_directory(self, tmp_path: Path) -> Path:
        """Create a sample directory with test files."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "a.md").write_text("# A\n\nContent A.")
        (docs_dir / "b.md").write_text("# B\n\nContent B.")
        return docs_dir

    def test_new_dataset_incremental_runs_full(
        self, test_db, sample_directory: Path
    ):
        """Incremental on a new dataset runs full ingestion (no last_ingested_at)."""
        config = SourceDirectoryConfig(
            source_path=sample_directory,
            dataset_name="incr-test-new",
            incremental=True,
        )
        pipeline = DatasetIngestPipelineV2(ingest_config=config)
        result = pipeline.ingest()

        # Full run: all documents created
        assert result.documents_created == 2
        assert result.dataset_name == "incr-test-new"

    def test_last_ingested_at_stamped_after_ingest(
        self, test_db, sample_directory: Path
    ):
        """last_ingested_at is set on the dataset after successful ingestion."""
        config = SourceDirectoryConfig(
            source_path=sample_directory,
            dataset_name="incr-test-stamp",
        )
        pipeline = DatasetIngestPipelineV2(ingest_config=config)
        before = datetime.now(tz=timezone.utc)
        result = pipeline.ingest()

        with test_db() as session:
            repo = DatasetRepository(session)
            dataset = repo.get_by_name("incr-test-stamp")
            assert dataset.last_ingested_at is not None
            assert dataset.last_ingested_at >= before.replace(tzinfo=None)

    def test_existing_dataset_incremental_resolves_timestamp(
        self, test_db, sample_directory: Path
    ):
        """Incremental on existing dataset resolves if_modified_since from last_ingested_at."""
        # First run: full ingestion, stamps last_ingested_at
        config1 = SourceDirectoryConfig(
            source_path=sample_directory,
            dataset_name="incr-test-resolve",
        )
        pipeline1 = DatasetIngestPipelineV2(ingest_config=config1)
        result1 = pipeline1.ingest()
        assert result1.documents_created == 2

        # Verify last_ingested_at was set
        with test_db() as session:
            repo = DatasetRepository(session)
            dataset = repo.get_by_name("incr-test-resolve")
            first_ingest_ts = dataset.last_ingested_at
            assert first_ingest_ts is not None

        # Second run: incremental, should resolve if_modified_since
        config2 = SourceDirectoryConfig(
            source_path=sample_directory,
            dataset_name="incr-test-resolve",
            incremental=True,
        )
        pipeline2 = DatasetIngestPipelineV2(ingest_config=config2)
        result2 = pipeline2.ingest()

        # The config should have been mutated with resolved timestamp
        assert config2.if_modified_since is not None

    def test_explicit_if_modified_since_not_overwritten_by_incremental(
        self, test_db, sample_directory: Path
    ):
        """Explicit if_modified_since takes precedence over incremental resolution."""
        # First run
        config1 = SourceDirectoryConfig(
            source_path=sample_directory,
            dataset_name="incr-test-explicit",
        )
        DatasetIngestPipelineV2(ingest_config=config1).ingest()

        # Second run with both incremental=True and explicit timestamp
        explicit_ts = datetime(2020, 1, 1, tzinfo=timezone.utc)
        config2 = SourceDirectoryConfig(
            source_path=sample_directory,
            dataset_name="incr-test-explicit",
            incremental=True,
            if_modified_since=explicit_ts,
        )
        DatasetIngestPipelineV2(ingest_config=config2).ingest()

        # Explicit value should not be overwritten
        assert config2.if_modified_since == explicit_ts

    def test_incremental_skips_deletion_sync(
        self, test_db, sample_directory: Path
    ):
        """Incremental mode does not deactivate missing documents."""
        # First run: full, creates both docs
        config1 = SourceDirectoryConfig(
            source_path=sample_directory,
            dataset_name="incr-test-delsync",
        )
        result1 = DatasetIngestPipelineV2(ingest_config=config1).ingest()
        assert result1.documents_created == 2

        # Second run: incremental with if_modified_since in the future
        # (no files match, empty batch)
        future_ts = datetime(2099, 1, 1, tzinfo=timezone.utc)
        config2 = SourceDirectoryConfig(
            source_path=sample_directory,
            dataset_name="incr-test-delsync",
            if_modified_since=future_ts,
        )
        result2 = DatasetIngestPipelineV2(ingest_config=config2).ingest()

        # No documents should be deactivated despite empty batch
        assert result2.documents_deactivated == 0

        # Original documents should still be active
        with test_db() as session:
            doc_repo = DocumentRepository(session)
            active = doc_repo.list_by_parent(result1.dataset_id, active_only=True)
            assert len(active) == 2
