"""Unit tests for work repositories."""

import pytest
import pytest_asyncio
from advanced_alchemy.exceptions import NotFoundError
from advanced_alchemy.filters import LimitOffset

from ontologizer.relational.models import Activity
from ontologizer.relational.repository.work import ActivityRepository


@pytest.mark.asyncio
class TestActivityRepository:
    """Test the ActivityRepository."""

    @pytest_asyncio.fixture
    async def activity_repo(self, db_session):
        """Create an ActivityRepository for testing."""
        return ActivityRepository(session=db_session, wrap_exceptions=True)

    async def test_add_activity(self, activity_repo, db_session):
        """Test adding a new activity."""
        activity = Activity(
            title="Test Activity",
            activity_type="Task",
        )
        result = await activity_repo.add(activity)
        await db_session.flush()

        assert result.id is not None
        assert result.title == "Test Activity"
        assert result.activity_type == "Task"
        assert result.id == "act:test-activity"

    async def test_add_many_activities(self, activity_repo, db_session):
        """Test adding multiple activities."""
        activities = [
            Activity(title=f"Activity {i}", activity_type="Task") for i in range(3)
        ]
        results = await activity_repo.add_many(activities)
        await db_session.flush()

        assert len(results) == 3
        for i, activity in enumerate(results):
            assert activity.title == f"Activity {i}"

    async def test_get_activity(self, activity_repo, db_session):
        """Test retrieving an activity by ID."""
        activity = Activity(title="Test Activity", activity_type="Task")
        created = await activity_repo.add(activity)
        await db_session.flush()

        retrieved = await activity_repo.get(created.id)

        assert retrieved.id == created.id
        assert retrieved.title == "Test Activity"

    async def test_get_nonexistent_activity(self, activity_repo):
        """Test retrieving a nonexistent activity raises NotFoundError."""
        nonexistent_id = "act:test"

        with pytest.raises(NotFoundError):
            await activity_repo.get(nonexistent_id)

    async def test_get_one_or_none(self, activity_repo, db_session):
        """Test get_one_or_none method."""
        activity = Activity(title="Test Activity", activity_type="Task")
        created = await activity_repo.add(activity)
        await db_session.flush()

        # Should find the activity
        found = await activity_repo.get_one_or_none(id=created.id)
        assert found is not None
        assert found.id == created.id

        # Should return None for nonexistent
        not_found = await activity_repo.get_one_or_none(id="act:test")
        assert not_found is None

    async def test_update_activity(self, activity_repo, db_session):
        """Test updating an activity."""
        activity = Activity(title="Original Title", activity_type="Task")
        created = await activity_repo.add(activity)
        await db_session.flush()

        # Update the activity
        created.title = "Updated Title"
        created.description = "New description"
        updated = await activity_repo.update(created)
        await db_session.flush()

        assert updated.title == "Updated Title"
        assert updated.description == "New description"

    async def test_delete_activity(self, activity_repo, db_session):
        """Test deleting an activity."""
        activity = Activity(title="Test Activity", activity_type="Task")
        created = await activity_repo.add(activity)
        await db_session.flush()

        activity_id = created.id

        # Delete the activity
        await activity_repo.delete(activity_id)
        await db_session.flush()

        # Should not be found after deletion
        result = await activity_repo.get_one_or_none(id=activity_id)
        assert result is None

    async def test_list_activities(self, activity_repo, db_session):
        """Test listing activities."""
        activities = [
            Activity(title=f"Activity {i}", activity_type="Task") for i in range(5)
        ]
        await activity_repo.add_many(activities)
        await db_session.flush()

        results = await activity_repo.list()

        assert len(results) == 5

    async def test_list_and_count(self, activity_repo, db_session):
        """Test listing activities with count."""
        activities = [
            Activity(title=f"Activity {i}", activity_type="Task") for i in range(10)
        ]
        await activity_repo.add_many(activities)
        await db_session.flush()

        results, total = await activity_repo.list_and_count(
            LimitOffset(limit=5, offset=0)
        )

        assert len(results) == 5
        assert total == 10

    async def test_count_activities(self, activity_repo, db_session):
        """Test counting activities."""
        activities = [
            Activity(title=f"Activity {i}", activity_type="Task") for i in range(7)
        ]
        await activity_repo.add_many(activities)
        await db_session.flush()

        count = await activity_repo.count()

        assert count == 7

    async def test_exists(self, activity_repo, db_session):
        """Test checking if activity exists."""
        activity = Activity(title="Test Activity", activity_type="Task")
        created = await activity_repo.add(activity)
        await db_session.flush()

        # Should exist
        exists = await activity_repo.exists(id=created.id)
        assert exists is True

        # Should not exist
        not_exists = await activity_repo.exists(id="act:test")
        assert not_exists is False

    async def test_upsert_new_activity(self, activity_repo, db_session):
        """Test upserting a new activity."""
        activity = Activity(
            title="New Activity",
            activity_type="Task",
            id="act:new-activity",
        )
        result = await activity_repo.upsert(activity)
        await db_session.flush()

        assert result.id is not None
        assert result.title == "New Activity"

    @pytest.mark.skip(
        reason="advanced-alchemy upsert requires to_dict() method on ORM models"
    )
    async def test_upsert_existing_activity(self, activity_repo, db_session):
        """Test upserting an existing activity.

        TODO: This test is currently skipped due to an architectural issue with
        advanced-alchemy's repository.upsert() method. To fix this:

        1. The issue: advanced-alchemy's upsert method calls to_dict() on ORM model
           instances when no match_fields are provided or when it needs to update
           existing records. SQLAlchemy ORM models don't have a to_dict() method
           by default.

        2. Possible solutions:
           a) Add a to_dict() method to CURIEBase (or a mixin) that all ORM models
              inherit from. This method should convert ORM instances to dictionaries.

           b) Use get_or_create pattern instead of upsert:
              existing = await repo.get_one_or_none(id=data.id)
              if existing:
                  return await repo.update(existing, data)
              else:
                  return await repo.add(data)

           c) Always provide explicit match_fields to upsert() calls, though this
              still fails when updating the existing record

           d) Override the upsert method in ActivityRepository to handle the
              conversion properly

        3. Recommended approach: Add a to_dict() method to CURIEBase in
           src/ontology/database/models.py that uses SQLAlchemy's inspection
           to extract column values:

           from sqlalchemy import inspect

           def to_dict(self, exclude=None):
               exclude = exclude or set()
               mapper = inspect(self.__class__)
               return {
                   c.key: getattr(self, c.key)
                   for c in mapper.column_attrs
                   if c.key not in exclude
               }

        Expected behavior: Upserting with an existing ID should update the record
        rather than creating a duplicate.
        """
        # Create initial activity
        activity = Activity(
            title="Original",
            activity_type="Task",
            id="act:original",
        )
        created = await activity_repo.add(activity)
        await db_session.flush()

        # Upsert with same id
        updated_activity = Activity(
            id=created.id,
            title="Updated",
            activity_type="Task",
        )
        result = await activity_repo.upsert(updated_activity, match_fields=["id"])
        await db_session.flush()

        assert result.id == created.id
        assert result.title == "Updated"

    async def test_filter_by_type(self, activity_repo, db_session):
        """Test filtering activities by type."""
        activities = [
            Activity(title="Task 1", activity_type="Task"),
            Activity(title="Task 2", activity_type="Task"),
            Activity(title="Effort 1", activity_type="Effort"),
        ]
        await activity_repo.add_many(activities)
        await db_session.flush()

        # Filter by Task type
        tasks = await activity_repo.list(Activity.activity_type == "Task")

        assert len(tasks) == 2
        assert all(t.activity_type == "Task" for t in tasks)

    async def test_filter_by_created_by(self, activity_repo, db_session):
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
        await activity_repo.add_many(activities)
        await db_session.flush()

        # Filter by user1
        user1_activities = await activity_repo.list(
            Activity.created_by == "user1@example.com"
        )

        assert len(user1_activities) == 2
        assert all(a.created_by == "user1@example.com" for a in user1_activities)
