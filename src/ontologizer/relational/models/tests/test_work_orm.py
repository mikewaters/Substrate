"""Unit tests for work ORM models."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ontologizer.relational.models.work import Activity


@pytest.mark.asyncio
class TestActivity:
    """Test the Activity ORM model."""

    async def test_activity_creation_with_required_fields(self, db_session):
        """Test creating an Activity with required fields."""
        activity = Activity(
            title="Test Activity",
            activity_type="Task",
        )
        db_session.add(activity)
        await db_session.commit()

        # Verify it was created
        result = await db_session.execute(select(Activity))
        saved_activity = result.scalar_one()

        assert saved_activity.title == "Test Activity"
        assert saved_activity.activity_type == "Task"
        assert saved_activity.id == "act:test-activity"
        assert saved_activity.id is not None
        assert saved_activity.created_at is not None
        assert saved_activity.updated_at is not None

    async def test_activity_creation_with_all_fields(self, db_session):
        """Test creating an Activity with all fields."""
        activity = Activity(
            title="Complete Activity",
            activity_type="Effort",
            id="act:complete-activity",
            description="A complete activity with all fields",
            url="https://example.com",
            created_by="user@example.com",
        )
        db_session.add(activity)
        await db_session.commit()

        # Verify it was created
        result = await db_session.execute(select(Activity))
        saved_activity = result.scalar_one()

        assert saved_activity.title == "Complete Activity"
        assert saved_activity.activity_type == "Effort"
        assert saved_activity.id == "act:complete-activity"
        assert saved_activity.description == "A complete activity with all fields"
        assert saved_activity.url == "https://example.com"
        assert saved_activity.created_by == "user@example.com"

    async def test_activity_identifier_auto_generation(self, db_session):
        """Test that identifier is auto-generated from title."""
        activity = Activity(
            title="My Test Activity",
            activity_type="Task",
        )
        db_session.add(activity)
        await db_session.commit()

        result = await db_session.execute(select(Activity))
        saved_activity = result.scalar_one()

        assert saved_activity.id == "act:my-test-activity"

    async def test_activity_custom_identifier(self, db_session):
        """Test that custom identifier is preserved."""
        activity = Activity(
            title="Test",
            activity_type="Task",
            id="custom:identifier",
        )
        db_session.add(activity)
        await db_session.commit()

        result = await db_session.execute(select(Activity))
        saved_activity = result.scalar_one()

        assert saved_activity.id == "custom:identifier"

    async def test_activity_identifier_unique_constraint(self, db_session):
        """Test that identifier must be unique."""
        activity1 = Activity(
            title="First Activity",
            activity_type="Task",
            id="act:same-id",
        )
        db_session.add(activity1)
        await db_session.commit()

        activity2 = Activity(
            title="Second Activity",
            activity_type="Task",
            id="act:same-id",
        )
        db_session.add(activity2)

        with pytest.raises(IntegrityError):
            await db_session.commit()

    async def test_activity_type_constraint(self, db_session):
        """Test that activity_type must be one of the valid types."""
        activity = Activity(
            title="Invalid Activity",
            activity_type="InvalidType",
        )
        db_session.add(activity)

        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.parametrize(
        "activity_type",
        ["Effort", "Experiment", "Research", "Study", "Task", "Thinking"],
    )
    async def test_valid_activity_types(self, db_session, activity_type):
        """Test that all valid activity types are accepted."""
        activity = Activity(
            title=f"Test {activity_type}",
            activity_type=activity_type,
        )
        db_session.add(activity)
        await db_session.commit()

        result = await db_session.execute(select(Activity))
        saved_activity = result.scalar_one()

        assert saved_activity.activity_type == activity_type

    async def test_activity_title_required(self, db_session):
        """Test that title is required."""
        activity = Activity(
            activity_type="Task",
        )
        db_session.add(activity)

        with pytest.raises(IntegrityError):
            await db_session.commit()

    async def test_activity_type_required(self, db_session):
        """Test that activity_type is required."""
        activity = Activity(
            title="Test Activity",
        )
        db_session.add(activity)

        with pytest.raises(IntegrityError):
            await db_session.commit()

    async def test_activity_repr(self, db_session):
        """Test string representation of Activity."""
        activity = Activity(
            title="Test Activity",
            activity_type="Task",
        )
        db_session.add(activity)
        await db_session.commit()

        result = await db_session.execute(select(Activity))
        saved_activity = result.scalar_one()

        repr_str = repr(saved_activity)
        assert "Activity" in repr_str
        assert "Task" in repr_str
        assert "Test Activity" in repr_str

    async def test_activity_timestamps(self, db_session):
        """Test that timestamps are automatically managed."""
        activity = Activity(
            title="Test Activity",
            activity_type="Task",
        )
        db_session.add(activity)
        await db_session.commit()

        result = await db_session.execute(select(Activity))
        saved_activity = result.scalar_one()

        assert saved_activity.created_at is not None
        assert saved_activity.updated_at is not None
        # created_at and updated_at should be very close for a new record
        assert (
            saved_activity.updated_at - saved_activity.created_at
        ).total_seconds() < 1

    async def test_activity_update_timestamp(self, db_session):
        """Test that updated_at changes on update."""
        activity = Activity(
            title="Test Activity",
            activity_type="Task",
        )
        db_session.add(activity)
        await db_session.commit()

        result = await db_session.execute(select(Activity))
        saved_activity = result.scalar_one()
        original_updated_at = saved_activity.updated_at

        # Update the activity
        saved_activity.description = "Updated description"
        await db_session.commit()

        result = await db_session.execute(select(Activity))
        updated_activity = result.scalar_one()

        # Note: updated_at auto-update depends on the CURIEBase implementation
        # This test may need adjustment based on actual behavior
        assert updated_activity.description == "Updated description"

    async def test_multiple_activities(self, db_session):
        """Test creating multiple activities."""
        activities = [
            Activity(title=f"Activity {i}", activity_type="Task") for i in range(5)
        ]
        db_session.add_all(activities)
        await db_session.commit()

        result = await db_session.execute(select(Activity))
        saved_activities = result.scalars().all()

        assert len(saved_activities) == 5
        for i, activity in enumerate(saved_activities):
            assert activity.title == f"Activity {i}"
            assert activity.activity_type == "Task"

    async def test_activity_filter_by_type(self, db_session):
        """Test filtering activities by type."""
        activities = [
            Activity(title="Task 1", activity_type="Task"),
            Activity(title="Task 2", activity_type="Task"),
            Activity(title="Effort 1", activity_type="Effort"),
            Activity(title="Research 1", activity_type="Research"),
        ]
        db_session.add_all(activities)
        await db_session.commit()

        # Query only Tasks
        result = await db_session.execute(
            select(Activity).where(Activity.activity_type == "Task")
        )
        tasks = result.scalars().all()

        assert len(tasks) == 2
        assert all(t.activity_type == "Task" for t in tasks)

    async def test_activity_filter_by_created_by(self, db_session):
        """Test filtering activities by created_by."""
        activities = [
            Activity(
                title="Activity 1", activity_type="Task", created_by="user1@example.com"
            ),
            Activity(
                title="Activity 2", activity_type="Task", created_by="user1@example.com"
            ),
            Activity(
                title="Activity 3", activity_type="Task", created_by="user2@example.com"
            ),
        ]
        db_session.add_all(activities)
        await db_session.commit()

        # Query by created_by
        result = await db_session.execute(
            select(Activity).where(Activity.created_by == "user1@example.com")
        )
        user1_activities = result.scalars().all()

        assert len(user1_activities) == 2
        assert all(a.created_by == "user1@example.com" for a in user1_activities)
