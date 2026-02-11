"""Pydantic schemas for Catalog I/O.

These schemas are used for API request/response validation and serialization.
They are separate from domain models (attrs) and database models (SQLAlchemy).
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer
from ontologizer.schema.utils import WithTimestamps, Page, partial_model

# Type aliases
DocumentType = Literal[
    "Document", "Journal", "List", "Notebook", "Logbook", "Inventory", "Landscape"
]
NoteType = Literal["Note", "Log", "Thought", "Idea", "Reference", "Highlight"]
ResourceType = Literal["Resource", "Bookmark", "Collection", "Document", "Note"]


# Catalog schemas (refactored)


class CatalogCreate(BaseModel):
    """Input DTO for create/replace operations for Catalog."""

    id: str = Field(..., min_length=1, max_length=255)
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, description="Optional description")
    taxonomies: list[str] = Field(
        default_factory=list, description="List of taxonomy identifiers"
    )


# Auto-derived update/patch model; all fields optional, constraints preserved
CatalogUpdate = partial_model("CatalogUpdate", CatalogCreate)


class CatalogResponse(WithTimestamps, CatalogCreate):
    """Response DTO with timestamps composed with the input fields."""

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("taxonomies")
    def serialize_taxonomies(self, taxonomies: Any) -> list[str]:
        """Serialize taxonomy relationship to list of identifiers.

        Args:
            taxonomies: Either a list of Taxonomy ORM objects or a list of strings

        Returns:
            List of taxonomy identifiers
        """
        if not taxonomies:
            return []

        # Handle case where taxonomies is already a list of strings
        if isinstance(taxonomies, list) and all(isinstance(t, str) for t in taxonomies):
            return taxonomies

        # Handle case where taxonomies is a list of ORM objects with id attribute
        return [t.id if hasattr(t, "id") else str(t) for t in taxonomies]


# Generic paging wrapper for catalogs
CatalogListResponse = Page[CatalogResponse]


# Repository schemas (refactored)


class RepositoryCreate(BaseModel):
    id: str = Field(..., min_length=1, max_length=255)
    title: str = Field(..., min_length=1, max_length=255)
    service_name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


RepositoryUpdate = partial_model("RepositoryUpdate", RepositoryCreate)


class RepositoryResponse(WithTimestamps, RepositoryCreate):
    model_config = ConfigDict(from_attributes=True)


RepositoryListResponse = Page[RepositoryResponse]


# Purpose schemas (refactored)


class PurposeCreate(BaseModel):
    id: str = Field(..., min_length=1, max_length=255)
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    role: str | None = None
    meaning: str | None = None


PurposeUpdate = partial_model("PurposeUpdate", PurposeCreate)


class PurposeResponse(WithTimestamps, PurposeCreate):
    model_config = ConfigDict(from_attributes=True)


PurposeListResponse = Page[PurposeResponse]


# Resource schemas


class ResourceBase(BaseModel):
    catalog: str = Field(..., min_length=1, max_length=255)
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    resource_type: ResourceType = "Resource"
    location: str | None = None
    repository: str | None = None
    content_location: str | None = None
    format: str | None = None
    media_type: str | None = None
    theme: str | None = None
    subject: str | None = None
    creator: str | None = None
    has_purpose: str | None = None
    has_use: list[str] = Field(default_factory=list)
    related_resources: list[str] = Field(default_factory=list)
    related_topics: list[str] = Field(default_factory=list)


class ResourceCreate(BaseModel):
    """Schema for creating a new resource.

    Base Resource type requires a location (URL to external resource).
    Typed resources (Document, Note, etc.) require a repository instead.
    """

    id: str = Field(..., min_length=1, max_length=255)
    catalog: str = Field(..., min_length=1, max_length=255)
    catalog_id: str
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    resource_type: ResourceType = "Resource"
    location: str = Field(..., description="Required for base Resource type")
    repository: str | None = None
    repository_id: str | None = None
    content_location: str | None = None
    format: str | None = None
    media_type: str | None = None
    theme: str | None = None
    subject: str | None = None
    creator: str | None = None
    has_purpose: str | None = None
    has_use: list[str] = Field(default_factory=list)
    related_resources: list[str] = Field(default_factory=list)
    related_topics: list[str] = Field(default_factory=list)


class ResourceUpdate(BaseModel):
    """Schema for updating an existing resource."""

    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    location: str | None = None
    repository: str | None = None
    content_location: str | None = None
    format: str | None = None
    media_type: str | None = None
    theme: str | None = None
    subject: str | None = None
    creator: str | None = None
    has_purpose: str | None = None
    has_use: list[str] | None = None
    related_resources: list[str] | None = None
    related_topics: list[str] | None = None


class ResourceResponse(WithTimestamps, ResourceBase):
    """Schema for resource responses."""

    model_config = ConfigDict(from_attributes=True)

    catalog_id: str
    repository_id: str | None = None


ResourceListResponse = Page[ResourceResponse]


# Bookmark schemas


class BookmarkCreate(ResourceCreate):
    """Schema for creating a new bookmark.

    Bookmarks live in a repository and don't require an external location.
    """

    resource_type: Literal["Bookmark"] = "Bookmark"
    location: str | None = None  # Override parent requirement
    repository: str = Field(..., description="Required for Bookmark")


class BookmarkResponse(ResourceResponse):
    """Schema for bookmark responses."""

    resource_type: Literal["Bookmark"] = "Bookmark"


# Collection schemas


class CollectionCreate(ResourceCreate):
    """Schema for creating a new collection.

    Collections live in a repository and don't require an external location.
    """

    resource_type: Literal["Collection"] = "Collection"
    location: str | None = None  # Override parent requirement
    repository: str = Field(..., description="Required for Collection")
    has_resources: list[str] = Field(default_factory=list)


class CollectionResponse(ResourceResponse):
    """Schema for collection responses."""

    resource_type: Literal["Collection"] = "Collection"
    has_resources: list[str] = Field(default_factory=list)


# Document schemas


class DocumentCreate(ResourceCreate):
    """Schema for creating a new document.

    Documents live in a repository and don't require an external location.
    """

    resource_type: Literal["Document"] = "Document"
    location: str | None = None  # Override parent requirement
    repository: str = Field(..., description="Required for Document")
    document_type: DocumentType = "Document"


class DocumentUpdate(ResourceUpdate):
    """Schema for updating a document."""

    document_type: DocumentType | None = None


class DocumentResponse(ResourceResponse):
    """Schema for document responses."""

    resource_type: Literal["Document"] = "Document"
    document_type: DocumentType = "Document"


# Note schemas


class NoteCreate(ResourceCreate):
    """Schema for creating a new note.

    Notes live in a repository and don't require an external location.
    """

    resource_type: Literal["Note"] = "Note"
    location: str | None = None  # Override parent requirement
    repository: str = Field(..., description="Required for Note")
    note_type: NoteType = "Note"


class NoteUpdate(ResourceUpdate):
    """Schema for updating a note."""

    note_type: NoteType | None = None


class NoteResponse(ResourceResponse):
    """Schema for note responses."""

    resource_type: Literal["Note"] = "Note"
    note_type: NoteType = "Note"


# Note Topic Suggestion Schemas (FEAT-006)


class NoteSuggestionRequest(BaseModel):
    """Request schema for suggesting topics for a note."""

    taxonomy_hint: str | None = Field(
        None,
        description="Optional taxonomy to scope suggestions. If not provided, will auto-detect.",
    )
    mode: Literal["fast", "accurate", "hybrid"] = Field(
        default="hybrid",
        description="Suggestion mode: fast (keyword), accurate (LLM), or hybrid (both)",
    )
    include_new_topics: bool = Field(
        default=True,
        description="Whether to suggest creating new topics if no good matches exist",
    )


class TopicSuggestionDetail(BaseModel):
    """Detailed topic suggestion for a note."""

    topic_id: str = Field(..., description="Suggested topic ID (CURIE)")
    topic_title: str = Field(..., description="Topic title")
    taxonomy_title: str = Field(..., description="Taxonomy containing the topic")
    taxonomy_id: str = Field(..., description="Taxonomy ID")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    reasoning: str | None = Field(None, description="Explanation for the suggestion")
    matched_phrases: list[str] = Field(
        default_factory=list,
        description="Phrases from the note that matched this topic",
    )
    source: Literal["keyword", "llm"] = Field(
        ..., description="Source of the suggestion (keyword classifier or LLM)"
    )


class NewTopicProposal(BaseModel):
    """Proposal for creating a new topic based on note content."""

    suggested_title: str = Field(..., description="Proposed topic title")
    suggested_description: str = Field(..., description="Proposed topic description")
    suggested_taxonomy_id: str = Field(
        ..., description="Taxonomy the topic should belong to"
    )
    suggested_parent_ids: list[str] = Field(
        default_factory=list, description="Suggested parent topics for hierarchy"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in this proposal"
    )
    reasoning: str = Field(
        ..., description="Explanation for why this new topic is needed"
    )


class NoteSuggestionResponse(BaseModel):
    """Response containing topic suggestions for a note."""

    existing_topics: list[TopicSuggestionDetail] = Field(
        default_factory=list, description="Existing topics that match the note content"
    )
    new_topic_suggestions: list[NewTopicProposal] = Field(
        default_factory=list,
        description="Proposals for new topics if no good matches exist",
    )
    taxonomy_suggestions: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Suggested taxonomies if taxonomy_hint was not provided",
    )


class NewTopicCreation(BaseModel):
    """Schema for creating a new topic from a proposal."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(...)
    taxonomy_id: str = Field(...)
    parent_ids: list[str] = Field(default_factory=list)


class ApplySuggestionsRequest(BaseModel):
    """Request to apply topic suggestions to a note."""

    selected_topic_ids: list[str] = Field(
        default_factory=list, description="Topic IDs to associate with the note"
    )
    new_topics_to_create: list[NewTopicCreation] = Field(
        default_factory=list,
        description="New topics to create and associate with the note",
    )
