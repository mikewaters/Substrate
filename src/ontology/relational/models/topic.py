"""SQLAlchemy ORM models for Topic and Taxonomy entities.

This module defines the database schema for the topic/taxonomy system using
SQLAlchemy 2.x with Advanced Alchemy patterns.

Models:
    - Taxonomy: A collection of related topics
    - Topic: A specific concept within a taxonomy
    - TopicEdge: Relationships between topics
    - TopicClosure: Transitive closure table for hierarchy traversal
    - Match: External entity mappings for topics and taxonomies
"""

from datetime import datetime, UTC
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ontology.relational.database import CURIEBase, IdBase, JSONDict
from ontology.domain import TAXONOMY_DEFAULT_NAMESPACE_PREFIX
from ontology.utils.slug import (
    generate_identifier,
    generate_slug,
    split_namespace,
)

# Import association tables from catalog module (late import to avoid circular dependency)
if TYPE_CHECKING:
    from ontology.relational.models.catalog import (
        Catalog,
        Resource,
    )
else:
    # At runtime, we need the actual table objects for the relationships
    try:
        from ontology.relational.models.catalog import catalog_taxonomies, resource_related_topics
    except ImportError:
        # If catalog module isn't available yet, set to None
        # SQLAlchemy will still try to resolve the string reference
        resource_related_topics = None  # type: ignore
        catalog_taxonomies = None  # type: ignore


class Taxonomy(CURIEBase):
    """A collection of related topics forming a taxonomy.

    Taxonomies provide organizational structure for topics, such as
    'Software Development', 'Health', etc.

    Attributes:
        id: Unique identifier (UUID)
        title: Human-readable title
        description: Optional longer description
        skos_uri: Optional SKOS URI for alignment with SKOS vocabularies
        catalogs: Related Catalog instances (many-to-many relationship)
        created_at: Timestamp when created (auto-managed)
        updated_at: Timestamp when last updated (auto-managed)
    """

    __tablename__ = "taxonomy"
    _curie_namespace_prefix = TAXONOMY_DEFAULT_NAMESPACE_PREFIX

    # Primary fields
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    skos_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    topics: Mapped[list["Topic"]] = relationship(
        "Topic",
        back_populates="taxonomy",
        cascade="all, delete-orphan",
        passive_deletes=False,  # True,
        # lazy='raise'
    )

    catalogs: Mapped[list["Catalog"]] = relationship(  # noqa: F821
        "Catalog",
        secondary="catalog_taxonomies",  # Use string reference to avoid import order issues
        back_populates="taxonomies",
        lazy="selectin",  # Use eager loading for async compatibility
    )

    def __repr__(self) -> str:
        return f"<Taxonomy(id={self.id}, title='{self.title}')>"

    @hybrid_property
    def namespace(self):
        """Split the instance's id into [namespace, id] components"""
        return split_namespace(self.id)


