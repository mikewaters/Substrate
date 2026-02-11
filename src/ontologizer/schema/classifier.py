"""Pydantic schemas for Classifier I/O.

These schemas are used for API request/response validation and serialization.
They are separate from domain models (attrs) and database models (SQLAlchemy).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TopicSuggestionRequest(BaseModel):
    """Request payload for topic suggestions."""

    text: str = Field(..., min_length=1, description="Input text to classify.")
    taxonomy_id: str | None = Field(
        None, description="Optional taxonomy scope for suggestions."
    )
    limit: int = Field(
        default=5, ge=1, le=20, description="Maximum number of suggestions to return."
    )
    min_confidence: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Minimum confidence required to include a suggestion.",
    )


class TopicSuggestionResult(BaseModel):
    """Single suggestion item returned to clients."""

    topic_id: str = Field(..., description="Suggested topic ID.")
    taxonomy_id: str = Field(..., description="Taxonomy containing the topic.")
    title: str = Field(..., description="Topic title.")
    slug: str = Field(..., description="Topic slug.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score.")
    rank: int = Field(..., ge=1, description="Rank order (1 = best).")
    metadata: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Additional metadata for the suggestion.",
    )


class TopicSuggestionResponse(BaseModel):
    """Response payload for topic suggestions."""

    input_text: str = Field(..., description="Original input text.")
    suggestions: list[TopicSuggestionResult] = Field(
        default_factory=list, description="Ordered list of topic suggestions."
    )
    model_name: str = Field(..., description="Classifier implementation name.")
    model_version: str = Field(..., description="Classifier version.")


# Document Classification Schemas


class DocumentClassificationRequest(BaseModel):
    """Request to classify a document into taxonomy and topics.

    The user provides the document content and optional constraints.
    The system will suggest taxonomy first, then topics within that taxonomy.
    """

    content: str = Field(
        ...,
        min_length=1,
        max_length=50000,
        description="Document content to classify",
    )

    document_id: str | None = Field(
        None, description="Optional document ID if classifying existing document"
    )

    document_type: str | None = Field(
        None, description="Type of document (Note, Document, etc.)"
    )

    taxonomy_hint: str | None = Field(
        None, description="Optional taxonomy hint to scope the classification"
    )

    max_topics: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of topics to suggest",
    )

    min_confidence: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for suggestions",
    )

    store_result: bool = Field(
        default=True, description="Whether to persist the classification result"
    )


class TaxonomyClassificationRequest(BaseModel):
    """Request to classify content into a taxonomy only.

    Use this when you only need taxonomy suggestion without topics.
    """

    content: str = Field(..., min_length=1, max_length=50000)
    top_k: int = Field(
        default=3, ge=1, le=10, description="Number of taxonomy suggestions"
    )
    min_confidence: float = Field(default=0.2, ge=0.0, le=1.0)


class FeedbackRequest(BaseModel):
    """User feedback on a classification result."""

    classification_id: str
    feedback: Literal["accepted", "rejected", "modified"]
    corrected_taxonomy_id: str | None = None
    corrected_topic_ids: list[str] | None = None
    notes: str | None = None


class TaxonomySuggestion(BaseModel):
    """A single taxonomy suggestion with confidence."""

    taxonomy_id: str  # This is the CURIE
    taxonomy_title: str
    taxonomy_description: str | None
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str | None = None


class TopicSuggestion(BaseModel):
    """A single topic suggestion with confidence and rank."""

    topic_id: str  # This is the CURIE
    topic_title: str
    topic_description: str | None
    confidence: float = Field(..., ge=0.0, le=1.0)
    rank: int = Field(..., ge=1)
    reasoning: str | None = None


class DocumentClassificationResponse(BaseModel):
    """Complete classification response including taxonomy and topics."""

    model_config = ConfigDict(from_attributes=True)

    # Request context
    content_preview: str = Field(..., description="First 200 chars of content")
    document_id: str | None = None
    document_type: str | None = None

    # Primary taxonomy suggestion
    suggested_taxonomy: TaxonomySuggestion

    # Alternative taxonomies (if requested via top_k)
    alternative_taxonomies: list[TaxonomySuggestion] = Field(default_factory=list)

    # Topic suggestions within the primary taxonomy
    suggested_topics: list[TopicSuggestion] = Field(default_factory=list)

    # Model metadata
    model_name: str
    model_version: str
    prompt_version: str

    # Persistence
    classification_id: str | None = Field(
        None, description="ID of stored classification if persisted"
    )

    created_at: datetime


class TaxonomyClassificationResponse(BaseModel):
    """Response for taxonomy-only classification."""

    content_preview: str
    suggestions: list[TaxonomySuggestion]
    model_name: str
    model_version: str
    created_at: datetime


class ClassificationHistoryResponse(BaseModel):
    """Historical classification results for a document."""

    document_id: str
    document_type: str
    classifications: list[DocumentClassificationResponse]
    total: int


# Parent Suggestion Schemas (FEAT-006)


class ParentSuggestionRequest(BaseModel):
    """Request to suggest parent topics for a topic."""

    topic_id: str = Field(..., description="Topic to find parents for")
    candidate_parent_ids: list[str] | None = Field(
        None,
        description="Optional list of candidate parent IDs to evaluate. If not provided, will search all topics in the taxonomy.",
    )


class ParentSuggestion(BaseModel):
    """A single parent topic suggestion."""

    parent_topic_id: str = Field(..., description="Suggested parent topic ID (CURIE)")
    parent_topic_title: str = Field(..., description="Parent topic title")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    reasoning: str = Field(..., description="Explanation for the suggestion")


__all__ = [
    "TopicSuggestionRequest",
    "TopicSuggestionResult",
    "TopicSuggestionResponse",
    "DocumentClassificationRequest",
    "TaxonomyClassificationRequest",
    "FeedbackRequest",
    "TaxonomySuggestion",
    "TopicSuggestion",
    "DocumentClassificationResponse",
    "TaxonomyClassificationResponse",
    "ClassificationHistoryResponse",
    "ParentSuggestionRequest",
    "ParentSuggestion",
]
