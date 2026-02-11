"""SQLAlchemy ORM models for Classifier entities.

This module defines the database schema for the document classification system using
SQLAlchemy 2.x with Advanced Alchemy patterns.

Models:
    - TopicSuggestion: Classifier-generated suggestions for linking text to topics
    - Match: External entity mappings for topics and taxonomies
    - DocumentClassification: LLM-based classification of documents into taxonomies
    - DocumentTopicAssignment: Assignment of documents to topics within classifications
"""


from sqlalchemy import (
    JSON,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ontologizer.relational.database import IdBase, JSONDict


class TopicSuggestion(IdBase):
    """Classifier-generated suggestion for linking input text to a topic.

    This table stores classifier-generated suggestions linking free-form text
    inputs to existing topics along with confidence scores and provenance.
    """

    __tablename__ = "topic_suggestion"
    __table_args__ = (
        UniqueConstraint(
            "input_hash",
            "topic_id",
            "model_name",
            "model_version",
            name="uq_suggestion_input_topic_model",
        ),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0", name="ck_suggestion_confidence"
        ),
        Index("ix_suggestion_input_hash", "input_hash"),
        Index("ix_suggestion_topic_id", "topic_id"),
        Index("ix_suggestion_taxonomy_id", "taxonomy_id"),
    )

    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    taxonomy_id: Mapped[str | None] = mapped_column(
        ForeignKey("taxonomy.id", ondelete="SET NULL"), nullable=True
    )
    topic_id: Mapped[str] = mapped_column(
        ForeignKey("topic.id", ondelete="CASCADE"), nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[int] = mapped_column(nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    context: Mapped[JSONDict] = mapped_column(
        "metadata_json",
        JSON,
        nullable=False,
        default=dict,
        server_default="{}",
    )


class Match(IdBase):
    """External entity mapping for topics and taxonomies.

    Match records alignments between internal entities and external systems
    (e.g., Wikidata, external taxonomies), with confidence scores and evidence.

    Attributes:
        id: Unique identifier (UUID)
        entity_type: Type of entity being matched (topic, taxonomy)
        entity_id: ID of the internal entity
        system: External system name (e.g., 'wikidata', 'dbpedia')
        external_id: ID in the external system
        match_type: Type of match (exactMatch, closeMatch, broadMatch, narrowMatch, relatedMatch)
        confidence: Confidence score (0.0 to 1.0)
        evidence: JSON object with match evidence/provenance
        created_at: Timestamp when created (auto-managed)
        updated_at: Timestamp when last updated (auto-managed)
    """

    __tablename__ = "match"
    __table_args__ = (
        UniqueConstraint(
            "entity_type",
            "entity_id",
            "system",
            "external_id",
            name="uq_match_entity_system_external",
        ),
        CheckConstraint(
            "entity_type IN ('topic', 'taxonomy')", name="ck_match_entity_type"
        ),
        CheckConstraint(
            "match_type IN ('exactMatch', 'closeMatch', 'broadMatch', 'narrowMatch', 'relatedMatch')",
            name="ck_match_type",
        ),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0", name="ck_match_confidence"
        ),
        Index("ix_match_entity", "entity_type", "entity_id"),
        Index("ix_match_system", "system"),
    )

    # Entity reference
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_id: Mapped[str] = mapped_column(nullable=False)

    # External reference
    system: Mapped[str] = mapped_column(String(100), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Match properties
    match_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="exactMatch"
    )
    confidence: Mapped[float] = mapped_column(nullable=False, default=1.0)
    evidence: Mapped[JSONDict] = mapped_column(
        JSON, nullable=False, default=dict, server_default="{}"
    )

    def __repr__(self) -> str:
        return f"<Match(entity={self.entity_type}:{self.entity_id}, system='{self.system}', external_id='{self.external_id}')>"


class DocumentClassification(IdBase):
    """Classification of a document into a taxonomy.

    This stores the LLM's suggestion that a particular document
    belongs to a specific taxonomy, along with confidence and reasoning.

    Attributes:
        id: Unique identifier
        document_id: Reference to the document (could be catalog item, note, etc.)
        document_type: Type of document (from catalog.DocumentType)
        taxonomy_id: The suggested taxonomy
        confidence: Confidence score (0.0 to 1.0)
        reasoning: Optional explanation from LLM
        model_name: Which LLM was used (e.g., "claude-sonnet-4")
        model_version: Version/timestamp of model
        prompt_version: Version of prompt template used
        metadata: Additional structured data from LLM response
        user_feedback: Optional user correction (accepted/rejected/modified)
        created_at: When classification was performed
        updated_at: When record was last updated
    """

    __tablename__ = "document_classification"
    __table_args__ = (
        Index("idx_doc_classification_lookup", "document_id", "document_type"),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="check_confidence_range",
        ),
    )

    # Document reference - polymorphic to support multiple document types
    document_id: Mapped[str] = mapped_column(nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Taxonomy reference
    taxonomy_id: Mapped[str] = mapped_column(
        ForeignKey("taxonomy.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Classification metadata
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Model information
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)

    # Additional data
    meta: Mapped[JSONDict] = mapped_column(
        "metadata_json", JSON, nullable=False, default=dict, server_default="{}"
    )
    user_feedback: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Relationships
    taxonomy: Mapped["Taxonomy"] = relationship("Taxonomy", lazy="joined")  # noqa: F821

    topic_assignments: Mapped[list["DocumentTopicAssignment"]] = relationship(
        "DocumentTopicAssignment",
        back_populates="classification",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<DocumentClassification(id={self.id}, document_id={self.document_id}, taxonomy_id={self.taxonomy_id})>"


class DocumentTopicAssignment(IdBase):
    """Assignment of a document to a topic within a classification.

    This represents one of potentially multiple topic suggestions
    for a document within its classified taxonomy.

    Attributes:
        id: Unique identifier
        classification_id: Parent classification record
        topic_id: The suggested topic
        confidence: Confidence score for this specific topic
        rank: Ranking (1 = most confident)
        reasoning: Optional explanation from LLM
        metadata: Additional structured data
        user_feedback: Optional user correction
        created_at: When assignment was created
        updated_at: When record was last updated
    """

    __tablename__ = "document_topic_assignment"
    __table_args__ = (
        UniqueConstraint(
            "classification_id", "topic_id", name="uq_classification_topic"
        ),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="check_assignment_confidence_range",
        ),
        CheckConstraint("rank >= 1", name="check_rank_positive"),
        Index("idx_topic_lookup", "topic_id", "confidence"),
    )

    # Parent classification
    classification_id: Mapped[str] = mapped_column(
        ForeignKey("document_classification.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Topic reference
    topic_id: Mapped[str] = mapped_column(
        ForeignKey("topic.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Assignment metadata
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[int] = mapped_column(nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[JSONDict] = mapped_column(
        "metadata_json", JSON, nullable=False, default=dict, server_default="{}"
    )
    user_feedback: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Relationships
    classification: Mapped["DocumentClassification"] = relationship(
        "DocumentClassification",
        back_populates="topic_assignments",
    )

    topic: Mapped["Topic"] = relationship("Topic", lazy="joined")  # noqa: F821

    def __repr__(self) -> str:
        return f"<DocumentTopicAssignment(id={self.id}, classification_id={self.classification_id}, topic_id={self.topic_id}, rank={self.rank})>"


__all__ = [
    "TopicSuggestion",
    "Match",
    "DocumentClassification",
    "DocumentTopicAssignment",
]