class Topic(CURIEBase):
    """A specific concept within a taxonomy.

    Topics represent individual concepts that can be organized hierarchically
    within a taxonomy.

    Attributes:
        id: Unique identifier (UUID)
        taxonomy_id: Foreign key to parent taxonomy
        title: Human-readable title
        slug: URL-friendly identifier (unique within taxonomy)
        description: Optional longer description
        status: Current status (draft, active, deprecated, merged)
        aliases: List of alternative names
        external_refs: Dictionary of external system references
        path: Materialized path for hierarchy display
        created_at: Timestamp when created (auto-managed)
        updated_at: Timestamp when last updated (auto-managed)
    """

    __tablename__ = "topic"
    __table_args__ = (
        UniqueConstraint("taxonomy_id", "slug", name="uq_topic_taxonomy_slug"),
        ## We require the title to be unique within a taxonomy, given `slug`
        # may be computed from the title (and should be unique); this just helps us raise
        # exceptions earlier, before the `before_insert` hook tries to generate slug.
        UniqueConstraint("taxonomy_id", "title", name="uq_topic_taxonomy_title"),
        CheckConstraint(
            "status IN ('draft', 'active', 'deprecated', 'merged')",
            name="ck_topic_status",
        ),
        Index("ix_topic_taxonomy_id", "taxonomy_id"),
        Index("ix_topic_slug", "slug"),
        Index("ix_topic_title", "title"),
        Index("ix_topic_status", "status"),
        Index("ix_topic_taxonomy_status", "taxonomy_id", "status"),
        Index("ix_topic_created_at", "created_at"),
        Index("ix_topic_path", "path"),
    )

    # Foreign keys
    taxonomy_id: Mapped[str] = mapped_column(
        ForeignKey("taxonomy.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Primary fields
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")

    # JSON fields
    aliases: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
    external_refs: Mapped[JSONDict] = mapped_column(
        JSON, nullable=False, default=dict, server_default="{}"
    )

    # Materialized path
    path: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Relationships
    taxonomy: Mapped["Taxonomy"] = relationship(
        "Taxonomy",
        back_populates="topics",
        lazy="joined",  # required for async relationship loading; lazy no worky
    )

    # Parent/child edges
    parent_edges: Mapped[list["TopicEdge"]] = relationship(
        "TopicEdge",
        foreign_keys="TopicEdge.child_id",
        back_populates="child",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    child_edges: Mapped[list["TopicEdge"]] = relationship(
        "TopicEdge",
        foreign_keys="TopicEdge.parent_id",
        back_populates="parent",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Cross-module relationship to catalog resources
    related_resources: Mapped[list["Resource"]] = relationship(  # noqa: F821
        "Resource",
        secondary="resource_related_topics",  # Use string reference to avoid import order issues
        back_populates="related_topics",
        lazy="noload",  # Don't load automatically to match Resource side
        viewonly=True,  # Read-only to match Resource side
    )

    def __repr__(self) -> str:
        return f"<Topic(id={self.id}, title='{self.title}', slug='{self.slug}')>"


class TopicEdge(IdBase):
    """A relationship between two topics (parent → child).

    TopicEdge represents directed relationships between topics, supporting
    various relationship types aligned with SKOS.

    Attributes:
        id: Unique identifier (UUID)
        parent_id: Foreign key to parent topic
        child_id: Foreign key to child topic
        role: Relationship type (broader, part_of, instance_of, related)
        source: Where this relationship came from
        confidence: Confidence score (0.0 to 1.0)
        created_at: Timestamp when created
    """

    __tablename__ = "topic_edge"
    __table_args__ = (
        UniqueConstraint("parent_id", "child_id", name="uq_edge_parent_child"),
        CheckConstraint("parent_id != child_id", name="ck_edge_no_self_loop"),
        CheckConstraint(
            "role IN ('broader', 'part_of', 'instance_of', 'related')",
            name="ck_edge_role",
        ),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0", name="ck_edge_confidence"
        ),
        Index("ix_edge_parent_id", "parent_id"),
        Index("ix_edge_child_id", "child_id"),
        Index("ix_edge_role", "role"),
    )

    # Foreign keys
    parent_id: Mapped[str] = mapped_column(
        ForeignKey("topic.id", ondelete="CASCADE"),
        nullable=False,
    )
    child_id: Mapped[str] = mapped_column(
        ForeignKey("topic.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Edge properties
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="broader")
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confidence: Mapped[float] = mapped_column(nullable=False, default=1.0)
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    # Relationships
    parent: Mapped["Topic"] = relationship(
        "Topic",
        foreign_keys=[parent_id],
        back_populates="child_edges",
    )
    child: Mapped["Topic"] = relationship(
        "Topic",
        foreign_keys=[child_id],
        back_populates="parent_edges",
    )

    def __repr__(self) -> str:
        return f"<TopicEdge(parent={self.parent_id}, child={self.child_id}, role='{self.role}')>"


class TopicClosure(IdBase):
    """Transitive closure table for topic hierarchies.

    TopicClosure maintains all ancestor-descendant relationships to enable
    efficient hierarchy traversal queries. This table is automatically
    maintained when edges are added or removed.

    Attributes:
        id: Unique identifier (UUID)
        ancestor_id: Foreign key to ancestor topic
        descendant_id: Foreign key to descendant topic
        depth: Number of edges between ancestor and descendant (0 = self)
    """

    __tablename__ = "topic_closure"
    __table_args__ = (
        UniqueConstraint(
            "ancestor_id", "descendant_id", name="uq_closure_ancestor_descendant"
        ),
        CheckConstraint("depth >= 0", name="ck_closure_depth"),
        Index("ix_closure_ancestor_id", "ancestor_id"),
        Index("ix_closure_descendant_id", "descendant_id"),
        Index("ix_closure_depth", "depth"),
    )

    # Foreign keys
    ancestor_id: Mapped[str] = mapped_column(
        ForeignKey("topic.id", ondelete="CASCADE"),
        nullable=False,
    )
    descendant_id: Mapped[str] = mapped_column(
        ForeignKey("topic.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Closure properties
    depth: Mapped[int] = mapped_column(nullable=False)

    def __repr__(self) -> str:
        return f"<TopicClosure(ancestor={self.ancestor_id}, descendant={self.descendant_id}, depth={self.depth})>"


"""
Event listener definitions
"""


class TopicInsufficientTaxonomyError(Exception):
    def __init__(self, topic: Topic) -> None:
        super().__init__(f"Topic {topic} has no valid taxonomy.")


@event.listens_for(Topic, "before_insert")
def topic_before_insert(mapper, connection, target):
    """Perform initialization before a topic is inserted.

    Topic requires special handling because:
    1. Slug generation from title
    2. ID generation requires parent taxonomy's namespace (can't use base class approach)

    Note: This listener fires AFTER the CURIEBase listener, so we only handle
    Topic-specific logic here. The ID generation uses the parent taxonomy's
    namespace rather than a fixed prefix.
    """
    # Bail early if required field isn't present
    if not target.title:
        return

    # Generate a slug for any instance that doesn't have one
    if not target.slug:
        target.slug = generate_slug(target.title)

    # Generate CURIE-based id if not already set
    # Topic IDs use parent taxonomy namespace (e.g., "tech:python" for taxonomy "tx:tech")
    if not target.id:
        if not target.taxonomy_id:
            raise TopicInsufficientTaxonomyError(target)

        # Extract namespace from taxonomy_id (e.g., "tx:tech" -> "tech")
        parent_namespace = split_namespace(target.taxonomy_id)[1]
        target.id = generate_identifier(target.title, parent_namespace)
