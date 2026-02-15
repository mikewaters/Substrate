"""Integration tests for minimal-content markdown ingestion.

Issue #62 coverage:
1. Obsidian document with frontmatter only.
2. Heptabase document with frontmatter + H1 title only.

Both scenarios must still persist the document and produce FTS/vector entries.
"""

import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Generator
from unittest.mock import patch

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from catalog.core.settings import get_settings
from catalog.ingest.pipelines import DatasetIngestPipeline
from catalog.integrations.heptabase import SourceHeptabaseConfig
from catalog.integrations.obsidian import SourceObsidianConfig
from catalog.store.database import Base, create_engine_for_path
from catalog.store.fts import create_fts_table
from catalog.store.fts_chunk import create_chunks_fts_table


def _clear_pipeline_cache(dataset_names: list[str]) -> None:
    """Clear LlamaIndex pipeline cache for specific datasets."""
    settings = get_settings()
    pipeline_dir = settings.cache_path / "pipeline_storage"
    for name in dataset_names:
        cache_path = pipeline_dir / name
        if cache_path.exists():
            shutil.rmtree(cache_path)


@pytest.fixture
def test_engine(tmp_path: Path) -> Engine:
    """Create a temporary SQLite database and required FTS tables."""
    db_path = tmp_path / "test.db"
    engine = create_engine_for_path(db_path)
    Base.metadata.create_all(engine)
    create_fts_table(engine)
    create_chunks_fts_table(engine)
    return engine


@pytest.fixture
def session_factory(test_engine: Engine):
    """Create a SQLAlchemy session factory for the test database."""
    return sessionmaker(bind=test_engine, expire_on_commit=False)


@contextmanager
def create_session(factory) -> Generator[Session, None, None]:
    """Create a session that auto-commits on success."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@pytest.fixture(autouse=True)
def clear_cache() -> None:
    """Clear pipeline cache before and after each test for isolation."""
    dataset_names = [
        "issue62-obsidian-frontmatter-only",
        "issue62-heptabase-frontmatter-h1-only",
    ]
    _clear_pipeline_cache(dataset_names)
    yield
    _clear_pipeline_cache(dataset_names)


@pytest.fixture(autouse=True)
def use_mock_embedding(patched_embedding, mock_embed_model) -> None:
    """Use mock embedding/vector fixtures from tests/idx/conftest.py."""
    with patch("catalog.ingest.pipelines.get_embed_model", return_value=mock_embed_model):
        yield


@pytest.fixture
def patched_get_session(session_factory):
    """Patch pipeline get_session to use the test database."""

    @contextmanager
    def get_test_session():
        with create_session(session_factory) as session:
            yield session

    with patch("catalog.ingest.pipelines.get_session", get_test_session):
        yield get_test_session


@pytest.fixture
def obsidian_frontmatter_only_vault(tmp_path: Path) -> Path:
    """Create a minimal Obsidian vault containing a frontmatter-only document."""
    vault = tmp_path / "obsidian-vault"
    vault.mkdir()
    (vault / ".obsidian").mkdir()
    (vault / "frontmatter-only.md").write_text(
        """---
title: Frontmatter Only
tags: [issue-62]
---
""",
        encoding="utf-8",
    )
    return vault


@pytest.fixture
def heptabase_frontmatter_h1_export(tmp_path: Path) -> Path:
    """Create a minimal Heptabase export with frontmatter + H1 only."""
    export_dir = tmp_path / "heptabase-export"
    export_dir.mkdir()
    (export_dir / "title-only.md").write_text(
        """---
title: Title Only
tags: [issue-62]
---
# Title
""",
        encoding="utf-8",
    )
    return export_dir


def _assert_document_fts_and_vectors_exist(
    session_factory,
    patched_embedding,
    dataset_name: str,
) -> None:
    """Assert document persistence and FTS/vector indexing for a dataset."""
    with create_session(session_factory) as session:
        dataset_id = session.execute(
            text("SELECT id FROM datasets WHERE name = :dataset_name"),
            {"dataset_name": dataset_name},
        ).scalar_one()

        doc_count = session.execute(
            text(
                "SELECT COUNT(*) FROM documents "
                "WHERE parent_id = :dataset_id AND active = 1"
            ),
            {"dataset_id": dataset_id},
        ).scalar_one()
        assert doc_count == 1

        doc_fts_count = session.execute(
            text(
                "SELECT COUNT(*) "
                "FROM documents_fts f "
                "JOIN documents d ON d.id = f.rowid "
                "WHERE d.parent_id = :dataset_id"
            ),
            {"dataset_id": dataset_id},
        ).scalar_one()
        assert doc_fts_count == 1

        chunk_fts_count = session.execute(
            text(
                "SELECT COUNT(*) "
                "FROM chunks_fts "
                "WHERE source_doc_id LIKE :source_doc_id_prefix"
            ),
            {"source_doc_id_prefix": f"{dataset_name}:%"},
        ).scalar_one()
        assert chunk_fts_count >= 1

    vector_store = patched_embedding["vector_manager"].get_vector_store.return_value
    # SimpleVectorStore: verify vectors were written
    point_count = len(vector_store.data.embedding_dict)
    assert point_count >= 1


class TestMinimalContentIngestion:
    """Integration coverage for minimal-content ingestion edge cases."""

    def test_obsidian_frontmatter_only_document_is_stored_and_indexed(
        self,
        patched_get_session,
        session_factory,
        patched_embedding,
        obsidian_frontmatter_only_vault: Path,
    ) -> None:
        """Frontmatter-only Obsidian note should still produce FTS/vector artifacts."""
        dataset_name = "issue62-obsidian-frontmatter-only"
        pipeline = DatasetIngestPipeline()
        result = pipeline.ingest_dataset(
            SourceObsidianConfig(
                source_path=obsidian_frontmatter_only_vault,
                dataset_name=dataset_name,
            )
        )

        assert result.documents_created == 1
        assert result.documents_failed == 0
        assert result.vectors_inserted >= 1

        _assert_document_fts_and_vectors_exist(
            session_factory=session_factory,
            patched_embedding=patched_embedding,
            dataset_name=dataset_name,
        )

    def test_heptabase_frontmatter_plus_h1_document_is_stored_and_indexed(
        self,
        patched_get_session,
        session_factory,
        patched_embedding,
        heptabase_frontmatter_h1_export: Path,
    ) -> None:
        """Heptabase frontmatter + H1-only note should still produce FTS/vector artifacts."""
        dataset_name = "issue62-heptabase-frontmatter-h1-only"
        pipeline = DatasetIngestPipeline()
        result = pipeline.ingest_dataset(
            SourceHeptabaseConfig(
                source_path=heptabase_frontmatter_h1_export,
                dataset_name=dataset_name,
            )
        )

        assert result.documents_created == 1
        assert result.documents_failed == 0
        assert result.vectors_inserted >= 1

        _assert_document_fts_and_vectors_exist(
            session_factory=session_factory,
            patched_embedding=patched_embedding,
            dataset_name=dataset_name,
        )
