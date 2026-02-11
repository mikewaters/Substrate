"""Pydantic schemas for Topic and Taxonomy I/O.

These schemas are used for API request/response validation and serialization.
They are separate from domain models (attrs) and database models (SQLAlchemy).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TopicStatus = Literal["draft", "active", "deprecated", "merged"]
EdgeRole = Literal["broader", "part_of", "instance_of", "related"]


# Topic schema


class TopicBase(BaseModel):
    """Base schema for Topic with common fields.
    This should be a 1-1 repr of the domain requirements; subclasses will declare fields
    as optional based on input/output requirements"""

    taxonomy_id: str = Field(..., description="Parent taxonomy ID (CURIE)")
    title: str = Field(..., min_length=1, max_length=255, description="Topic title")
    slug: str = Field(
        ..., min_length=1, max_length=255, description="URL-friendly slug"
    )
    description: str | None = Field(None, description="Optional topic description")
    status: TopicStatus = Field(default="draft", description="Topic status")
    aliases: list[str] = Field(default_factory=list, description="Alternative names")
    external_refs: dict[str, str] = Field(
        default_factory=dict, description="External system references"
    )
    path: str | None = Field(None, description="Materialized path for hierarchy")


class TopicCreate(BaseModel):
    """Schema for creating a new topic.

    Used for API requests when creating a new topic.
    Slug is optional and will be auto-generated from title if not provided.
    """

    taxonomy_id: str
    title: str = Field(..., min_length=1, max_length=255)
    slug: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    status: TopicStatus = "draft"
    aliases: list[str] = Field(default_factory=list)
    external_refs: dict[str, str] = Field(default_factory=dict)


class TopicUpdate(BaseModel):
    """Schema for updating an existing topic.

    All fields are optional to support partial updates.
    """

    title: str | None = Field(None, min_length=1, max_length=255)
    slug: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    status: TopicStatus | None = None
    aliases: list[str] | None = None
    external_refs: dict[str, str] | None = None
    path: str | None = None


class TopicResponse(TopicBase):
    """Schema for topic responses.

    Used for API responses. Includes all fields including ID and timestamps.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique identifier (CURIE)")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class TopicListResponse(BaseModel):
    """Schema for paginated topic list responses."""

    items: list[TopicResponse] = Field(..., description="List of topics")
    total: int = Field(..., ge=0, description="Total count of topics")
    limit: int = Field(..., ge=1, description="Items per page")
    offset: int = Field(..., ge=0, description="Offset from start")


class TopicSearchRequest(BaseModel):
    """Schema for topic search requests."""

    query: str = Field(..., min_length=1, description="Search query")
    taxonomy_id: str | None = Field(None, description="Filter by taxonomy")
    status: TopicStatus | None = Field(None, description="Filter by status")
    limit: int = Field(default=50, ge=1, le=1000, description="Max results")
    offset: int = Field(default=0, ge=0, description="Result offset")


# Topic overview schemas (FEAT-016)


class TopicRelationshipRef(BaseModel):
    """Minimal representation of a related topic."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Topic identifier (CURIE)")
    title: str = Field(..., description="Human-readable topic title")
    status: TopicStatus = Field(..., description="Current status of the related topic")


class TopicOverview(BaseModel):
    """Topic data enriched with relationship details for UI rendering."""

    model_config = ConfigDict(from_attributes=True)

    topic: TopicResponse = Field(..., description="Full topic details")
    child_count: int = Field(
        ..., ge=0, description="Number of immediate children for this topic"
    )
    children: list[TopicRelationshipRef] = Field(
        default_factory=list,
        description="Immediate children (first page of children for quick display)",
    )
    parents: list[TopicRelationshipRef] = Field(
        default_factory=list, description="Immediate parents of this topic"
    )


class TopicOverviewListResponse(BaseModel):
    """Paginated list of topic overviews within a taxonomy."""

    items: list[TopicOverview] = Field(..., description="List of topic overviews")
    total: int = Field(..., ge=0, description="Total count of topics")
    limit: int = Field(..., ge=1, description="Items per page")
    offset: int = Field(..., ge=0, description="Offset from start")


# Edge schemas


class TopicEdgeBase(BaseModel):
    """Base schema for TopicEdge with common fields."""

    parent_id: str = Field(..., description="Parent topic ID")
    child_id: str = Field(..., description="Child topic ID")
    role: EdgeRole = Field(default="broader", description="Relationship type")
    source: str | None = Field(None, description="Source of relationship")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence score"
    )
    is_primary: bool = Field(
        default=False,
        description="Primary parent flag for materialized path maintenance",
    )


class TopicEdgeCreate(TopicEdgeBase):
    """Schema for creating a new topic edge."""

    pass


class TopicEdgeResponse(TopicEdgeBase):
    """Schema for topic edge responses."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")


class TopicSummaryResponse(BaseModel):
    """Aggregate summary of topics by status."""

    total: int = Field(..., ge=0, description="Total topics in scope.")
    by_status: dict[str, int] = Field(
        default_factory=dict,
        description="Counts keyed by status value.",
    )
    taxonomy_id: str | None = Field(
        None, description="Optional taxonomy scope for counts."
    )


class TopicCountsResponse(BaseModel):
    """Counts grouped by taxonomy."""

    class Entry(BaseModel):
        taxonomy_id: str = Field(..., description="Taxonomy identifier.")
        count: int = Field(..., ge=0, description="Number of topics in taxonomy.")

    total: int = Field(..., ge=0, description="Total topics across all taxonomies.")
    items: list[Entry] = Field(default_factory=list, description="Counts per taxonomy.")


class TopicRecentListResponse(BaseModel):
    """Recently created topics."""

    class Item(BaseModel):
        id: str
        taxonomy_id: str
        title: str
        slug: str
        path: str | None
        status: str
        created_at: datetime

    taxonomy_id: str | None = Field(
        None, description="Optional taxonomy scope for recent topics."
    )
    items: list[Item] = Field(default_factory=list)
