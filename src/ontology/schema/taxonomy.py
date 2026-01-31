# Taxonomy Schemas


from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TaxonomyBase(BaseModel):
    """Base schema for Taxonomy with common fields."""

    title: str = Field(..., min_length=1, max_length=255, description="Taxonomy title")
    description: str | None = Field(
        None, description="Optional taxonomy description"
    )
    skos_uri: str | None = Field(None, description="Optional SKOS URI for alignment")


class TaxonomyCreate(TaxonomyBase):
    """Schema for creating a new taxonomy.

    Used for API requests when creating a new taxonomy.
    Does not include ID or timestamps.
    """

    pass


class TaxonomyUpdate(BaseModel):
    """Schema for updating an existing taxonomy.

    All fields are optional to support partial updates.
    """

    # id: str = Field(..., description="Unique identifier (CURIE)")
    title: str | None = Field(None, min_length=1, max_length=255)
    # identifier: Optional[str] = Field(None, min_length=1, max_length=255, description="Taxonomy CURIE")
    description: str | None = None
    skos_uri: str | None = None


class TaxonomyResponse(TaxonomyBase):
    """Schema for taxonomy responses.

    Used for API responses. Includes all fields including ID and timestamps.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique identifier (CURIE)")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class TaxonomyListResponse(BaseModel):
    """Schema for paginated taxonomy list responses."""

    items: list[TaxonomyResponse] = Field(..., description="List of taxonomies")
    total: int = Field(..., ge=0, description="Total count of taxonomies")
    limit: int = Field(..., ge=1, description="Items per page")
    offset: int = Field(..., ge=0, description="Offset from start")
