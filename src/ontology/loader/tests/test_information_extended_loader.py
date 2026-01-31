"""Integration tests for extended information dataset loader."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ontology.relational.models.classifier import TopicSuggestion, Match
from ontology.relational.models import Taxonomy, Topic
from ontology.loader.loader import (
    load_taxonomy_dataset,
    load_information_extended_dataset,
)

TAXONOMY_PATH = (
    Path(__file__).parent.parent / "data" / "sample_taxonomies.yaml"
)
EXTENDED_PATH = (
    Path(__file__).parent.parent
    / "data"
    / "sample_information_extended.yaml"
)

pytestmark = pytest.mark.asyncio


async def test_load_information_extended_dataset(db_session: AsyncSession) -> None:
    """Test loading extended information dataset."""
    # First load taxonomies (required for references)
    await load_taxonomy_dataset(str(TAXONOMY_PATH), db_session)

    # Load raw data to get expected counts
    raw = yaml.safe_load(EXTENDED_PATH.read_text())
    expected_suggestions = len(raw.get("topic_suggestions", []))
    expected_matches = len(raw.get("matches", []))

    # Load extended dataset
    summary = await load_information_extended_dataset(str(EXTENDED_PATH), db_session)

    # Verify summary
    assert summary["topic_suggestions"] == expected_suggestions
    assert summary["matches"] == expected_matches

    # Verify database counts
    suggestion_count = (
        await db_session.execute(select(func.count()).select_from(TopicSuggestion))
    ).scalar_one()
    match_count = (
        await db_session.execute(select(func.count()).select_from(Match))
    ).scalar_one()

    assert suggestion_count == expected_suggestions
    assert match_count == expected_matches


async def test_topic_suggestion_fields(db_session: AsyncSession) -> None:
    """Test that topic suggestion fields are populated correctly."""
    await load_taxonomy_dataset(str(TAXONOMY_PATH), db_session)
    await load_information_extended_dataset(str(EXTENDED_PATH), db_session)

    # Get a specific suggestion
    suggestions = (
        (
            await db_session.execute(
                select(TopicSuggestion)
                .where(
                    TopicSuggestion.input_text
                    == "Building a machine learning model for text classification"
                )
                .order_by(TopicSuggestion.rank)
            )
        )
        .scalars()
        .all()
    )

    assert len(suggestions) >= 2

    # Check first suggestion (highest confidence)
    first_suggestion = suggestions[0]
    assert first_suggestion.rank == 1
    assert first_suggestion.confidence > 0.5
    assert first_suggestion.model_name == "claude-3-opus"
    assert first_suggestion.input_hash is not None
    assert len(first_suggestion.input_hash) == 64  # SHA256 hash

    # Verify it links to correct topic
    topic = await db_session.get(Topic, first_suggestion.topic_id)
    assert topic.id == "tech:ai"


async def test_topic_suggestion_ranking(db_session: AsyncSession) -> None:
    """Test that topic suggestions are ranked by confidence."""
    await load_taxonomy_dataset(str(TAXONOMY_PATH), db_session)
    await load_information_extended_dataset(str(EXTENDED_PATH), db_session)

    # Get suggestions for a specific input
    suggestions = (
        (
            await db_session.execute(
                select(TopicSuggestion)
                .where(
                    TopicSuggestion.input_text
                    == "Building a machine learning model for text classification"
                )
                .order_by(TopicSuggestion.rank)
            )
        )
        .scalars()
        .all()
    )

    # Verify ranking order
    for i in range(len(suggestions) - 1):
        assert suggestions[i].rank < suggestions[i + 1].rank
        assert suggestions[i].confidence >= suggestions[i + 1].confidence


async def test_topic_suggestion_context(db_session: AsyncSession) -> None:
    """Test that topic suggestion context is stored correctly."""
    await load_taxonomy_dataset(str(TAXONOMY_PATH), db_session)
    await load_information_extended_dataset(str(EXTENDED_PATH), db_session)

    # Get a suggestion with context
    suggestion = (
        await db_session.execute(
            select(TopicSuggestion)
            .where(
                TopicSuggestion.input_text
                == "Building a machine learning model for text classification"
            )
            .where(TopicSuggestion.rank == 1)
        )
    ).scalar_one()

    assert isinstance(suggestion.context, dict)
    assert "keywords" in suggestion.context
    assert isinstance(suggestion.context["keywords"], list)


async def test_match_entity_types(db_session: AsyncSession) -> None:
    """Test that matches are created for both topics and taxonomies."""
    await load_taxonomy_dataset(str(TAXONOMY_PATH), db_session)
    await load_information_extended_dataset(str(EXTENDED_PATH), db_session)

    # Count matches by entity type
    result = await db_session.execute(
        select(Match.entity_type, func.count(Match.id))
        .group_by(Match.entity_type)
        .order_by(Match.entity_type)
    )
    type_counts = dict(result.all())

    # Verify both types are present
    assert "topic" in type_counts
    assert "taxonomy" in type_counts
    assert type_counts["topic"] > 0
    assert type_counts["taxonomy"] > 0


async def test_match_external_systems(db_session: AsyncSession) -> None:
    """Test that matches are created for multiple external systems."""
    await load_taxonomy_dataset(str(TAXONOMY_PATH), db_session)
    await load_information_extended_dataset(str(EXTENDED_PATH), db_session)

    # Get all unique systems
    result = await db_session.execute(select(Match.system).distinct())
    systems = [row[0] for row in result.all()]

    # Verify multiple systems are represented
    assert len(systems) > 1
    assert "wikidata" in systems


async def test_match_types(db_session: AsyncSession) -> None:
    """Test that different match types are loaded correctly."""
    await load_taxonomy_dataset(str(TAXONOMY_PATH), db_session)
    await load_information_extended_dataset(str(EXTENDED_PATH), db_session)

    # Get all unique match types
    result = await db_session.execute(select(Match.match_type).distinct())
    match_types = [row[0] for row in result.all()]

    # Verify multiple match types are represented
    assert len(match_types) > 1
    expected_types = ["exactMatch", "closeMatch", "broadMatch", "relatedMatch"]
    for expected_type in expected_types:
        if expected_type in match_types:
            # At least some of the expected types should be present
            break
    else:
        pytest.fail("No expected match types found")


async def test_match_fields(db_session: AsyncSession) -> None:
    """Test that match fields are populated correctly."""
    await load_taxonomy_dataset(str(TAXONOMY_PATH), db_session)
    await load_information_extended_dataset(str(EXTENDED_PATH), db_session)

    # Get a specific match
    match = (
        await db_session.execute(
            select(Match)
            .where(Match.system == "wikidata")
            .where(Match.external_id == "Q11660")
        )
    ).scalar_one()

    assert match.entity_type == "topic"
    assert match.match_type == "exactMatch"
    assert match.confidence > 0.5
    assert isinstance(match.evidence, dict)

    # Verify it links to correct topic
    topic = await db_session.get(Topic, match.entity_id)
    assert topic.id == "tech:ai"


async def test_match_evidence(db_session: AsyncSession) -> None:
    """Test that match evidence is stored correctly."""
    await load_taxonomy_dataset(str(TAXONOMY_PATH), db_session)
    await load_information_extended_dataset(str(EXTENDED_PATH), db_session)

    # Get a match with evidence
    match = (
        await db_session.execute(
            select(Match)
            .where(Match.system == "wikidata")
            .where(Match.external_id == "Q11016")
        )
    ).scalar_one()

    assert isinstance(match.evidence, dict)
    assert "source" in match.evidence
    assert match.evidence["source"] == "manual_curation"


async def test_suggestion_taxonomy_relationship(db_session: AsyncSession) -> None:
    """Test that suggestions are correctly linked to taxonomies."""
    await load_taxonomy_dataset(str(TAXONOMY_PATH), db_session)
    await load_information_extended_dataset(str(EXTENDED_PATH), db_session)

    # Get a suggestion with taxonomy
    result = await db_session.execute(
        select(TopicSuggestion).where(TopicSuggestion.taxonomy_id.is_not(None)).limit(1)
    )
    suggestion = result.scalars().first()

    assert suggestion is not None
    assert suggestion.taxonomy_id is not None

    # Verify taxonomy exists
    taxonomy = await db_session.get(Taxonomy, suggestion.taxonomy_id)
    assert taxonomy is not None
