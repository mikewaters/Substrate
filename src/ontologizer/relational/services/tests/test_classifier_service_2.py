"""Tests for ClassifierService."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ontologizer.relational.models import TopicSuggestion as TopicSuggestionORM
from ontologizer.schema import (
    TopicCreate,
    TopicSuggestionRequest,
)
from ontologizer.schema.taxonomy import TaxonomyCreate
from ontologizer.relational.services import (
    TaxonomyService,
    TopicTaxonomyService,
)
from ontologizer.relational.services.topic_suggestion import TopicSuggestionService

pytestmark = pytest.mark.asyncio


async def _create_sample_data(
    taxonomy_service: TaxonomyService, topic_service: TopicTaxonomyService
):
    taxonomy = await taxonomy_service.create(TaxonomyCreate(title="Knowledge Base"))

    await topic_service.create(
        TopicCreate(
            taxonomy_id=taxonomy.id,
            title="Python Programming",
            description="General-purpose programming language",
            aliases=["Python Language"],
            status="active",
        )
    )

    await topic_service.create(
        TopicCreate(
            taxonomy_id=taxonomy.id,
            title="FastAPI",
            description="Modern Python web framework",
            aliases=["Python Web Framework"],
            status="active",
        )
    )

    await topic_service.create(
        TopicCreate(
            taxonomy_id=taxonomy.id,
            title="Gardening",
            description="All about plants and gardens",
            status="active",
        )
    )

    return taxonomy


async def test_classifier_returns_ranked_suggestions(
    classifier_service: TopicSuggestionService,
    taxonomy_service: TaxonomyService,
    topic_service: TopicTaxonomyService,
    db_session: AsyncSession,
) -> None:
    taxonomy = await _create_sample_data(taxonomy_service, topic_service)

    response = await classifier_service.suggest_topics(
        TopicSuggestionRequest(
            text="Python web framework for APIs",
            taxonomy_id=taxonomy.id,
            limit=3,
        )
    )

    assert response.model_name == "simple-keyword-matcher"
    assert response.suggestions, "Expected at least one suggestion"

    top = response.suggestions[0]
    assert top.title == "FastAPI"
    assert top.rank == 1
    assert top.confidence > 0.3

    count_stmt = select(func.count()).select_from(TopicSuggestionORM)
    count = (await db_session.execute(count_stmt)).scalar_one()
    assert count >= len(response.suggestions)


async def test_classifier_respects_min_confidence(
    classifier_service: TopicSuggestionService,
    taxonomy_service: TaxonomyService,
    topic_service: TopicTaxonomyService,
) -> None:
    taxonomy = await _create_sample_data(taxonomy_service, topic_service)

    response = await classifier_service.suggest_topics(
        TopicSuggestionRequest(
            text="Python web framework",
            taxonomy_id=taxonomy.id,
            min_confidence=0.8,
        )
    )

    assert all(item.confidence >= 0.8 for item in response.suggestions)


async def test_classifier_avoids_duplicate_records(
    classifier_service: TopicSuggestionService,
    taxonomy_service: TaxonomyService,
    topic_service: TopicTaxonomyService,
    db_session: AsyncSession,
) -> None:
    taxonomy = await _create_sample_data(taxonomy_service, topic_service)

    request = TopicSuggestionRequest(
        text="Python web framework",
        taxonomy_id=taxonomy.id,
    )

    first_response = await classifier_service.suggest_topics(request)
    first_count = (
        await db_session.execute(select(func.count()).select_from(TopicSuggestionORM))
    ).scalar_one()

    await classifier_service.suggest_topics(request)

    second_count = (
        await db_session.execute(select(func.count()).select_from(TopicSuggestionORM))
    ).scalar_one()

    assert first_count == second_count
    assert first_count >= len(first_response.suggestions)
