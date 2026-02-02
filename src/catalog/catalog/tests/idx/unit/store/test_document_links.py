"""Tests for DocumentLink model and DocumentLinkRepository."""

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from catalog.store.database import Base, create_engine_for_path
from catalog.store.models import (
    Dataset,
    Document,
    DocumentLink,
    DocumentLinkKind,
)
from catalog.store.repositories import DocumentLinkRepository
from catalog.store.session_context import use_session


@pytest.fixture
def db_session(tmp_path: Path):
    """Create a test database session with all tables."""
    db_path = tmp_path / "test.db"
    engine = create_engine_for_path(db_path)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    yield session
    session.close()


@pytest.fixture
def dataset(db_session) -> Dataset:
    """Create a test dataset."""
    ds = Dataset(
        name="link-test",
        uri="dataset:link-test",
        source_type="obsidian",
        source_path="/test/vault",
    )
    db_session.add(ds)
    db_session.commit()
    return ds


@pytest.fixture
def docs(db_session, dataset: Dataset) -> list[Document]:
    """Create three test documents for link tests."""
    doc_a = Document(
        uri="document:link-test/A.md",
        parent_id=dataset.id,
        path="A.md",
        content_hash="hash_a",
        body="# A\n\nLinks to B and C.",
    )
    doc_b = Document(
        uri="document:link-test/B.md",
        parent_id=dataset.id,
        path="B.md",
        content_hash="hash_b",
        body="# B\n\nLinks to A.",
    )
    doc_c = Document(
        uri="document:link-test/C.md",
        parent_id=dataset.id,
        path="C.md",
        content_hash="hash_c",
        body="# C\n\nNo links.",
    )
    db_session.add_all([doc_a, doc_b, doc_c])
    db_session.commit()
    return [doc_a, doc_b, doc_c]


# ---------------------------------------------------------------------------
# DocumentLink model tests
# ---------------------------------------------------------------------------


class TestDocumentLinkModel:
    """Tests for the DocumentLink ORM model."""

    def test_create_link(self, db_session, docs: list[Document]) -> None:
        """DocumentLink can be created with composite PK."""
        link = DocumentLink(
            source_id=docs[0].id,
            target_id=docs[1].id,
            relation=DocumentLinkKind.WIKILINK,
        )
        db_session.add(link)
        db_session.commit()

        assert link.source_id == docs[0].id
        assert link.target_id == docs[1].id
        assert link.relation == DocumentLinkKind.WIKILINK

    def test_duplicate_link_rejected(self, db_session, docs: list[Document]) -> None:
        """Cannot create duplicate (source_id, target_id) links."""
        link1 = DocumentLink(
            source_id=docs[0].id,
            target_id=docs[1].id,
            relation=DocumentLinkKind.WIKILINK,
        )
        db_session.add(link1)
        db_session.commit()

        link2 = DocumentLink(
            source_id=docs[0].id,
            target_id=docs[1].id,
            relation=DocumentLinkKind.WIKILINK,
        )
        db_session.add(link2)
        with pytest.raises(Exception):
            db_session.commit()

    def test_outgoing_links_relationship(self, db_session, docs: list[Document]) -> None:
        """Document.outgoing_links returns its outgoing links."""
        link = DocumentLink(
            source_id=docs[0].id,
            target_id=docs[1].id,
            relation=DocumentLinkKind.WIKILINK,
        )
        db_session.add(link)
        db_session.commit()

        db_session.refresh(docs[0])
        assert len(docs[0].outgoing_links) == 1
        assert docs[0].outgoing_links[0].target_id == docs[1].id

    def test_incoming_links_relationship(self, db_session, docs: list[Document]) -> None:
        """Document.incoming_links returns links pointing to it."""
        link = DocumentLink(
            source_id=docs[0].id,
            target_id=docs[1].id,
            relation=DocumentLinkKind.WIKILINK,
        )
        db_session.add(link)
        db_session.commit()

        db_session.refresh(docs[1])
        assert len(docs[1].incoming_links) == 1
        assert docs[1].incoming_links[0].source_id == docs[0].id

    def test_cascade_delete_source(self, db_session, docs: list[Document]) -> None:
        """Deleting the source document cascades to its outgoing links."""
        link = DocumentLink(
            source_id=docs[0].id,
            target_id=docs[1].id,
            relation=DocumentLinkKind.WIKILINK,
        )
        db_session.add(link)
        db_session.commit()

        db_session.delete(docs[0])
        db_session.commit()

        remaining = db_session.execute(select(DocumentLink)).scalars().all()
        assert len(remaining) == 0

    def test_cascade_delete_target(self, db_session, docs: list[Document]) -> None:
        """Deleting the target document cascades to its incoming links."""
        link = DocumentLink(
            source_id=docs[0].id,
            target_id=docs[1].id,
            relation=DocumentLinkKind.WIKILINK,
        )
        db_session.add(link)
        db_session.commit()

        db_session.delete(docs[1])
        db_session.commit()

        remaining = db_session.execute(select(DocumentLink)).scalars().all()
        assert len(remaining) == 0

    def test_repr(self, db_session, docs: list[Document]) -> None:
        """DocumentLink has useful repr."""
        link = DocumentLink(
            source_id=docs[0].id,
            target_id=docs[1].id,
            relation=DocumentLinkKind.WIKILINK,
        )
        db_session.add(link)
        db_session.commit()

        repr_str = repr(link)
        assert "DocumentLink" in repr_str
        assert "WIKILINK" in repr_str


