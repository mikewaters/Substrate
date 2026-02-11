"""Integration tests for loading all dataset types."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ontologizer.relational.models import Taxonomy, Topic
from ontologizer.relational.models import Activity
from ontologizer.relational.models import Catalog
from ontologizer.loader.loader import load_yaml_dataset

DATA_DIR = Path(__file__).parent.parent / "data"

pytestmark = pytest.mark.asyncio


async def test_load_all_datasets(db_session: AsyncSession) -> None:
    """Test loading all datasets from directory."""
    summary = await load_yaml_dataset(str(DATA_DIR), db_session)

    # Verify summary contains all expected keys
    assert "taxonomies" in summary
    assert "topics" in summary
    assert "edges" in summary
    assert "closures" in summary
    assert "activities" in summary
    assert "catalogs" in summary
    assert "repositories" in summary
    assert "purposes" in summary
    assert "resources" in summary
    assert "topic_suggestions" in summary
    assert "matches" in summary

    # Verify counts are positive
    assert summary["taxonomies"] > 0
    assert summary["topics"] > 0
    assert summary["activities"] > 0
    assert summary["catalogs"] > 0
    assert summary["resources"] > 0

    # Verify database contains data
    taxonomy_count = (
        await db_session.execute(select(func.count()).select_from(Taxonomy))
    ).scalar_one()
    topic_count = (
        await db_session.execute(select(func.count()).select_from(Topic))
    ).scalar_one()
    activity_count = (
        await db_session.execute(select(func.count()).select_from(Activity))
    ).scalar_one()
    catalog_count = (
        await db_session.execute(select(func.count()).select_from(Catalog))
    ).scalar_one()

    assert taxonomy_count == summary["taxonomies"]
    assert topic_count == summary["topics"]
    assert activity_count == summary["activities"]
    assert catalog_count == summary["catalogs"]
