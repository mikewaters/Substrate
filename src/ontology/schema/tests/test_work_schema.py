"""Unit tests for work Pydantic schemas."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from ontology.schema.work import (
    ActivityCreate,
    ActivityUpdate,
    ActivityResponse,
    ActivityListResponse,
    ActivitySearchRequest,
    ActivitySummaryResponse,
    ActivityRecentListResponse,
)


class TestActivityCreate:
    """Test the ActivityCreate schema."""

    def test_activity_create_with_required_fields(self):
        """Test creating ActivityCreate with only required fields."""
        data = {
            "title": "Test Activity",
            "activity_type": "Task",
        }
        activity = ActivityCreate(**data)

        assert activity.title == "Test Activity"
        assert activity.activity_type == "Task"
        assert activity.description is None
        assert activity.url is None
        assert activity.created_by is None

    def test_activity_create_with_all_fields(self):
        """Test creating ActivityCreate with all fields."""
        data = {
            "title": "Complete Activity",
            "activity_type": "Effort",
            "description": "A complete activity",
            "url": "https://example.com",
            "created_by": "user@example.com",
        }
        activity = ActivityCreate(**data)

        assert activity.title == "Complete Activity"
        assert activity.activity_type == "Effort"
        assert activity.description == "A complete activity"
        assert activity.url == "https://example.com"
        assert activity.created_by == "user@example.com"

    def test_activity_create_missing_required_field(self):
        """Test that ActivityCreate requires title and activity_type."""
        with pytest.raises(ValidationError):
            ActivityCreate(title="Test")  # Missing activity_type

        with pytest.raises(ValidationError):
            ActivityCreate(activity_type="Task")  # Missing title

    def test_activity_create_invalid_type(self):
        """Test that ActivityCreate validates activity_type."""
        data = {
            "title": "Test Activity",
            "activity_type": "InvalidType",
        }
        with pytest.raises(ValidationError):
            ActivityCreate(**data)

    @pytest.mark.parametrize(
        "activity_type",
        ["Effort", "Experiment", "Research", "Study", "Task", "Thinking"],
    )
    def test_activity_create_valid_types(self, activity_type):
        """Test that all valid activity types are accepted."""
        data = {
            "title": f"Test {activity_type}",
            "activity_type": activity_type,
        }
        activity = ActivityCreate(**data)

        assert activity.activity_type == activity_type


class TestActivityUpdate:
    """Test the ActivityUpdate schema."""

    def test_activity_update_all_fields_optional(self):
        """Test that all fields in ActivityUpdate are optional."""
        activity = ActivityUpdate()

        assert activity.title is None
        assert activity.activity_type is None
        assert activity.description is None
        assert activity.url is None
        assert activity.created_by is None

    def test_activity_update_partial_update(self):
        """Test partial updates with ActivityUpdate."""
        data = {"title": "Updated Title"}
        activity = ActivityUpdate(**data)

        assert activity.title == "Updated Title"
        assert activity.activity_type is None

    def test_activity_update_invalid_type(self):
        """Test that ActivityUpdate validates activity_type when provided."""
        data = {"activity_type": "InvalidType"}
        with pytest.raises(ValidationError):
            ActivityUpdate(**data)


class TestActivityResponse:
    """Test the ActivityResponse schema."""

    def test_activity_response_with_all_fields(self):
        """Test creating ActivityResponse with all fields."""
        now = datetime.now()
        activity_id = "act:test"

        data = {
            "id": activity_id,
            "title": "Test Activity",
            "activity_type": "Task",
            "description": "A test activity",
            "url": "https://example.com",
            "created_by": "user@example.com",
            "created_at": now,
            "updated_at": now,
        }
        activity = ActivityResponse(**data)

        assert activity.id == activity_id
        assert activity.title == "Test Activity"
        assert activity.activity_type == "Task"
        assert activity.description == "A test activity"
        assert activity.url == "https://example.com"
        assert activity.created_by == "user@example.com"
        assert activity.created_at == now
        assert activity.updated_at == now

    def test_activity_response_missing_required_fields(self):
        """Test that ActivityResponse requires all fields."""
        with pytest.raises(ValidationError):
            ActivityResponse(
                title="Test",
                activity_type="Task",
            )  # Missing id, timestamps


class TestActivityListResponse:
    """Test the ActivityListResponse schema."""

    def test_activity_list_response(self):
        """Test creating ActivityListResponse."""
        now = datetime.now()
        items = [
            ActivityResponse(
                id=f"act:activity-{i}",
                title=f"Activity {i}",
                activity_type="Task",
                created_at=now,
                updated_at=now,
            )
            for i in range(3)
        ]

        response = ActivityListResponse(
            items=items,
            total=10,
            limit=3,
            offset=0,
        )

        assert len(response.items) == 3
        assert response.total == 10
        assert response.limit == 3
        assert response.offset == 0

    def test_activity_list_response_empty(self):
        """Test ActivityListResponse with empty items."""
        response = ActivityListResponse(
            items=[],
            total=0,
            limit=50,
            offset=0,
        )

        assert len(response.items) == 0
        assert response.total == 0


class TestActivitySearchRequest:
    """Test the ActivitySearchRequest schema."""

    def test_activity_search_request_minimal(self):
        """Test ActivitySearchRequest with minimal fields."""
        request = ActivitySearchRequest(query="test")

        assert request.query == "test"
        assert request.activity_type is None
        assert request.created_by is None
        assert request.limit == 50
        assert request.offset == 0

    def test_activity_search_request_with_filters(self):
        """Test ActivitySearchRequest with all filters."""
        request = ActivitySearchRequest(
            query="test",
            activity_type="Task",
            created_by="user@example.com",
            limit=10,
            offset=20,
        )

        assert request.query == "test"
        assert request.activity_type == "Task"
        assert request.created_by == "user@example.com"
        assert request.limit == 10
        assert request.offset == 20

    def test_activity_search_request_invalid_limit(self):
        """Test that ActivitySearchRequest validates limit bounds."""
        with pytest.raises(ValidationError):
            ActivitySearchRequest(query="test", limit=0)  # Too small

        with pytest.raises(ValidationError):
            ActivitySearchRequest(query="test", limit=2000)  # Too large

    def test_activity_search_request_invalid_offset(self):
        """Test that ActivitySearchRequest validates offset."""
        with pytest.raises(ValidationError):
            ActivitySearchRequest(query="test", offset=-1)  # Negative


class TestActivitySummaryResponse:
    """Test the ActivitySummaryResponse schema."""

    def test_activity_summary_response(self):
        """Test creating ActivitySummaryResponse."""
        response = ActivitySummaryResponse(
            total=10,
            by_type={
                "Task": 5,
                "Effort": 3,
                "Research": 2,
            },
            created_by="user@example.com",
        )

        assert response.total == 10
        assert response.by_type["Task"] == 5
        assert response.by_type["Effort"] == 3
        assert response.by_type["Research"] == 2
        assert response.created_by == "user@example.com"


class TestActivityRecentListResponse:
    """Test the ActivityRecentListResponse schema."""

    def test_activity_recent_list_response(self):
        """Test creating ActivityRecentListResponse."""
        now = datetime.now()
        items = [
            ActivityRecentListResponse.Item(
                id="act:test",
                title=f"Activity {i}",
                activity_type="Task",
                created_by="user@example.com",
                created_at=now,
            )
            for i in range(3)
        ]

        response = ActivityRecentListResponse(
            items=items,
            created_by="user@example.com",
        )

        assert len(response.items) == 3
        assert response.created_by == "user@example.com"
        for item in response.items:
            assert item.activity_type == "Task"
            assert item.created_by == "user@example.com"
