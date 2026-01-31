"""Integration test for the async YAML dataset loader."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ontology.relational.models import Taxonomy, Topic, TopicClosure, TopicEdge
from ontology.loader.loader import load_yaml_dataset

DATA_PATH = (
    Path(__file__).parent.parent / "data" / "sample_taxonomies.yaml"
)

pytestmark = pytest.mark.asyncio


async def test_load_sample_dataset(db_session: AsyncSession) -> None:
    raw = yaml.safe_load(DATA_PATH.read_text())
    expected_taxonomies = len(raw.get("taxonomies", []))
    expected_topics = sum(len(t.get("topics", [])) for t in raw.get("taxonomies", []))

    summary = await load_yaml_dataset(str(DATA_PATH), db_session)

    taxonomy_count = (
        await db_session.execute(select(func.count()).select_from(Taxonomy))
    ).scalar_one()
    topic_count = (
        await db_session.execute(select(func.count()).select_from(Topic))
    ).scalar_one()
    edge_count = (
        await db_session.execute(select(func.count()).select_from(TopicEdge))
    ).scalar_one()
    closure_count = (
        await db_session.execute(select(func.count()).select_from(TopicClosure))
    ).scalar_one()

    assert taxonomy_count == summary["taxonomies"] == expected_taxonomies
    assert topic_count == summary["topics"] == expected_topics
    assert edge_count >= topic_count - taxonomy_count
    assert summary["edges"] == edge_count
    assert summary["closures"] == closure_count

    tech_iot = (
        await db_session.execute(select(Topic).where(Topic.id == "tech:iot"))
    ).scalar_one()
    parent_edges = (
        (
            await db_session.execute(
                select(TopicEdge).where(TopicEdge.child_id == tech_iot.id)
            )
        )
        .scalars()
        .all()
    )
    parent_ids = set()
    for edge in parent_edges:
        parent = (
            await db_session.execute(select(Topic).where(Topic.id == edge.parent_id))
        ).scalar_one()
        parent_ids.add(parent.id)
    assert {"tech:hardware", "tech:cloud"}.issubset(parent_ids)

    self_closure = (
        await db_session.execute(
            select(TopicClosure).where(
                TopicClosure.ancestor_id == tech_iot.id,
                TopicClosure.descendant_id == tech_iot.id,
                TopicClosure.depth == 0,
            )
        )
    ).scalar_one_or_none()
    assert self_closure is not None

    tech_mlops = (
        await db_session.execute(select(Topic).where(Topic.id == "tech:mlops"))
    ).scalar_one()
    mlops_closures = (
        (
            await db_session.execute(
                select(TopicClosure).where(TopicClosure.descendant_id == tech_mlops.id)
            )
        )
        .scalars()
        .all()
    )
    ancestor_ids = set()
    for closure in mlops_closures:
        ancestor = (
            await db_session.execute(
                select(Topic).where(Topic.id == closure.ancestor_id)
            )
        ).scalar_one()
        ancestor_ids.add(ancestor.id)
    assert "tech:software" in ancestor_ids
    assert all(c.depth >= 0 for c in mlops_closures)

    health_recovery = (
        await db_session.execute(select(Topic).where(Topic.id == "health:recovery"))
    ).scalar_one()
    recovery_edges = (
        (
            await db_session.execute(
                select(TopicEdge).where(TopicEdge.child_id == health_recovery.id)
            )
        )
        .scalars()
        .all()
    )
    rec_ids = set()
    for edge in recovery_edges:
        parent = (
            await db_session.execute(select(Topic).where(Topic.id == edge.parent_id))
        ).scalar_one()
        rec_ids.add(parent.id)
    assert rec_ids == {"health:fitness", "health:sleep"}

    root_identifiers = [
        "tech:software",
        "health:nutrition",
        "life:productivity",
        "know:capture",
        "work:communication",
    ]
    for identifier in root_identifiers:
        root_topic = (
            await db_session.execute(select(Topic).where(Topic.id == identifier))
        ).scalar_one()
        count = (
            await db_session.execute(
                select(func.count())
                .select_from(TopicEdge)
                .where(TopicEdge.child_id == root_topic.id)
            )
        ).scalar_one()
        assert count == 0
