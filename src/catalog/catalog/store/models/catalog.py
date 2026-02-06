"""catalog.store.models.catalog - SQLAlchemy ORM models for the catalog database.

Defines the database schema for the Resource hierarchy using joined-table
polymorphic inheritance. All resource types (Dataset, Document, Catalog,
Collection, Bookmark, Repository) extend the Resource base class.

These models live in the catalog database (the primary database).
"""

import enum
import json
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

__all__ = [
    "CatalogBase",
    "Bookmark",
    "BookmarkLink",
    "BookmarkRelationKind",
    "Catalog",
    "CatalogEntry",
    "CatalogEntryRelationKind",
    "Collection",
    "CollectionMember",
    "Dataset",
    "Document",
    "DocumentKind",
    "DocumentLink",
    "DocumentLinkKind",
    "Repository",
    "RepositoryLink",
    "Resource",
    "ResourceKind",
]


class CatalogBase(DeclarativeBase):
    """SQLAlchemy declarative base for catalog database models."""

    pass


class ResourceKind(str, enum.Enum):
    """Polymorphic discriminator for the Resource hierarchy."""

    BOOKMARK = "bookmark"
    CATALOG = "catalog"
    COLLECTION = "collection"
    DATASET = "dataset"
    DOCUMENT = "document"
    REPOSITORY = "repository"


class DocumentKind(str, enum.Enum):
    """Classifies the origin/format of a Document."""

    CACHED_PAGE = "cached_page"
    VAULT_EXPORT = "vault_export"
    PDF = "pdf"
    OTHER = "other"


class CatalogEntryRelationKind(str, enum.Enum):
    """Describes how a resource relates to its catalog."""

    BOOKMARK = "bookmark"
    COLLECTION = "collection"
    DATASET = "dataset"
    OTHER = "other"
    REPOSITORY = "repository"


class BookmarkRelationKind(str, enum.Enum):
    """Describes how a bookmark relates to a resource."""

    DERIVED_FROM = "derived_from"
    RELEVANT_TO = "relevant_to"
    SOURCE_FOR = "source_for"


class DocumentLinkKind(str, enum.Enum):
    """Describes the type of link between two documents."""

    WIKILINK = "wikilink"
    MARKDOWN_LINK = "markdown_link"


# ---------------------------------------------------------------------------
# Resource base class (joined-table inheritance root)
# ---------------------------------------------------------------------------


class Resource(CatalogBase):
    """Base class for all catalog resources using joined-table inheritance.

    Table ``resources`` stores the common fields shared by all resource types.
    Subclasses store type-specific columns in their own tables joined via FK.

    Attributes:
        id: Primary key.
        kind: Polymorphic discriminator.
        uri: Unique URI identifying the resource.
        title: Optional human-readable title.
        description: Optional longer description.
        created_at: When the resource was created.
        updated_at: When the resource was last modified.
        documents: Child documents linked via ``Document.parent_id``.
    """

    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[ResourceKind] = mapped_column(Enum(ResourceKind), nullable=False)
    uri: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    documents: Mapped[list["Document"]] = relationship(
        "Document",
        foreign_keys="[Document.parent_id]",
        back_populates="parent_resource",
        cascade="all, delete-orphan",
    )

    __mapper_args__ = {
        "polymorphic_on": "kind",
    }

    def __repr__(self) -> str:
        return f"<Resource(id={self.id}, kind='{self.kind}', uri='{self.uri}')>"


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------


