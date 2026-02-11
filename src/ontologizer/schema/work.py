"""Pydantic schemas for Activity I/O.

These schemas are used for API request/response validation and serialization.
They are separate from domain models (attrs) and database models (SQLAlchemy).
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# Activity types based on the work domain schema
ActivityType = Literal["Effort", "Experiment", "Research", "Study", "Task", "Thinking"]


class ActivityBase(BaseModel):
    """Base schema for Activity with common fields."""

    title: str = Field(..., min_length=1, max_length=255, description="Activity title")
    activity_type: ActivityType = Field(..., description="Type of activity")
    description: str | None = Field(
        None, description="Optional activity description"
    )
    url: str | None = Field(
        None, description="Optional URL associated with this activity"
    )
    created_by: str | None = Field(None, description="Who created this activity")


class ActivityCreate(BaseModel):
    """Schema for creating a new activity.

    Used for API requests when creating a new activity.
    ID is optional and will be auto-generated from title if not provided.
    """

    title: str = Field(..., min_length=1, max_length=255)
    activity_type: ActivityType
    description: str | None = None
    url: str | None = None
    created_by: str | None = None


class ActivityUpdate(BaseModel):
    """Schema for updating an existing activity.

    All fields are optional to support partial updates.
    """

    title: str | None = Field(None, min_length=1, max_length=255)
    activity_type: ActivityType | None = None
    description: str | None = None
    url: str | None = None
    created_by: str | None = None


class ActivityResponse(ActivityBase):
    """Schema for activity responses.

    Used for API responses. Includes all fields including ID and timestamps.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class ActivityListResponse(BaseModel):
    """Schema for paginated activity list responses."""

    items: list[ActivityResponse] = Field(..., description="List of activities")
    total: int = Field(..., ge=0, description="Total count of activities")
    limit: int = Field(..., ge=1, description="Items per page")
    offset: int = Field(..., ge=0, description="Offset from start")


class ActivitySearchRequest(BaseModel):
    """Schema for activity search requests."""

    query: str = Field(..., min_length=1, description="Search query")
    activity_type: ActivityType | None = Field(
        None, description="Filter by activity type"
    )
    created_by: str | None = Field(None, description="Filter by creator")
    limit: int = Field(default=50, ge=1, le=1000, description="Max results")
    offset: int = Field(default=0, ge=0, description="Result offset")


class ActivitySummaryResponse(BaseModel):
    """Aggregate summary of activities by type."""

    total: int = Field(..., ge=0, description="Total activities")
    by_type: dict[str, int] = Field(
        default_factory=dict,
        description="Counts keyed by activity type",
    )
    created_by: str | None = Field(
        None, description="Optional creator scope for counts"
    )


class ActivityRecentListResponse(BaseModel):
    """Recently created activities."""

    class Item(BaseModel):
        id: str
        title: str
        activity_type: str
        created_by: str | None
        created_at: datetime

    items: list[Item] = Field(default_factory=list)
    created_by: str | None = Field(
        None, description="Optional creator scope for recent activities"
    )
