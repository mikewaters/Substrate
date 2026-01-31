"""Unit tests for work services."""

import pytest
import pytest_asyncio
from sqlalchemy import select, func

from advanced_alchemy.filters import LimitOffset
from ontology.relational.models import Activity as ActivityORM
from ontology.relational.services.work import ActivityService
from ontology.schema.work import (
    ActivityCreate,
    ActivityUpdate,
)


@pytest.mark.asyncio
class TestActivityService:
    """Test the ActivityService."""

    @pytest_asyncio.fixture
    async def activity_service(self, db_session):
        """Create an ActivityService for testing."""
        return ActivityService(session=db_session)

    async def test_add_activity(self, activity_service):
        """Test adding a new activity."""
        data = ActivityCreate(
            title="Test Activity",
            activity_type="Task",
        )
        result = await activity_service.create(data)

        assert result.title == "Test Activity"
        assert result.activity_type == "Task"
        assert result.id == "act:test-activity"

    async def test_get_activity(self, activity_service, db_session):
        """Test retrieving an activity."""
        # Create an activity first
        activity = ActivityORM(title="Test Activity", activity_type="Task")
        db_session.add(activity)
        await db_session.flush()

        # Retrieve it
        result = await activity_service.get_one_or_none(id=activity.id)

        assert result is not None
        assert result.title == "Test Activity"
        assert result.id == activity.id

    async def test_get_nonexistent_activity(self, activity_service):
        """Test retrieving a nonexistent activity returns None."""
        result = await activity_service.get_one_or_none(id="act:test")
        assert result is None

    async def test_update_activity(self, activity_service, db_session):
        """Test updating an activity."""
        # Create an activity first
        activity = ActivityORM(title="Original Title", activity_type="Task")
        db_session.add(activity)
        await db_session.flush()

        # Update it
        update_data = ActivityUpdate(
            title="Updated Title", description="New description"
        )
        result = await activity_service.update(update_data, activity.id)

        assert result.title == "Updated Title"
        assert result.description == "New description"

    async def test_delete_activity(self, activity_service, db_session):
        """Test deleting an activity."""
        # Create an activity first
        activity = ActivityORM(title="Test Activity", activity_type="Task")
        db_session.add(activity)
        await db_session.flush()

        activity_id = activity.id

        # Delete it
        await activity_service.delete(activity_id)

        # Verify it's gone
        result = await activity_service.get_one_or_none(id=activity_id)
        assert result is None

    async def test_list_activities(self, activity_service, db_session):
        """Test listing activities."""
        # Create several activities
        activities = [
            ActivityORM(title=f"Activity {i}", activity_type="Task") for i in range(5)
        ]
        db_session.add_all(activities)
        await db_session.flush()

        # List them
        results, total = await activity_service.list_and_count(LimitOffset(10, 0))

        assert total == 5
        assert len(results) == 5

    async def test_list_activities_with_type_filter(self, activity_service, db_session):
        """Test listing activities filtered by type."""
        activities = [
            ActivityORM(title="Task 1", activity_type="Task"),
            ActivityORM(title="Task 2", activity_type="Task"),
            ActivityORM(title="Effort 1", activity_type="Effort"),
        ]
        db_session.add_all(activities)
        await db_session.flush()

        # Use filter with list_and_count
        results, total = await activity_service.list_and_count(
            ActivityORM.activity_type == "Task"
        )

        assert total == 2
        assert all(item.activity_type == "Task" for item in results)

    async def test_list_activities_with_created_by_filter(
        self, activity_service, db_session
    ):
        """Test listing activities filtered by created_by."""
        activities = [
            ActivityORM(
                title="Activity 1", activity_type="Task", created_by="user1@example.com"
            ),
            ActivityORM(
                title="Activity 2", activity_type="Task", created_by="user1@example.com"
            ),
            ActivityORM(
                title="Activity 3", activity_type="Task", created_by="user2@example.com"
            ),
        ]
        db_session.add_all(activities)
        await db_session.flush()

        # Use filter with list_and_count
        results, total = await activity_service.list_and_count(
            ActivityORM.created_by == "user1@example.com"
        )

        assert total == 2
        assert all(item.created_by == "user1@example.com" for item in results)

    async def test_search_activities(self, activity_service, db_session):
        """Test searching activities by title."""
        activities = [
            ActivityORM(title="Write Documentation", activity_type="Task"),
            ActivityORM(title="Write Tests", activity_type="Task"),
            ActivityORM(title="Review Code", activity_type="Task"),
        ]
        db_session.add_all(activities)
        await db_session.flush()

        # Use list_and_count with LIKE filter for search
        results, total = await activity_service.list_and_count(
            ActivityORM.title.like("%Write%")
        )

        assert total == 2
        assert all("Write" in item.title for item in results)

    async def test_search_activities_with_filters(self, activity_service, db_session):
        """Test searching with filters."""
        activities = [
            ActivityORM(
                title="Write Documentation",
                activity_type="Task",
                created_by="user@example.com",
            ),
            ActivityORM(
                title="Write Tests",
                activity_type="Effort",
                created_by="user@example.com",
            ),
            ActivityORM(
                title="Review Code",
                activity_type="Task",
                created_by="other@example.com",
            ),
        ]
        db_session.add_all(activities)
        await db_session.flush()

        # Use list_and_count with multiple filters
        results, total = await activity_service.list_and_count(
            ActivityORM.title.like("%Write%"),
            ActivityORM.activity_type == "Task",
            ActivityORM.created_by == "user@example.com",
        )

        assert total == 1
        assert results[0].title == "Write Documentation"

    async def test_get_activity_summary(self, activity_service, db_session):
        """Test getting activity summary."""
        activities = [
            ActivityORM(title="Task 1", activity_type="Task"),
            ActivityORM(title="Task 2", activity_type="Task"),
            ActivityORM(title="Effort 1", activity_type="Effort"),
            ActivityORM(title="Research 1", activity_type="Research"),
        ]
        db_session.add_all(activities)
        await db_session.flush()

        # Use direct session query for aggregation
        total_result = await db_session.execute(
            select(func.count()).select_from(ActivityORM)
        )
        total = total_result.scalar()

        type_result = await db_session.execute(
            select(ActivityORM.activity_type, func.count(ActivityORM.id)).group_by(
                ActivityORM.activity_type
            )
        )
        by_type = {row[0]: row[1] for row in type_result.all()}

        assert total == 4
        assert by_type["Task"] == 2
        assert by_type["Effort"] == 1
        assert by_type["Research"] == 1

    async def test_get_activity_summary_filtered(self, activity_service, db_session):
        """Test getting activity summary filtered by created_by."""
        activities = [
            ActivityORM(
                title="Task 1", activity_type="Task", created_by="user1@example.com"
            ),
            ActivityORM(
                title="Task 2", activity_type="Task", created_by="user1@example.com"
            ),
            ActivityORM(
                title="Task 3", activity_type="Task", created_by="user2@example.com"
            ),
        ]
        db_session.add_all(activities)
        await db_session.flush()

        # Use direct session query with filter for aggregation
        total_result = await db_session.execute(
            select(func.count())
            .select_from(ActivityORM)
            .where(ActivityORM.created_by == "user1@example.com")
        )
        total = total_result.scalar()

        assert total == 2

    async def test_get_recent_activities(self, activity_service, db_session):
        """Test getting recent activities."""
        # Create activities with different timestamps
        activities = [
            ActivityORM(title=f"Activity {i}", activity_type="Task") for i in range(5)
        ]
        db_session.add_all(activities)
        await db_session.flush()

        # Use direct session query with order_by
        result = await db_session.execute(
            select(ActivityORM).order_by(ActivityORM.created_at.desc()).limit(3)
        )
        items = result.scalars().all()

        assert len(items) == 3
        # Should be in descending order by created_at
        for i in range(len(items) - 1):
            assert items[i].created_at >= items[i + 1].created_at

    async def test_get_recent_activities_filtered(self, activity_service, db_session):
        """Test getting recent activities filtered by created_by."""
        activities = [
            ActivityORM(
                title="Activity 1", activity_type="Task", created_by="user1@example.com"
            ),
            ActivityORM(
                title="Activity 2", activity_type="Task", created_by="user1@example.com"
            ),
            ActivityORM(
                title="Activity 3", activity_type="Task", created_by="user2@example.com"
            ),
        ]
        db_session.add_all(activities)
        await db_session.flush()

        # Use direct session query with filter and order_by
        result = await db_session.execute(
            select(ActivityORM)
            .where(ActivityORM.created_by == "user1@example.com")
            .order_by(ActivityORM.created_at.desc())
            .limit(10)
        )
        items = result.scalars().all()

        assert len(items) == 2
        assert all(item.created_by == "user1@example.com" for item in items)
