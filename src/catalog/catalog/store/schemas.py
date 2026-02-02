"""catalog.store.schemas - Pydantic models for store operations.

Provides Create and Info schemas for each Resource type in the catalog.
Create schemas define input for resource creation; Info schemas define
the read representation returned from queries.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from catalog.store.models import DocumentKind

__all__ = [
    "BookmarkCreate",
    "BookmarkInfo",
    "CatalogCreate",
    "CatalogInfo",
    "CollectionCreate",
    "CollectionInfo",
    "DatasetCreate",
    "DatasetInfo",
    "DocumentCreate",
    "DocumentInfo",
    "DocumentUpdate",
    "RepositoryCreate",
    "RepositoryInfo",
]


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------


class DatasetCreate(BaseModel):
    """Input schema for creating a new Dataset resource."""

    name: str = Field(..., description="Unique name identifier for the dataset")
    source_type: str = Field(..., description="Type of source (directory, obsidian, etc.)")
    source_path: str = Field(..., description="Filesystem path to the source")
    title: str | None = Field(None, description="Optional human-readable title")
    description: str | None = Field(None, description="Optional longer description")
    model_config = {"frozen": True}


class DatasetInfo(BaseModel):
    """Read representation of a Dataset resource."""

    id: int
    name: str
    uri: str
    source_type: str
    source_path: str
    title: str | None = None
    description: str | None = None
    created_at: datetime
    updated_at: datetime
    document_count: int = 0
    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------


class DocumentCreate(BaseModel):
    """Input schema for creating a new Document within a parent resource."""

    path: str
    content_hash: str
    body: str
    title: str | None = Field(None, description="Optional human-readable title")
    description: str | None = Field(None, description="Optional longer description")
    doc_type: DocumentKind = Field(
        default=DocumentKind.OTHER,
        description="Classifies the document origin/format",
    )
    etag: str | None = None
    last_modified: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    model_config = {"frozen": True}


class DocumentUpdate(BaseModel):
    """Partial update schema for an existing Document."""

    title: str | None = None
    description: str | None = None
    content_hash: str | None = None
    body: str | None = None
    doc_type: DocumentKind | None = None
    etag: str | None = None
    last_modified: datetime | None = None
    metadata: dict[str, Any] | None = None
    active: bool | None = None
    model_config = {"frozen": True}


class DocumentInfo(BaseModel):
    """Read representation of a Document resource."""

    id: int
    parent_id: int
    path: str
    title: str | None = None
    description: str | None = None
    active: bool
    doc_type: DocumentKind
    content_hash: str
    etag: str | None
    last_modified: datetime | None
    body: str
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, doc: Any) -> "DocumentInfo":
        """Construct a DocumentInfo from a Document ORM instance.

        Handles metadata_json deserialization via the model's get_metadata().

        Args:
            doc: A Document ORM model instance.

        Returns:
            Populated DocumentInfo.
        """
        return cls(
            id=doc.id,
            parent_id=doc.parent_id,
            path=doc.path,
            title=doc.title,
            description=doc.description,
            active=doc.active,
            doc_type=doc.doc_type,
            content_hash=doc.content_hash,
            etag=doc.etag,
            last_modified=doc.last_modified,
            body=doc.body,
            metadata=doc.get_metadata(),
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------


class CatalogCreate(BaseModel):
    """Input schema for creating a new Catalog resource."""

    title: str = Field(..., description="Human-readable title for the catalog")
    description: str | None = Field(None, description="Optional longer description")
    homepage: str | None = Field(None, description="Optional homepage URL")
    model_config = {"frozen": True}


class CatalogInfo(BaseModel):
    """Read representation of a Catalog resource."""

    id: int
    uri: str
    title: str | None = None
    description: str | None = None
    homepage: str | None = None
    created_at: datetime
    updated_at: datetime
    entry_count: int = 0
    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------


class CollectionCreate(BaseModel):
    """Input schema for creating a new Collection resource."""

    title: str = Field(..., description="Human-readable title for the collection")
    description: str | None = Field(None, description="Optional longer description")
    model_config = {"frozen": True}


class CollectionInfo(BaseModel):
    """Read representation of a Collection resource."""

    id: int
    uri: str
    title: str | None = None
    description: str | None = None
    created_at: datetime
    updated_at: datetime
    member_count: int = 0
    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Bookmark
# ---------------------------------------------------------------------------


class BookmarkCreate(BaseModel):
    """Input schema for creating a new Bookmark resource."""

    url: str = Field(..., description="The URL to bookmark")
    title: str | None = Field(None, description="Optional human-readable title")
    description: str | None = Field(None, description="Optional longer description")
    favicon_url: str | None = Field(None, description="Optional favicon URL")
    owner: str = Field(..., description="Owner of the bookmark")
    folder: str | None = Field(None, description="Optional folder/category")
    is_archived: bool = Field(False, description="Whether the bookmark is archived")
    model_config = {"frozen": True}


class BookmarkInfo(BaseModel):
    """Read representation of a Bookmark resource."""

    id: int
    uri: str
    url: str
    title: str | None = None
    description: str | None = None
    favicon_url: str | None = None
    owner: str
    folder: str | None = None
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class RepositoryCreate(BaseModel):
    """Input schema for creating a new Repository resource."""

    title: str | None = Field(None, description="Optional human-readable title")
    description: str | None = Field(None, description="Optional longer description")
    host: str | None = Field(None, description="Hosting platform (github, gitlab, etc.)")
    repo_full_name: str | None = Field(None, description="Full name, e.g. owner/repo")
    default_branch: str | None = Field(None, description="Default branch name")
    web_url: str | None = Field(None, description="Web URL for the repository")
    model_config = {"frozen": True}


class RepositoryInfo(BaseModel):
    """Read representation of a Repository resource."""

    id: int
    uri: str
    title: str | None = None
    description: str | None = None
    host: str | None = None
    repo_full_name: str | None = None
    default_branch: str | None = None
    web_url: str | None = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
