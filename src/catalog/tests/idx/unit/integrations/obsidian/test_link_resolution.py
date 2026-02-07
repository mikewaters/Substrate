"""Tests for LinkResolutionTransform (catalog.integrations.obsidian.transforms)."""

from pathlib import Path

import pytest
from llama_index.core.schema import Document as LlamaDocument
from sqlalchemy.orm import sessionmaker

from catalog.store.database import Base, create_engine_for_path
from catalog.store.dataset import DatasetService
from catalog.store.fts import create_fts_table
from catalog.store.models import Dataset, Document, DocumentLink, DocumentLinkKind
from catalog.store.repositories import DocumentLinkRepository, DocumentRepository
from catalog.store.session_context import use_session
from catalog.integrations.obsidian import LinkResolutionTransform
from catalog.transform.llama import PersistenceTransform


@pytest.fixture
def db_session(tmp_path: Path):
    """Create a test database session with all tables."""
    db_path = tmp_path / "test.db"
    engine = create_engine_for_path(db_path)
    Base.metadata.create_all(engine)
    create_fts_table(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    yield session
    session.close()


@pytest.fixture
def dataset_id(db_session) -> int:
    """Create a test dataset and return its ID."""
    with use_session(db_session):
        dataset = DatasetService.create_or_update(
            db_session, "test-vault", source_type="obsidian", source_path="/test"
        )
        db_session.commit()
    return dataset.id


def _make_node(path: str, wikilinks: list[str] | None = None, **extra_meta) -> LlamaDocument:
    """Build a LlamaDocument with metadata mimicking post-PersistenceTransform state."""
    meta = {"relative_path": path, "note_name": Path(path).stem}
    if wikilinks is not None:
        meta["wikilinks"] = wikilinks
    meta.update(extra_meta)
    return LlamaDocument(text=f"Content of {path}", metadata=meta)


def _persist_nodes(db_session, dataset_id: int, nodes: list[LlamaDocument]) -> list[LlamaDocument]:
    """Run PersistenceTransform on nodes to create DB records and assign doc_id."""
    with use_session(db_session):
        persist = PersistenceTransform(dataset_id=dataset_id)
        result = persist(nodes)
        db_session.commit()
    return result


class TestLinkResolution:
    """Tests for LinkResolutionTransform."""

    def test_resolves_wikilinks(self, db_session, dataset_id: int) -> None:
        """Wikilinks are resolved to document IDs and DocumentLink rows created."""
        nodes = [
            _make_node("A.md", wikilinks=["B", "C"]),
            _make_node("B.md"),
            _make_node("C.md"),
        ]
        nodes = _persist_nodes(db_session, dataset_id, nodes)

        with use_session(db_session):
            transform = LinkResolutionTransform(dataset_id=dataset_id)
            transform(nodes)
            db_session.commit()

        assert transform.stats.resolved == 2
        assert transform.stats.unresolved == 0

        with use_session(db_session):
            link_repo = DocumentLinkRepository()
            outgoing = link_repo.list_outgoing(nodes[0].metadata["doc_id"])
        assert len(outgoing) == 2

    def test_unresolved_links_counted(self, db_session, dataset_id: int) -> None:
        """Links to non-existent documents are counted as unresolved."""
        nodes = [
            _make_node("A.md", wikilinks=["B", "NonExistent"]),
            _make_node("B.md"),
        ]
        nodes = _persist_nodes(db_session, dataset_id, nodes)

        with use_session(db_session):
            transform = LinkResolutionTransform(dataset_id=dataset_id)
            transform(nodes)
            db_session.commit()

        assert transform.stats.resolved == 1
        assert transform.stats.unresolved == 1

    def test_self_links_skipped(self, db_session, dataset_id: int) -> None:
        """Links from a document to itself are skipped."""
        nodes = [
            _make_node("A.md", wikilinks=["A"]),
        ]
        nodes = _persist_nodes(db_session, dataset_id, nodes)

        with use_session(db_session):
            transform = LinkResolutionTransform(dataset_id=dataset_id)
            transform(nodes)
            db_session.commit()

        assert transform.stats.self_links == 1
        assert transform.stats.resolved == 0

        with use_session(db_session):
            link_repo = DocumentLinkRepository()
            outgoing = link_repo.list_outgoing(nodes[0].metadata["doc_id"])
        assert len(outgoing) == 0

    def test_idempotent_re_ingestion(self, db_session, dataset_id: int) -> None:
        """Running the transform twice produces the same links (idempotent)."""
        nodes = [
            _make_node("A.md", wikilinks=["B"]),
            _make_node("B.md"),
        ]
        nodes = _persist_nodes(db_session, dataset_id, nodes)

        with use_session(db_session):
            # First run
            transform1 = LinkResolutionTransform(dataset_id=dataset_id)
            transform1(nodes)
            db_session.flush()

            # Second run
            transform2 = LinkResolutionTransform(dataset_id=dataset_id)
            transform2(nodes)
            db_session.flush()

            link_repo = DocumentLinkRepository()
            outgoing = link_repo.list_outgoing(nodes[0].metadata["doc_id"])
            assert len(outgoing) == 1
            db_session.commit()

    def test_nodes_without_wikilinks_ignored(self, db_session, dataset_id: int) -> None:
        """Nodes without wikilinks metadata are silently skipped."""
        nodes = [
            _make_node("A.md"),  # No wikilinks
            _make_node("B.md"),
        ]
        nodes = _persist_nodes(db_session, dataset_id, nodes)

        with use_session(db_session):
            transform = LinkResolutionTransform(dataset_id=dataset_id)
            transform(nodes)
            db_session.commit()

        assert transform.stats.documents_processed == 0
        assert transform.stats.resolved == 0

    def test_stats_reset_between_runs(self, db_session, dataset_id: int) -> None:
        """Stats are reset at the start of each __call__."""
        nodes = [
            _make_node("A.md", wikilinks=["B"]),
            _make_node("B.md"),
        ]
        nodes = _persist_nodes(db_session, dataset_id, nodes)

        with use_session(db_session):
            transform = LinkResolutionTransform(dataset_id=dataset_id)
            transform(nodes)
            assert transform.stats.resolved == 1

            # Run again - stats should reset, not accumulate.
            transform(nodes)
            assert transform.stats.resolved == 1
            db_session.commit()

    def test_passthrough_returns_same_nodes(self, db_session, dataset_id: int) -> None:
        """Transform returns the same list of nodes it received."""
        nodes = [
            _make_node("A.md", wikilinks=["B"]),
            _make_node("B.md"),
        ]
        nodes = _persist_nodes(db_session, dataset_id, nodes)

        with use_session(db_session):
            transform = LinkResolutionTransform(dataset_id=dataset_id)
            result = transform(nodes)
            db_session.commit()

        assert result is nodes

    def test_shortest_path_wins_for_duplicate_stems(self, db_session, dataset_id: int) -> None:
        """When two docs have the same stem, the shorter path wins."""
        nodes = [
            _make_node("sub/deep/B.md"),  # Longer path
            _make_node("B.md"),            # Shorter path
            _make_node("A.md", wikilinks=["B"]),
        ]
        nodes = _persist_nodes(db_session, dataset_id, nodes)

        with use_session(db_session):
            transform = LinkResolutionTransform(dataset_id=dataset_id)
            transform(nodes)
            db_session.commit()

        assert transform.stats.resolved == 1

        # Should resolve to the shorter-path B.md
        with use_session(db_session):
            link_repo = DocumentLinkRepository()
            outgoing = link_repo.list_outgoing(nodes[2].metadata["doc_id"])
        assert len(outgoing) == 1
        assert outgoing[0].target_id == nodes[1].metadata["doc_id"]

    def test_backlinks_queryable(self, db_session, dataset_id: int) -> None:
        """Backlinks can be queried via list_incoming()."""
        nodes = [
            _make_node("A.md", wikilinks=["C"]),
            _make_node("B.md", wikilinks=["C"]),
            _make_node("C.md"),
        ]
        nodes = _persist_nodes(db_session, dataset_id, nodes)

        with use_session(db_session):
            transform = LinkResolutionTransform(dataset_id=dataset_id)
            transform(nodes)
            db_session.commit()

        with use_session(db_session):
            link_repo = DocumentLinkRepository()
            incoming = link_repo.list_incoming(nodes[2].metadata["doc_id"])
        assert len(incoming) == 2
        source_ids = {l.source_id for l in incoming}
        assert source_ids == {nodes[0].metadata["doc_id"], nodes[1].metadata["doc_id"]}
