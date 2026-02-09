"""Integration test: Obsidian vault with cross-linking notes → ingest → query links from DB.

Exercises the full pipeline: ObsidianVaultReader → OntologyMapper →
PersistenceTransform → LinkResolutionTransform, then queries DocumentLink
rows to verify forward links and backlinks are queryable.
"""

from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import pytest
from llama_index.core.ingestion import IngestionPipeline
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from catalog.integrations.obsidian import ObsidianVaultReader
from catalog.store.database import Base, create_engine_for_path
from catalog.store.dataset import DatasetService
from catalog.store.fts import create_fts_table
from catalog.store.models import DocumentLinkKind
from catalog.store.repositories import DocumentLinkRepository
from catalog.store.session_context import use_session
from catalog.integrations.obsidian import LinkResolutionTransform
from catalog.transform.llama import PersistenceTransform
from catalog.transform.ontology import OntologyMapper


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
def linked_vault(tmp_path: Path) -> Path:
    """Create an Obsidian vault with cross-linking notes."""
    vault = tmp_path / "linked-vault"
    vault.mkdir()
    (vault / ".obsidian").mkdir()

    # Note A links to B and C
    (vault / "A.md").write_text("""\
---
title: Note A
tags: [test]
---

# Note A

This note links to [[B]] and [[C]].
Also links to [[B#Section]] (should dedup to just B).
""")

    # Note B links to A
    (vault / "B.md").write_text("""\
---
title: Note B
---

# Note B

Links back to [[A]].
""")

    # Note C links to nothing
    (vault / "C.md").write_text("""\
---
title: Note C
---

# Note C

Standalone note with no outgoing links.
""")

    # Note D links to a non-existent note
    (vault / "D.md").write_text("""\
---
title: Note D
---

# Note D

Links to [[NonExistent]] and [[A]].
""")

    return vault