# ---------------------------------------------------------------------------
# DocumentLinkRepository tests
# ---------------------------------------------------------------------------


class TestDocumentLinkRepository:
    """Tests for DocumentLinkRepository."""

    def test_create(self, db_session, docs: list[Document]) -> None:
        """create() inserts a new link."""
        with use_session(db_session):
            repo = DocumentLinkRepository()
            link = repo.create(docs[0].id, docs[1].id, DocumentLinkKind.WIKILINK)
            db_session.flush()

        assert link.source_id == docs[0].id
        assert link.target_id == docs[1].id

    def test_upsert_creates(self, db_session, docs: list[Document]) -> None:
        """upsert() creates when no existing link."""
        with use_session(db_session):
            repo = DocumentLinkRepository()
            link = repo.upsert(docs[0].id, docs[1].id, DocumentLinkKind.WIKILINK)
            db_session.flush()

        assert link.source_id == docs[0].id
        assert link.relation == DocumentLinkKind.WIKILINK

    def test_upsert_updates(self, db_session, docs: list[Document]) -> None:
        """upsert() returns existing link if already present."""
        with use_session(db_session):
            repo = DocumentLinkRepository()
            link1 = repo.upsert(docs[0].id, docs[1].id, DocumentLinkKind.WIKILINK)
            db_session.flush()
            link2 = repo.upsert(docs[0].id, docs[1].id, DocumentLinkKind.WIKILINK)
            db_session.flush()

        assert link1 is link2

    def test_get_found(self, db_session, docs: list[Document]) -> None:
        """get() returns the link when it exists."""
        with use_session(db_session):
            repo = DocumentLinkRepository()
            repo.create(docs[0].id, docs[1].id, DocumentLinkKind.WIKILINK)
            db_session.flush()

            found = repo.get(docs[0].id, docs[1].id)

        assert found is not None
        assert found.relation == DocumentLinkKind.WIKILINK

    def test_get_not_found(self, db_session, docs: list[Document]) -> None:
        """get() returns None when link does not exist."""
        with use_session(db_session):
            repo = DocumentLinkRepository()
            found = repo.get(docs[0].id, docs[1].id)

        assert found is None

    def test_list_outgoing(self, db_session, docs: list[Document]) -> None:
        """list_outgoing() returns all links from a source document."""
        with use_session(db_session):
            repo = DocumentLinkRepository()
            repo.create(docs[0].id, docs[1].id, DocumentLinkKind.WIKILINK)
            repo.create(docs[0].id, docs[2].id, DocumentLinkKind.WIKILINK)
            db_session.flush()

            outgoing = repo.list_outgoing(docs[0].id)

        assert len(outgoing) == 2
        target_ids = {l.target_id for l in outgoing}
        assert target_ids == {docs[1].id, docs[2].id}

    def test_list_incoming(self, db_session, docs: list[Document]) -> None:
        """list_incoming() returns all links pointing to a target document."""
        with use_session(db_session):
            repo = DocumentLinkRepository()
            repo.create(docs[0].id, docs[2].id, DocumentLinkKind.WIKILINK)
            repo.create(docs[1].id, docs[2].id, DocumentLinkKind.WIKILINK)
            db_session.flush()

            incoming = repo.list_incoming(docs[2].id)

        assert len(incoming) == 2
        source_ids = {l.source_id for l in incoming}
        assert source_ids == {docs[0].id, docs[1].id}

    def test_delete_outgoing(self, db_session, docs: list[Document]) -> None:
        """delete_outgoing() clears all outgoing links from a source."""
        with use_session(db_session):
            repo = DocumentLinkRepository()
            repo.create(docs[0].id, docs[1].id, DocumentLinkKind.WIKILINK)
            repo.create(docs[0].id, docs[2].id, DocumentLinkKind.WIKILINK)
            db_session.flush()

            deleted = repo.delete_outgoing(docs[0].id)

        assert deleted == 2
        remaining = db_session.execute(select(DocumentLink)).scalars().all()
        assert len(remaining) == 0

    def test_delete_outgoing_no_links(self, db_session, docs: list[Document]) -> None:
        """delete_outgoing() returns 0 when no links exist."""
        with use_session(db_session):
            repo = DocumentLinkRepository()
            deleted = repo.delete_outgoing(docs[0].id)

        assert deleted == 0

    def test_delete_by_parent(self, db_session, dataset: Dataset, docs: list[Document]) -> None:
        """delete_by_parent() removes all links involving documents in a dataset."""
        with use_session(db_session):
            repo = DocumentLinkRepository()
            repo.create(docs[0].id, docs[1].id, DocumentLinkKind.WIKILINK)
            repo.create(docs[1].id, docs[2].id, DocumentLinkKind.WIKILINK)
            db_session.flush()

            deleted = repo.delete_by_parent(dataset.id)

        assert deleted == 2
        remaining = db_session.execute(select(DocumentLink)).scalars().all()
        assert len(remaining) == 0
