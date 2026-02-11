"""Tests for taxonomy API endpoints."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

@pytest.mark.skip
class TestTaxonomyCreate:
    """Tests for POST /taxonomies."""

    async def test_create_taxonomy(self, client: AsyncClient) -> None:
        """Test creating a taxonomy."""
        response = await client.post(
            "/taxonomies",
            json={
                "title": "Test Taxonomy",
                "description": "A test taxonomy",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Test Taxonomy"
        assert data["description"] == "A test taxonomy"
        assert "id" in data
        assert "created_at" in data

    async def test_create_taxonomy_minimal(self, client: AsyncClient) -> None:
        """Test creating a taxonomy with minimal fields."""
        response = await client.post(
            "/taxonomies",
            json={"title": "Minimal Taxonomy"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Minimal Taxonomy"

@pytest.mark.skip
class TestTaxonomyRead:
    """Tests for GET /taxonomies endpoints."""

    async def test_get_taxonomy(self, client: AsyncClient) -> None:
        """Test getting a taxonomy by ID."""
        # Create
        create_response = await client.post(
            "/taxonomies",
            json={"title": "Test Taxonomy"},
        )
        created = create_response.json()

        # Get
        response = await client.get(f"/taxonomies/{created['id']}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created["id"]
        assert data["title"] == created["title"]

    async def test_get_taxonomy_not_found(self, client: AsyncClient) -> None:
        """Test getting a non-existent taxonomy returns 404."""
        response = await client.get("/taxonomies/00000000-0000-0000-0000-000000000000")

        assert response.status_code == 404
        assert response.headers["content-type"] == "application/problem+json"

    async def test_list_taxonomies_empty(self, client: AsyncClient) -> None:
        """Test listing taxonomies when none exist."""
        response = await client.get("/taxonomies")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_list_taxonomies_with_data(self, client: AsyncClient) -> None:
        """Test listing taxonomies with data."""
        # Create some taxonomies
        for i in range(3):
            await client.post("/taxonomies", json={"title": f"Taxonomy {i}"})

        # List
        response = await client.get("/taxonomies")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["total"] == 3

    async def test_list_taxonomies_with_pagination(self, client: AsyncClient) -> None:
        """Test listing taxonomies with pagination."""
        # Create some taxonomies
        for i in range(5):
            await client.post("/taxonomies", json={"title": f"Taxonomy {i}"})

        # List with pagination
        response = await client.get("/taxonomies?limit=2&offset=1")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["limit"] == 2
        assert data["offset"] == 1

@pytest.mark.skip
class TestTaxonomyUpdate:
    """Tests for PUT /taxonomies/{id}."""

    async def test_update_taxonomy(self, client: AsyncClient) -> None:
        """Test updating a taxonomy."""
        # Create
        create_response = await client.post(
            "/taxonomies",
            json={"title": "Original Title"},
        )
        created = create_response.json()

        # Update
        response = await client.put(
            f"/taxonomies/{created['id']}",
            json={"id": created["id"], "title": "Updated Title"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"
        assert data["id"] == created["id"]

    async def test_update_taxonomy_not_found(self, client: AsyncClient) -> None:
        """Test updating a non-existent taxonomy returns 404."""
        # with pytest.raises(NotFoundError):
        response = await client.put(
            "/taxonomies/00000000-0000-0000-0000-000000000000",
            json={"title": "New Title"},
        )

        assert response.status_code == 404

@pytest.mark.skip
class TestTaxonomyDelete:
    """Tests for DELETE /taxonomies/{id}."""

    async def test_delete_taxonomy(self, client: AsyncClient) -> None:
        """Test deleting a taxonomy."""
        # Create
        create_response = await client.post(
            "/taxonomies",
            json={"title": "To Delete"},
        )
        created = create_response.json()
        # Delete
        response = await client.delete(f"/taxonomies/{created['id']}")

        assert response.status_code == 204

        # Verify deleted
        get_response = await client.get(f"/taxonomies/{created['id']}")
        assert get_response.status_code == 404

    async def test_delete_taxonomy_not_found(self, client: AsyncClient) -> None:
        """Test deleting a non-existent taxonomy returns 404."""
        # with pytest.raises(NotFoundError):
        response = await client.delete(
            "/taxonomies/00000000-0000-0000-0000-000000000000"
        )
        # import pdb; pdb.set_trace()
        assert response.status_code == 404
