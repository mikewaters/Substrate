"""SQLAlchemy ORM models for Catalog entities.

This module defines the database schema for the catalog system using
SQLAlchemy 2.x with Advanced Alchemy patterns.

Models:
    - Catalog: A group of similar Resource instances
    - Repository: The system that houses a resource
    - Purpose: Purpose/meaning relationships
    - Resource: Base class for information resources
    - Bookmark: A collected resource (URL with no content)
    - Collection: A group of Resources
    - Document: Larger container for authored documents
    - Note: Small data being ingested
"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ontology.relational.database import Base, CURIEBase
from ontology.domain import (
    CATALOG_DEFAULT_NAMESPACE_PREFIX,
    DEFAULT_NAMESPACE_PREFIXES,
    PURPOSE_DEFAULT_NAMESPACE_PREFIX,
    REPOSITORY_DEFAULT_NAMESPACE_PREFIX,
    RESOURCE_DEFAULT_NAMESPACE_PREFIX,
)
from ontology.relational.models.topic import Taxonomy, Topic

# Association table for catalog-to-taxonomy relationships
catalog_taxonomies = Table(
    "catalog_taxonomies",
    Base.metadata,
    Column(
        "catalog_id",
        ForeignKey("catalog.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "taxonomy_id",
        ForeignKey("taxonomy.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Index("ix_catalog_taxonomies_catalog", "catalog_id"),
    Index("ix_catalog_taxonomies_taxonomy", "taxonomy_id"),
)


class Catalog(CURIEBase):
    """A group of similar Resource instances around a theme or topic.

    Attributes:
        id: Unique identifier (UUID)
        identifier: Business identifier
        title: Human-readable title
        description: Optional longer description
        taxonomies: Related Taxonomy instances (many-to-many relationship)
        created_at: Timestamp when created (auto-managed)
        updated_at: Timestamp when last updated (auto-managed)
    """

    __tablename__ = "catalog"
    _curie_namespace_prefix = CATALOG_DEFAULT_NAMESPACE_PREFIX

    # Primary fields
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    resources: Mapped[list["Resource"]] = relationship(
        "Resource",
        back_populates="catalog_obj",
        cascade="all, delete-orphan",
        foreign_keys="Resource.catalog_id",
        lazy="selectin",  # Use eager loading for async compatibility
    )

    taxonomies: Mapped[list["Taxonomy"]] = relationship(  # noqa: F821
        "Taxonomy",
        secondary=catalog_taxonomies,
        back_populates="catalogs",
        lazy="selectin",  # Use eager loading for async compatibility
    )

    def __repr__(self) -> str:
        return f"<Catalog(id={self.id}, title='{self.title}')>"


class Repository(CURIEBase):
    """The system that houses a given resource.

    Attributes:
        id: Unique identifier (UUID)
        identifier: Business identifier
        title: Human-readable title
        service_name: The name of the app/service being used
        description: Optional longer description
        created_at: Timestamp when created (auto-managed)
        updated_at: Timestamp when last updated (auto-managed)
    """

    __tablename__ = "repository"
    _curie_namespace_prefix = REPOSITORY_DEFAULT_NAMESPACE_PREFIX

    # Primary fields
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    service_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    resources: Mapped[list["Resource"]] = relationship(
        "Resource",
        back_populates="repository_obj",
        foreign_keys="Resource.repository_id",
        lazy="selectin",  # Use eager loading for async compatibility
    )

    def __repr__(self) -> str:
        return f"<Repository(id={self.id}, title='{self.title}', service='{self.service_name}')>"


class Purpose(CURIEBase):
    """Purpose/meaning relationships.

    Attributes:
        id: Unique identifier (UUID)
        identifier: Business identifier
        title: Human-readable title
        description: Optional longer description
        role: Optional relationship type
        meaning: Optional meaning applied to the purpose
        created_at: Timestamp when created (auto-managed)
        updated_at: Timestamp when last updated (auto-managed)
    """

    __tablename__ = "purpose"
    _curie_namespace_prefix = PURPOSE_DEFAULT_NAMESPACE_PREFIX

    # Primary fields
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    meaning: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Purpose(id={self.id}, title='{self.title}')>"


# Association table for resource-to-resource relationships
resource_related_resources = Table(
    "resource_related_resources",
    Base.metadata,
    Column(
        "source_resource_id",
        ForeignKey("resource.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "related_resource_id",
        ForeignKey("resource.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Index("ix_resource_related_source", "source_resource_id"),
    Index("ix_resource_related_related", "related_resource_id"),
)


# Association table for resource-to-topic relationships
resource_related_topics = Table(
    "resource_related_topics",
    Base.metadata,
    Column(
        "resource_id",
        ForeignKey("resource.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "topic_id",
        ForeignKey("topic.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Index("ix_resource_topics_resource", "resource_id"),
    Index("ix_resource_topics_topic", "topic_id"),
)


class Resource(CURIEBase):
    """Base class for information resources.

    This is a single-table inheritance model where resource_type determines
    the specific subtype (Resource, Bookmark, Collection, Document, Note).

    Attributes:
        id: Unique identifier (UUID)
        identifier: Business identifier
        catalog_id: Foreign key to parent catalog
        catalog: Identifier of the catalog (business key)
        title: Human-readable title
        description: Optional longer description
        resource_type: Type discriminator
        location: Canonical URL in external repository
        repository_id: Optional foreign key to repository
        repository: Optional repository identifier (business key)
        content_location: Optional URL of content
        format: Optional file format
        media_type: Optional MIME type
        theme: Optional theme/topic identifier
        subject: Optional subject
        creator: Optional creator
        has_purpose: Optional purpose identifier
        has_use: List of use identifiers (JSON)
        has_resources: List of resource identifiers for Collections (JSON)
        related_resources: List of related resource identifiers (JSON)
        related_topics: List of related topic identifiers (JSON)
        document_type: Type of document (for Document resources)
        note_type: Type of note (for Note resources)
        created: Optional creation datetime
        modified: Optional modification datetime
        created_at: Timestamp when created (auto-managed)
        updated_at: Timestamp when last updated (auto-managed)

    Invariants (implementation):
        - `Document` instances default to document_type='Document'
        - `Note` instances default to note_type='Note'
        - `has_resources` can only be set for `Collection` type

    Invariants (domain):
        - Only `Document` instances can have a `document_type` value
        - Only `Note` instances can have a `note_type` value
        - Base `Resource` type requires `location` (URL to external resource)
        - All other resource types require `repository` (they live in a Repository)
        - Only `Collection` instances can have `has_resources`
    """

    __tablename__ = "resource"
    __table_args__ = (
        CheckConstraint(
            "resource_type IN ('Resource', 'Bookmark', 'Collection', 'Document', 'Note')",
            name="ck_resource_type",
        ),
        CheckConstraint(
            "document_type IS NULL OR resource_type = 'Document'",
            name="ck_document_type_only_for_documents",
        ),
        CheckConstraint(
            "note_type IS NULL OR resource_type = 'Note'",
            name="ck_note_type_only_for_notes",
        ),
        CheckConstraint(
            "(resource_type = 'Resource' AND location IS NOT NULL) OR "
            "(resource_type != 'Resource')",
            name="ck_location_required_for_base_resource",
        ),
        CheckConstraint(
            "(resource_type != 'Resource' AND repository IS NOT NULL) OR "
            "(resource_type = 'Resource')",
            name="ck_repository_required_for_typed_resources",
        ),
        CheckConstraint(
            "(has_resources = '[]' OR resource_type = 'Collection')",
            name="ck_has_resources_only_for_collections",
        ),
        Index("ix_resource_catalog_id", "catalog_id"),
        Index("ix_resource_repository_id", "repository_id"),
        Index("ix_resource_type", "resource_type"),
        Index("ix_resource_created", "created"),
        Index("ix_resource_modified", "modified"),
    )

    # Discriminator for single-table inheritance
    __mapper_args__ = {
        "polymorphic_identity": "Resource",
        "polymorphic_on": "resource_type",
    }

    _curie_namespace_prefix = RESOURCE_DEFAULT_NAMESPACE_PREFIX

    # Foreign keys
    catalog_id: Mapped[str] = mapped_column(
        ForeignKey("catalog.id", ondelete="CASCADE"),
        nullable=False,
    )
    repository_id: Mapped[str | None] = mapped_column(
        ForeignKey("repository.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Primary fields
    catalog: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Resource metadata
    location: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    repository: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_location: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    format: Mapped[str | None] = mapped_column(String(100), nullable=True)
    media_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    theme: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    creator: Mapped[str | None] = mapped_column(String(255), nullable=True)
    has_purpose: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # JSON fields for relationships and lists
    has_use: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
    has_resources: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )

    # Type-specific fields
    document_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    note_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Timestamps
    # NOTE: These refer to the original resource that this record points to,
    # whereas the in-built properties refer to the database record itself.
    created: Mapped[datetime | None] = mapped_column(nullable=True)
    modified: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationships
    catalog_obj: Mapped["Catalog"] = relationship(
        "Catalog", back_populates="resources", foreign_keys=[catalog_id]
    )
    repository_obj: Mapped["Repository | None"] = relationship(
        "Repository", back_populates="resources", foreign_keys=[repository_id]
    )

    # Many-to-many relationships
    # Using lazy="noload" to prevent automatic loading but still allow serialization
    related_resources: Mapped[list["Resource"]] = relationship(
        "Resource",
        secondary=resource_related_resources,
        primaryjoin="Resource.id == resource_related_resources.c.source_resource_id",
        secondaryjoin="Resource.id == resource_related_resources.c.related_resource_id",
        lazy="noload",  # Don't load automatically but return empty list
        viewonly=True,  # Read-only to avoid issues with self-referential relationships
    )

    related_topics: Mapped[list["Topic"]] = relationship(  # noqa: F821
        "Topic",
        secondary=resource_related_topics,
        back_populates="related_resources",  # Topics have related_resources, not related_topics
        lazy="noload",  # Don't load automatically but return empty list
        viewonly=True,  # Read-only for now
    )

    def __repr__(self) -> str:
        return f"<Resource(id={self.id}, title='{self.title}', type='{self.resource_type}')>"


class Bookmark(Resource):
    """A collected resource - a URL with no content.

    Inherits all fields from Resource with resource_type='Bookmark'.
    """

    __mapper_args__ = {
        "polymorphic_identity": "Bookmark",
    }

    _curie_namespace_prefix = DEFAULT_NAMESPACE_PREFIXES["Bookmark"]


class Collection(Resource):
    """A group of Resources centered around some need or theme.

    Inherits all fields from Resource with resource_type='Collection'.
    Uses has_resources field to store collection members.
    """

    __mapper_args__ = {
        "polymorphic_identity": "Collection",
    }

    _curie_namespace_prefix = DEFAULT_NAMESPACE_PREFIXES["Collection"]


class Document(Resource):
    """Larger container or promoted note; used only for documents authored by the Self.

    Inherits all fields from Resource with resource_type='Document'.
    Uses document_type field to specify the document type.
    """

    __mapper_args__ = {
        "polymorphic_identity": "Document",
    }

    _curie_namespace_prefix = DEFAULT_NAMESPACE_PREFIXES["Document"]


class Note(Resource):
    """Small data being ingested.

    Inherits all fields from Resource with resource_type='Note'.
    Uses note_type field to specify the note type.
    """

    __mapper_args__ = {
        "polymorphic_identity": "Note",
    }

    _curie_namespace_prefix = DEFAULT_NAMESPACE_PREFIXES["Note"]
