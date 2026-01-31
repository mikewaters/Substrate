"""Tests for classifier API endpoints."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _seed_topics(client: AsyncClient) -> str:
    tax_response = await client.post(
        "/taxonomies",
        json={"title": "Knowledge Base", "description": "Classifier test"},
    )
    assert tax_response.status_code == 201
    taxonomy = tax_response.json()
    taxonomy_id = taxonomy["id"]

    await client.post(
        "/topics",
        json={
            "taxonomy_id": taxonomy_id,
            "title": "Python Programming",
            "description": "General-purpose Python language",
            "status": "active",
        },
    )

    await client.post(
        "/topics",
        json={
            "taxonomy_id": taxonomy_id,
            "title": "FastAPI",
            "description": "Modern Python web framework",
            "aliases": ["Python Web Framework"],
            "status": "active",
        },
    )

    return taxonomy_id

@pytest.mark.skip
async def test_classifier_endpoint_returns_suggestions(client: AsyncClient) -> None:
    taxonomy_id = await _seed_topics(client)

    response = await client.post(
        "/classifier/suggestions",
        json={
            "text": "Python web framework",
            "taxonomy_id": taxonomy_id,
            "limit": 5,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["model_name"] == "simple-keyword-matcher"
    assert data["suggestions"], "Expected at least one suggestion"
    assert data["suggestions"][0]["title"] == "FastAPI"
    assert 0.0 <= data["suggestions"][0]["confidence"] <= 1.0

@pytest.mark.skip
async def test_classifier_endpoint_enforces_min_confidence(client: AsyncClient) -> None:
    taxonomy_id = await _seed_topics(client)

    response = await client.post(
        "/classifier/suggestions",
        json={
            "text": "Python web framework",
            "taxonomy_id": taxonomy_id,
            "min_confidence": 0.95,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert all(item["confidence"] >= 0.95 for item in data["suggestions"])

@pytest.mark.skip
async def test_classifier_endpoint_handles_blank_text(client: AsyncClient) -> None:
    response = await client.post(
        "/classifier/suggestions",
        json={"text": "   "},
    )

    assert response.status_code == 422