def _run_pipeline(
    session: Session,
    vault_path: Path,
    dataset_name: str,
) -> tuple[int, LinkResolutionTransform]:
    """Run the pipeline and return (dataset_id, link_transform)."""
    dataset = DatasetService.create_or_update(
        session,
        dataset_name,
        source_type="obsidian",
        source_path=str(vault_path),
    )

    persist = PersistenceTransform(dataset_id=dataset.id)
    mapper = OntologyMapper()
    link_resolve = LinkResolutionTransform(dataset_id=dataset.id)

    pipeline = IngestionPipeline(
        transformations=[mapper, persist, link_resolve],
    )

    reader = ObsidianVaultReader(vault_path)
    documents = reader.load_data()
    pipeline.run(documents=documents)
    return dataset.id, link_resolve


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestObsidianLinkIntegration:
    """End-to-end link resolution through a real vault ingestion."""

    def test_links_created(self, session_factory, linked_vault: Path) -> None:
        """Ingestion creates DocumentLink rows for resolved wikilinks."""
        with create_session(session_factory) as session:
            with use_session(session):
                dataset_id, link_transform = _run_pipeline(
                    session, linked_vault, "link-test-vault"
                )

        assert link_transform.stats.resolved > 0

        # Verify links exist in the database.
        with create_session(session_factory) as session:
            rows = session.execute(
                text("SELECT * FROM document_links")
            ).fetchall()

        assert len(rows) > 0

    def test_forward_links_queryable(self, session_factory, linked_vault: Path) -> None:
        """Forward links (outgoing) can be queried by source document."""
        with create_session(session_factory) as session:
            with use_session(session):
                dataset_id, _ = _run_pipeline(
                    session, linked_vault, "link-test-vault"
                )

        # Get doc A's ID.
        with create_session(session_factory) as session:
            row_a = session.execute(
                text("SELECT d.id FROM documents d WHERE d.path LIKE '%A.md'")
            ).fetchone()
            assert row_a is not None

            with use_session(session):
                link_repo = DocumentLinkRepository()
                outgoing = link_repo.list_outgoing(row_a.id)

            # A links to B and C (fragment links deduped).
            target_ids = {l.target_id for l in outgoing}
            assert len(target_ids) == 2

    def test_backlinks_queryable(self, session_factory, linked_vault: Path) -> None:
        """Backlinks (incoming) can be queried by target document."""
        with create_session(session_factory) as session:
            with use_session(session):
                dataset_id, _ = _run_pipeline(
                    session, linked_vault, "link-test-vault"
                )

        # Get doc A's ID — B and D both link to A.
        with create_session(session_factory) as session:
            row_a = session.execute(
                text("SELECT d.id FROM documents d WHERE d.path LIKE '%A.md'")
            ).fetchone()
            assert row_a is not None

            with use_session(session):
                link_repo = DocumentLinkRepository()
                incoming = link_repo.list_incoming(row_a.id)

            assert len(incoming) == 2

    def test_dead_links_counted_as_unresolved(self, session_factory, linked_vault: Path) -> None:
        """Wikilinks to non-existent notes are counted as unresolved.

        D.md contains [[NonExistent]] which cannot resolve to any document,
        so it is counted as unresolved. D's [[A]] link resolves normally.
        """
        with create_session(session_factory) as session:
            with use_session(session):
                dataset_id, link_transform = _run_pipeline(
                    session, linked_vault, "link-test-vault"
                )

        # NonExistent is unresolvable.
        assert link_transform.stats.unresolved == 1

        # D has only the resolved link to A.
        with create_session(session_factory) as session:
            row_d = session.execute(
                text("SELECT d.id FROM documents d WHERE d.path LIKE '%D.md'")
            ).fetchone()
            assert row_d is not None

            with use_session(session):
                link_repo = DocumentLinkRepository()
                outgoing = link_repo.list_outgoing(row_d.id)

            assert len(outgoing) == 1

    def test_idempotent_re_ingestion(self, session_factory, linked_vault: Path) -> None:
        """Running the pipeline twice produces the same set of links."""
        # First run
        with create_session(session_factory) as session:
            with use_session(session):
                _run_pipeline(session, linked_vault, "link-test-vault")

        with create_session(session_factory) as session:
            count_1 = session.execute(
                text("SELECT COUNT(*) FROM document_links")
            ).scalar()

        # Second run (force=True in pipeline resets)
        with create_session(session_factory) as session:
            with use_session(session):
                _run_pipeline(session, linked_vault, "link-test-vault")

        with create_session(session_factory) as session:
            count_2 = session.execute(
                text("SELECT COUNT(*) FROM document_links")
            ).scalar()

        assert count_1 == count_2

    def test_link_relation_is_wikilink(self, session_factory, linked_vault: Path) -> None:
        """All created links have relation=WIKILINK."""
        with create_session(session_factory) as session:
            with use_session(session):
                _run_pipeline(session, linked_vault, "link-test-vault")

        with create_session(session_factory) as session:
            rows = session.execute(
                text("SELECT relation FROM document_links")
            ).fetchall()

        for row in rows:
            # SQLite stores enum name; accept both name and value.
            assert row.relation in (
                DocumentLinkKind.WIKILINK.value,
                DocumentLinkKind.WIKILINK.name,
            )

    def test_standalone_note_has_no_outgoing(self, session_factory, linked_vault: Path) -> None:
        """Note C has no outgoing links."""
        with create_session(session_factory) as session:
            with use_session(session):
                _run_pipeline(session, linked_vault, "link-test-vault")

        with create_session(session_factory) as session:
            row_c = session.execute(
                text("SELECT d.id FROM documents d WHERE d.path LIKE '%C.md'")
            ).fetchone()
            assert row_c is not None

            with use_session(session):
                link_repo = DocumentLinkRepository()
                outgoing = link_repo.list_outgoing(row_c.id)

            assert len(outgoing) == 0

    def test_standalone_note_has_incoming(self, session_factory, linked_vault: Path) -> None:
        """Note C has incoming links (A links to C)."""
        with create_session(session_factory) as session:
            with use_session(session):
                _run_pipeline(session, linked_vault, "link-test-vault")

        with create_session(session_factory) as session:
            row_c = session.execute(
                text("SELECT d.id FROM documents d WHERE d.path LIKE '%C.md'")
            ).fetchone()
            assert row_c is not None

            with use_session(session):
                link_repo = DocumentLinkRepository()
                incoming = link_repo.list_incoming(row_c.id)

            assert len(incoming) == 1
