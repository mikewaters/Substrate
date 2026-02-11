"""Tests for health endpoints."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_health_endpoint(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


async def test_root_endpoint(client: AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Ontology API"
    assert data["version"] == "0.1.0"
    assert data["docs"] == "/docs"
