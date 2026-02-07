"""Integration tests for frontmatter → ontology metadata through the ingestion pipeline.

Exercises FrontmatterTransform within a LlamaIndex IngestionPipeline (the same
pipeline shape used by DatasetIngestPipeline.ingest_dataset()), verifying that raw
YAML frontmatter is validated, converted to DocumentMeta, and persisted as
structured ontology metadata in the database.
"""

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import pytest
from llama_index.core.ingestion import IngestionPipeline
from pydantic import Field
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from catalog.integrations.obsidian import ObsidianVaultReader
from catalog.integrations.obsidian import VaultSchema
from catalog.store.database import Base, create_engine_for_path
from catalog.store.dataset import DatasetService
from catalog.store.fts import create_fts_table
from catalog.store.session_context import use_session
from catalog.integrations.obsidian.transforms import FrontmatterTransform
from catalog.transform.llama import PersistenceTransform


# ---------------------------------------------------------------------------
# Test vault schema
# ---------------------------------------------------------------------------

class SampleVaultSchema(VaultSchema):
    """Schema for the test vault frontmatter."""

    tags: list[str] = Field(default_factory=list, json_schema_extra={"maps_to": "tags"})
    note_type: str | None = Field(None, json_schema_extra={"maps_to": "categories"})
    author: str | None = Field(None, json_schema_extra={"maps_to": "author"})
    aliases: list[str] = Field(default_factory=list)
    cssclass: str | None = None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_engine(tmp_path: Path) -> Engine:
    """Create a temporary SQLite database with all required tables."""
    db_path = tmp_path / "test.db"
    engine = create_engine_for_path(db_path)
    Base.metadata.create_all(engine)
    create_fts_table(engine)
    return engine


@pytest.fixture
def session_factory(test_engine: Engine):
    return sessionmaker(bind=test_engine, expire_on_commit=False)


@contextmanager
def create_session(factory) -> Generator[Session, None, None]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@pytest.fixture
def ontology_vault(tmp_path: Path) -> Path:
    """Create a small Obsidian vault with diverse frontmatter for ontology tests."""
    vault = tmp_path / "ontology-vault"
    vault.mkdir()
    (vault / ".obsidian").mkdir()

    # Note with full frontmatter: title, tags, categories, author, description.
    (vault / "full_meta.md").write_text("""\
---
title: Full Metadata Note
tags: [python, testing]
note_type: tutorial
author: Mike
description: A note with every ontology field populated.
aliases: [FMN, Full Note]
cssclass: wide
---

# Full Metadata Note

This note exercises all mapped and unmapped frontmatter fields.
""")

    # Note relying on alias for title, no explicit title key.
    (vault / "alias_title.md").write_text("""\
---
aliases: [Alias-Derived Title]
tags: [experiment]
---

# Some heading

Content that should get the alias as its title.
""")

    # Note with no frontmatter at all — title falls back to filename stem.
    (vault / "bare_note.md").write_text("""\
This note has no YAML frontmatter.

It should derive its title from the filename.
""")

    # Note with extra/unknown frontmatter keys that should land in extra.
    (vault / "extra_keys.md").write_text("""\
---
title: Extra Keys Note
tags: [misc]
custom_field: 42
project: lifeos
---

# Extra Keys Note

Has frontmatter keys not in the ontology.
""")

    # Note with description only in frontmatter (no summary key).
    (vault / "desc_only.md").write_text("""\
---
title: Description Only
description: Explicit frontmatter description.
---

Body text here.
""")

    return vault


def _run_pipeline(
    session: Session,
    vault_path: Path,
    dataset_name: str,
    vault_schema_cls: type[VaultSchema] | None = None,
) -> int:
    """Run a pipeline identical to DatasetIngestPipeline.ingest_dataset().

    Reads documents with ObsidianVaultReader, transforms through
    FrontmatterTransform + PersistenceTransform, and returns the count
    of nodes produced.
    """
    dataset = DatasetService.create_or_update(
        session,
        dataset_name,
        source_type="obsidian",
        source_path=str(vault_path),
    )

    persist = PersistenceTransform(dataset_id=dataset.id)
    frontmatter = FrontmatterTransform(vault_schema_cls=vault_schema_cls)

    pipeline = IngestionPipeline(
        transformations=[frontmatter, persist],
    )

    reader = ObsidianVaultReader(vault_path)
    documents = reader.load_data()
    nodes = pipeline.run(documents=documents)
    return len(nodes)