class Dataset(Resource):
    """A data source (e.g. directory, Obsidian vault) that has been indexed.

    Attributes:
        id: FK to ``resources.id``.
        name: Unique slug identifier for the dataset.
        source_type: Type of source ("directory", "obsidian", etc.).
        source_path: Filesystem path to the source.
    """

    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(ForeignKey("resources.id"), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_path: Mapped[str] = mapped_column(String(1024), nullable=False)

    __mapper_args__ = {
        "polymorphic_identity": ResourceKind.DATASET,
    }

    def __repr__(self) -> str:
        return f"<Dataset(id={self.id}, name='{self.name}', source_type='{self.source_type}')>"


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------


class Document(Resource):
    """An indexed document within a parent resource (typically a Dataset).

    ``parent_id`` replaces the old ``dataset_id`` and points to any owning
    Resource. Requires explicit ``inherit_condition`` because both ``id`` and
    ``parent_id`` are FKs to ``resources.id``.

    Attributes:
        id: FK to ``resources.id``.
        parent_id: FK to owning resource (Dataset, Catalog, etc.).
        doc_type: Classifies the document origin/format.
        path: Relative path within the parent source.
        active: Whether the document is active (False = soft-deleted).
        content_hash: SHA256 hash of the document content.
        etag: Source-provided etag for change detection.
        last_modified: Source-provided modification time.
        body: Full normalized text content for FTS and chunking.
        metadata_json: Extracted metadata as JSON.
        parent_resource: Relationship to owning Resource.
    """

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(ForeignKey("resources.id"), primary_key=True)
    parent_id: Mapped[int] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    doc_type: Mapped[DocumentKind] = mapped_column(
        Enum(DocumentKind), nullable=False, default=DocumentKind.OTHER
    )
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_modified: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    parent_resource: Mapped["Resource"] = relationship(
        "Resource",
        foreign_keys=[parent_id],
        back_populates="documents",
    )

    outgoing_links: Mapped[list["DocumentLink"]] = relationship(
        "DocumentLink",
        foreign_keys="[DocumentLink.source_id]",
        cascade="all, delete-orphan",
    )
    incoming_links: Mapped[list["DocumentLink"]] = relationship(
        "DocumentLink",
        foreign_keys="[DocumentLink.target_id]",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_documents_parent_path", "parent_id", "path", unique=True),
        Index("ix_documents_parent_active", "parent_id", "active"),
        Index("ix_documents_content_hash", "content_hash"),
    )

    __mapper_args__ = {
        "polymorphic_identity": ResourceKind.DOCUMENT,
        "inherit_condition": id == Resource.id,
    }

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, path='{self.path}', active={self.active})>"

    def get_metadata(self) -> dict[str, Any]:
        """Parse and return metadata as a dictionary.

        Returns:
            Parsed metadata dictionary, or empty dict if no metadata.
        """
        if not self.metadata_json:
            return {}
        try:
            return json.loads(self.metadata_json)
        except json.JSONDecodeError:
            return {}

    def set_metadata(self, value: dict[str, Any]) -> None:
        """Set metadata from a dictionary.

        Args:
            value: Metadata dictionary to serialize.
        """
        self.metadata_json = json.dumps(value)


# ---------------------------------------------------------------------------
# DocumentLink
# ---------------------------------------------------------------------------


