"""Integration tests for activity dataset loader."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ontologizer.relational.models import Activity
from ontologizer.loader.loader import load_activity_dataset

DATA_PATH = (
    Path(__file__).parent.parent / "data" / "sample_activities.yaml"
)

pytestmark = pytest.mark.asyncio


async def test_load_activity_dataset(db_session: AsyncSession) -> None:
    """Test loading activity dataset."""
    # Load raw data to get expected counts
    raw = yaml.safe_load(DATA_PATH.read_text())
    expected_activities = len(raw.get("activities", []))

    # Load dataset
    summary = await load_activity_dataset(str(DATA_PATH), db_session)

    # Verify summary
    assert summary["activities"] == expected_activities

    # Verify database count
    activity_count = (
        await db_session.execute(select(func.count()).select_from(Activity))
    ).scalar_one()
    assert activity_count == expected_activities


async def test_activity_types(db_session: AsyncSession) -> None:
    """Test that all activity types are loaded correctly."""
    await load_activity_dataset(str(DATA_PATH), db_session)

    # Get all activity types
    result = await db_session.execute(
        select(Activity.activity_type, func.count(Activity.id))
        .group_by(Activity.activity_type)
        .order_by(Activity.activity_type)
    )
    type_counts = dict(result.all())

    # Verify all expected types are present
    expected_types = {"Task", "Research", "Study", "Experiment", "Effort", "Thinking"}
    assert set(type_counts.keys()) == expected_types

    # Verify counts are positive
    for activity_type, count in type_counts.items():
        assert count > 0, f"{activity_type} should have at least 1 activity"


async def test_activity_fields(db_session: AsyncSession) -> None:
    """Test that activity fields are populated correctly."""
    await load_activity_dataset(str(DATA_PATH), db_session)

    # Test a specific activity
    activity = (
        await db_session.execute(
            select(Activity).where(Activity.id == "act:implement-auth")
        )
    ).scalar_one()

    assert activity.title == "Implement user authentication"
    assert activity.activity_type == "Task"
    assert activity.created_by == "alice"
    assert activity.url is not None
    assert activity.description is not None


async def test_activity_created_by(db_session: AsyncSession) -> None:
    """Test filtering activities by creator."""
    await load_activity_dataset(str(DATA_PATH), db_session)

    # Count activities by Alice
    alice_count = (
        await db_session.execute(
            select(func.count())
            .select_from(Activity)
            .where(Activity.created_by == "alice")
        )
    ).scalar_one()

    # Count activities by Bob
    bob_count = (
        await db_session.execute(
            select(func.count())
            .select_from(Activity)
            .where(Activity.created_by == "bob")
        )
    ).scalar_one()

    # Count activities by Charlie
    charlie_count = (
        await db_session.execute(
            select(func.count())
            .select_from(Activity)
            .where(Activity.created_by == "charlie")
        )
    ).scalar_one()

    # Verify all creators have activities
    assert alice_count > 0
    assert bob_count > 0
    assert charlie_count > 0


async def test_activity_identifiers(db_session: AsyncSession) -> None:
    """Test that activity identifiers are unique and follow convention."""
    await load_activity_dataset(str(DATA_PATH), db_session)

    # Get all identifiers
    result = await db_session.execute(select(Activity.id))
    identifiers = [row[0] for row in result.all()]

    # Verify uniqueness
    assert len(identifiers) == len(set(identifiers))

    # Verify all start with "act:"
    for identifier in identifiers:
        assert identifier.startswith("act:")