# ---------------------------------------------------------------------------
# Tests — with VaultSchema
# ---------------------------------------------------------------------------

class TestFrontmatterOntologyWithSchema:
    """Full pipeline run with a VaultSchema validates and maps frontmatter."""

    def test_ingest_creates_documents_with_ontology_metadata(
        self,
        session_factory,
        ontology_vault: Path,
    ) -> None:
        """All documents are created and carry ontology-shaped metadata_json."""
        with create_session(session_factory) as session:
            with use_session(session):
                count = _run_pipeline(
                    session, ontology_vault, "ontology-test-vault",
                    vault_schema_cls=SampleVaultSchema,
                )

        assert count == 5

        with create_session(session_factory) as session:
            rows = session.execute(
                text(
                    "SELECT d.path, r.title, r.description, d.metadata_json "
                    "FROM documents d JOIN resources r ON d.id = r.id "
                    "ORDER BY d.path"
                )
            ).fetchall()

        assert len(rows) == 5
        for row in rows:
            assert row.metadata_json is not None
            meta = json.loads(row.metadata_json)
            assert "title" in meta or "tags" in meta, (
                f"Missing ontology keys in {row.path}"
            )

    def test_full_meta_note_ontology(
        self,
        session_factory,
        ontology_vault: Path,
    ) -> None:
        """A note with all frontmatter fields populates ontology correctly."""
        with create_session(session_factory) as session:
            with use_session(session):
                _run_pipeline(
                    session, ontology_vault, "ontology-test-vault",
                    vault_schema_cls=SampleVaultSchema,
                )

        with create_session(session_factory) as session:
            row = session.execute(
                text(
                    "SELECT r.title, r.description, d.metadata_json "
                    "FROM documents d JOIN resources r ON d.id = r.id "
                    "WHERE d.path LIKE '%full_meta%'"
                )
            ).fetchone()

        assert row is not None
        assert row.title == "Full Metadata Note"
        assert row.description == "A note with every ontology field populated."

        meta = json.loads(row.metadata_json)
        assert meta["title"] == "Full Metadata Note"
        assert meta["description"] == "A note with every ontology field populated."
        assert meta["tags"] == ["python", "testing"]
        assert meta["categories"] == ["tutorial"]
        assert meta["author"] == "Mike"
        assert meta["extra"]["aliases"] == ["FMN", "Full Note"]
        assert meta["extra"]["cssclass"] == "wide"

    def test_alias_derived_title(
        self,
        session_factory,
        ontology_vault: Path,
    ) -> None:
        """When no explicit title, first alias becomes the title."""
        with create_session(session_factory) as session:
            with use_session(session):
                _run_pipeline(
                    session, ontology_vault, "ontology-test-vault",
                    vault_schema_cls=SampleVaultSchema,
                )

        with create_session(session_factory) as session:
            row = session.execute(
                text(
                    "SELECT r.title FROM documents d "
                    "JOIN resources r ON d.id = r.id "
                    "WHERE d.path LIKE '%alias_title%'"
                )
            ).fetchone()

        assert row is not None
        assert row.title == "Alias-Derived Title"

    def test_bare_note_title_from_filename(
        self,
        session_factory,
        ontology_vault: Path,
    ) -> None:
        """A note without frontmatter gets its title from the filename stem."""
        with create_session(session_factory) as session:
            with use_session(session):
                _run_pipeline(
                    session, ontology_vault, "ontology-test-vault",
                    vault_schema_cls=SampleVaultSchema,
                )

        with create_session(session_factory) as session:
            row = session.execute(
                text(
                    "SELECT r.title FROM documents d "
                    "JOIN resources r ON d.id = r.id "
                    "WHERE d.path LIKE '%bare_note%'"
                )
            ).fetchone()

        assert row is not None
        assert row.title == "bare_note"

    def test_extra_keys_in_ontology_extra(
        self,
        session_factory,
        ontology_vault: Path,
    ) -> None:
        """Unknown frontmatter keys land in DocumentMeta.extra."""
        with create_session(session_factory) as session:
            with use_session(session):
                _run_pipeline(
                    session, ontology_vault, "ontology-test-vault",
                    vault_schema_cls=SampleVaultSchema,
                )

        with create_session(session_factory) as session:
            row = session.execute(
                text(
                    "SELECT d.metadata_json FROM documents d "
                    "WHERE d.path LIKE '%extra_keys%'"
                )
            ).fetchone()

        assert row is not None
        meta = json.loads(row.metadata_json)
        assert meta["extra"]["custom_field"] == 42
        assert meta["extra"]["project"] == "lifeos"

    def test_metadata_json_is_ontology_shaped(
        self,
        session_factory,
        ontology_vault: Path,
    ) -> None:
        """metadata_json contains ontology structure, not raw frontmatter."""
        with create_session(session_factory) as session:
            with use_session(session):
                _run_pipeline(
                    session, ontology_vault, "ontology-test-vault",
                    vault_schema_cls=SampleVaultSchema,
                )

        with create_session(session_factory) as session:
            rows = session.execute(
                text("SELECT d.path, d.metadata_json FROM documents d")
            ).fetchall()

        for row in rows:
            meta = json.loads(row.metadata_json)
            # Should be ontology-shaped, not raw frontmatter.
            assert "frontmatter" not in meta, f"raw frontmatter leaked in {row.path}"
            assert "note_name" not in meta, f"note_name leaked in {row.path}"
            assert "file_path" not in meta, f"file_path leaked in {row.path}"

    def test_description_from_frontmatter(
        self,
        session_factory,
        ontology_vault: Path,
    ) -> None:
        """Explicit frontmatter description is persisted on the document."""
        with create_session(session_factory) as session:
            with use_session(session):
                _run_pipeline(
                    session, ontology_vault, "ontology-test-vault",
                    vault_schema_cls=SampleVaultSchema,
                )

        with create_session(session_factory) as session:
            row = session.execute(
                text(
                    "SELECT r.description FROM documents d "
                    "JOIN resources r ON d.id = r.id "
                    "WHERE d.path LIKE '%desc_only%'"
                )
            ).fetchone()

        assert row is not None
        assert row.description == "Explicit frontmatter description."