class DocumentLink(CatalogBase):
    """A directed link between two documents (e.g. an Obsidian wikilink).

    Uses composite primary key ``(source_id, target_id)`` matching the
    pattern established by ``BookmarkLink`` and ``RepositoryLink``.

    Attributes:
        source_id: FK to the linking document.
        target_id: FK to the linked-to document.
        relation: The kind of link (e.g. wikilink).
        source: Relationship to the source Document.
        target: Relationship to the target Document.
    """

    __tablename__ = "document_links"

    source_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    target_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    relation: Mapped[DocumentLinkKind] = mapped_column(
        Enum(DocumentLinkKind), nullable=False
    )

    source: Mapped["Document"] = relationship(
        "Document", foreign_keys=[source_id], overlaps="outgoing_links"
    )
    target: Mapped["Document"] = relationship(
        "Document", foreign_keys=[target_id], overlaps="incoming_links"
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentLink(source_id={self.source_id}, "
            f"target_id={self.target_id}, relation='{self.relation}')>"
        )


# ---------------------------------------------------------------------------
# Catalog + CatalogEntry
# ---------------------------------------------------------------------------


class Catalog(Resource):
    """A DCAT Catalog: a curated collection of resource descriptions.

    Attributes:
        id: FK to ``resources.id``.
        homepage: Optional homepage URL for the catalog.
        entries: Relationship to CatalogEntry association objects.
    """

    __tablename__ = "catalogs"

    id: Mapped[int] = mapped_column(ForeignKey("resources.id"), primary_key=True)
    homepage: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    entries: Mapped[list["CatalogEntry"]] = relationship(
        "CatalogEntry",
        back_populates="catalog",
        cascade="all, delete-orphan",
    )

    __mapper_args__ = {
        "polymorphic_identity": ResourceKind.CATALOG,
    }

    def __repr__(self) -> str:
        return f"<Catalog(id={self.id}, uri='{self.uri}')>"


class CatalogEntry(CatalogBase):
    """Associates a Catalog with a Resource.

    Attributes:
        id: Primary key.
        catalog_id: FK to ``catalogs.id``.
        resource_id: FK to ``resources.id``.
        relation: The relationship type between catalog and resource.
        created_at: When this entry was created.
        created_by: Optional author of the entry.
    """

    __tablename__ = "catalog_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    catalog_id: Mapped[int] = mapped_column(
        ForeignKey("catalogs.id", ondelete="CASCADE"), nullable=False
    )
    resource_id: Mapped[int] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"), nullable=False
    )
    relation: Mapped[CatalogEntryRelationKind] = mapped_column(
        Enum(CatalogEntryRelationKind), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    catalog: Mapped["Catalog"] = relationship(
        "Catalog", foreign_keys=[catalog_id], back_populates="entries"
    )
    resource: Mapped["Resource"] = relationship("Resource", foreign_keys=[resource_id])

    __table_args__ = (
        Index(
            "ix_catalog_entries_catalog_resource",
            "catalog_id",
            "resource_id",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<CatalogEntry(id={self.id}, catalog_id={self.catalog_id}, "
            f"resource_id={self.resource_id}, relation='{self.relation}')>"
        )


# ---------------------------------------------------------------------------
# Collection + CollectionMember
# ---------------------------------------------------------------------------


class Collection(Resource):
    """A referential grouping of resources. Does not own its members.

    Attributes:
        id: FK to ``resources.id``.
        members: Relationship to CollectionMember association objects.
    """

    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(ForeignKey("resources.id"), primary_key=True)

    members: Mapped[list["CollectionMember"]] = relationship(
        "CollectionMember",
        back_populates="collection",
        cascade="all, delete-orphan",
    )

    __mapper_args__ = {
        "polymorphic_identity": ResourceKind.COLLECTION,
    }

    def __repr__(self) -> str:
        return f"<Collection(id={self.id}, uri='{self.uri}')>"


class CollectionMember(CatalogBase):
    """Associates a Collection with a Resource.

    Attributes:
        id: Primary key.
        collection_id: FK to ``collections.id``.
        resource_id: FK to ``resources.id``.
        created_at: When this membership was created.
    """

    __tablename__ = "collection_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    collection_id: Mapped[int] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), nullable=False
    )
    resource_id: Mapped[int] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    collection: Mapped["Collection"] = relationship(
        "Collection", foreign_keys=[collection_id], back_populates="members"
    )
    resource: Mapped["Resource"] = relationship("Resource", foreign_keys=[resource_id])

    __table_args__ = (
        Index(
            "ix_collection_members_coll_resource",
            "collection_id",
            "resource_id",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<CollectionMember(id={self.id}, collection_id={self.collection_id}, "
            f"resource_id={self.resource_id})>"
        )


# ---------------------------------------------------------------------------
# Bookmark + BookmarkLink
# ---------------------------------------------------------------------------


class Bookmark(Resource):
    """A catalogued external URL.

    Attributes:
        id: FK to ``resources.id``.
        url: The bookmarked URL.
        favicon_url: Optional favicon URL.
        owner: Owner of the bookmark.
        folder: Optional folder/category.
        is_archived: Whether the bookmark is archived.
        resource_links: Relationship to BookmarkLink association objects.
    """

    __tablename__ = "bookmarks"

    id: Mapped[int] = mapped_column(ForeignKey("resources.id"), primary_key=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    favicon_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    folder: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    resource_links: Mapped[list["BookmarkLink"]] = relationship(
        "BookmarkLink",
        back_populates="bookmark",
        cascade="all, delete-orphan",
    )

    __mapper_args__ = {
        "polymorphic_identity": ResourceKind.BOOKMARK,
    }

    def __repr__(self) -> str:
        return f"<Bookmark(id={self.id}, url='{self.url}')>"


class BookmarkLink(CatalogBase):
    """Relates a Bookmark to any Resource.

    Uses composite primary key (bookmark_id, resource_id).

    Attributes:
        bookmark_id: FK to ``bookmarks.id``.
        resource_id: FK to ``resources.id``.
        relation: The relationship type.
    """

    __tablename__ = "bookmark_links"

    bookmark_id: Mapped[int] = mapped_column(
        ForeignKey("bookmarks.id", ondelete="CASCADE"), primary_key=True
    )
    resource_id: Mapped[int] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True
    )
    relation: Mapped[BookmarkRelationKind] = mapped_column(
        Enum(BookmarkRelationKind), nullable=False
    )

    bookmark: Mapped["Bookmark"] = relationship(
        "Bookmark", foreign_keys=[bookmark_id], back_populates="resource_links"
    )
    resource: Mapped["Resource"] = relationship("Resource", foreign_keys=[resource_id])

    def __repr__(self) -> str:
        return (
            f"<BookmarkLink(bookmark_id={self.bookmark_id}, "
            f"resource_id={self.resource_id}, relation='{self.relation}')>"
        )


# ---------------------------------------------------------------------------
# Repository + RepositoryLink
# ---------------------------------------------------------------------------


class Repository(Resource):
    """A code or content repository.

    Attributes:
        id: FK to ``resources.id``.
        host: Hosting platform (e.g. "github", "gitlab").
        repo_full_name: Full repository name (e.g. "owner/repo").
        default_branch: Default branch name.
        web_url: Web URL for the repository.
        resource_links: Relationship to RepositoryLink association objects.
    """

    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(ForeignKey("resources.id"), primary_key=True)
    host: Mapped[str | None] = mapped_column(String(100), nullable=True)
    repo_full_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    default_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    web_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    resource_links: Mapped[list["RepositoryLink"]] = relationship(
        "RepositoryLink",
        back_populates="repository",
        cascade="all, delete-orphan",
    )

    __mapper_args__ = {
        "polymorphic_identity": ResourceKind.REPOSITORY,
    }

    def __repr__(self) -> str:
        return f"<Repository(id={self.id}, repo_full_name='{self.repo_full_name}')>"


class RepositoryLink(CatalogBase):
    """Relates a Repository to any Resource.

    Uses composite primary key (repository_id, resource_id).

    Attributes:
        repository_id: FK to ``repositories.id``.
        resource_id: FK to ``resources.id``.
        relation: The relationship type (free-form string).
    """

    __tablename__ = "repository_links"

    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), primary_key=True
    )
    resource_id: Mapped[int] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True
    )
    relation: Mapped[str] = mapped_column(String(100), nullable=False)

    repository: Mapped["Repository"] = relationship(
        "Repository", foreign_keys=[repository_id], back_populates="resource_links"
    )
    resource: Mapped["Resource"] = relationship("Resource", foreign_keys=[resource_id])

    def __repr__(self) -> str:
        return (
            f"<RepositoryLink(repository_id={self.repository_id}, "
            f"resource_id={self.resource_id}, relation='{self.relation}')>"
        )