# ---------------------------------------------------------------------------
# Tests — without VaultSchema (best-effort mode)
# ---------------------------------------------------------------------------

class TestFrontmatterOntologyBestEffort:
    """Pipeline without a VaultSchema still produces ontology metadata."""

    def test_best_effort_tags_and_title(
        self,
        session_factory,
        ontology_vault: Path,
    ) -> None:
        """Without a schema, tags and title are still extracted best-effort."""
        with create_session(session_factory) as session:
            with use_session(session):
                _run_pipeline(
                    session, ontology_vault, "ontology-no-schema-vault",
                    vault_schema_cls=None,
                )

        with create_session(session_factory) as session:
            row = session.execute(
                text(
                    "SELECT r.title, d.metadata_json FROM documents d "
                    "JOIN resources r ON d.id = r.id "
                    "WHERE d.path LIKE '%full_meta%'"
                )
            ).fetchone()

        assert row is not None
        assert row.title == "Full Metadata Note"

        meta = json.loads(row.metadata_json)
        assert meta["tags"] == ["python", "testing"]
        assert meta["title"] == "Full Metadata Note"

    def test_best_effort_unknown_keys_to_extra(
        self,
        session_factory,
        ontology_vault: Path,
    ) -> None:
        """Without a schema, unrecognized keys go to extra."""
        with create_session(session_factory) as session:
            with use_session(session):
                _run_pipeline(
                    session, ontology_vault, "ontology-no-schema-vault",
                    vault_schema_cls=None,
                )

        with create_session(session_factory) as session:
            row = session.execute(
                text(
                    "SELECT d.metadata_json FROM documents d "
                    "WHERE d.path LIKE '%extra_keys%'"
                )
            ).fetchone()

        assert row is not None
        meta = json.loads(row.metadata_json)
        assert meta["extra"]["custom_field"] == 42
