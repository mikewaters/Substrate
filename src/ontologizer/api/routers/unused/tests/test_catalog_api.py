"""Tests for catalog API endpoints."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

@pytest.mark.skip
class TestCatalogAPI:
    """Tests for catalog API endpoints."""

    async def test_create_catalog(self, client: AsyncClient) -> None:
        """Test creating a catalog."""
        response = await client.post(
            "/catalogs",
            json={
                "id": "cat:test",
                "title": "Test Catalog",
                "description": "A test catalog",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "cat:test"
        assert data["title"] == "Test Catalog"
        assert "id" in data

    async def test_get_catalog(self, client: AsyncClient) -> None:
        """Test getting a catalog by ID."""
        # Create
        create_response = await client.post(
            "/catalogs",
            json={"id": "cat:test", "title": "Test Catalog"},
        )
        created = create_response.json()

        # Get
        response = await client.get(f"/catalogs/{created['id']}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created["id"]
        assert data["id"] == created["id"]

    async def test_list_catalogs(self, client: AsyncClient) -> None:
        """Test listing catalogs."""
        # Create some catalogs
        for i in range(3):
            await client.post(
                "/catalogs",
                json={"id": f"cat:test{i}", "title": f"Catalog {i}"},
            )

        # List
        response = await client.get("/catalogs")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["total"] == 3

    async def test_update_catalog(self, client: AsyncClient) -> None:
        """Test updating a catalog."""
        # Create
        create_response = await client.post(
            "/catalogs",
            json={"id": "cat:test", "title": "Test Catalog"},
        )
        created = create_response.json()

        # Update
        response = await client.put(
            f"/catalogs/{created['id']}",
            json={"title": "Updated Catalog"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Catalog"

    async def test_delete_catalog(self, client: AsyncClient) -> None:
        """Test deleting a catalog."""
        # Create
        create_response = await client.post(
            "/catalogs",
            json={"id": "cat:test", "title": "Test Catalog"},
        )
        created = create_response.json()

        # Delete
        response = await client.delete(f"/catalogs/{created['id']}")

        assert response.status_code == 204

@pytest.mark.skip
class TestRepositoryAPI:
    """Tests for repository API endpoints."""

    async def test_create_repository(self, client: AsyncClient) -> None:
        """Test creating a repository."""
        response = await client.post(
            "/repositories",
            json={
                "id": "repo:test",
                "title": "Test Repository",
                "service_name": "GitHub",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "repo:test"
        assert data["service_name"] == "GitHub"
        assert "id" in data

    async def test_get_repository(self, client: AsyncClient) -> None:
        """Test getting a repository by ID."""
        # Create
        create_response = await client.post(
            "/repositories",
            json={
                "id": "repo:test",
                "title": "Test Repository",
                "service_name": "GitHub",
            },
        )
        created = create_response.json()

        # Get
        response = await client.get(f"/repositories/{created['id']}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created["id"]
        assert data["id"] == created["id"]

    async def test_list_repositories(self, client: AsyncClient) -> None:
        """Test listing repositories."""
        # Create some repositories
        for i in range(2):
            await client.post(
                "/repositories",
                json={
                    "id": f"repo:test{i}",
                    "title": f"Repository {i}",
                    "service_name": "GitHub",
                },
            )

        # List
        response = await client.get("/repositories")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 2

@pytest.mark.skip
class TestPurposeAPI:
    """Tests for purpose API endpoints."""

    async def test_create_purpose(self, client: AsyncClient) -> None:
        """Test creating a purpose."""
        response = await client.post(
            "/purposes",
            json={
                "id": "purpose:test",
                "title": "Test Purpose",
                "description": "A test purpose",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "purpose:test"
        assert data["title"] == "Test Purpose"
        assert "id" in data

    async def test_get_purpose(self, client: AsyncClient) -> None:
        """Test getting a purpose by ID."""
        # Create
        create_response = await client.post(
            "/purposes",
            json={"id": "purpose:test", "title": "Test Purpose"},
        )
        created = create_response.json()

        # Get
        response = await client.get(f"/purposes/{created['id']}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created["id"]
        assert data["id"] == created["id"]

@pytest.mark.skip
class TestResourceAPI:
    """Tests for resource API endpoints."""

    async def test_create_resource(self, client: AsyncClient) -> None:
        """Test creating a resource."""
        # First create a catalog
        catalog_response = await client.post(
            "/catalogs",
            json={"id": "cat:test", "title": "Test Catalog"},
        )
        catalog = catalog_response.json()

        # Create resource
        response = await client.post(
            "/resources",
            json={
                "id": "res:test",
                "catalog": "cat:test",
                "catalog_id": catalog["id"],
                "title": "Test Resource",
                "location": "https://example.com/resource",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "res:test"
        assert data["title"] == "Test Resource"
        assert data["location"] == "https://example.com/resource"
        assert "id" in data

    async def test_get_resource(self, client: AsyncClient) -> None:
        """Test getting a resource by ID."""
        # Create catalog
        catalog_response = await client.post(
            "/catalogs",
            json={"id": "cat:test", "title": "Test Catalog"},
        )
        catalog = catalog_response.json()

        # Create resource
        create_response = await client.post(
            "/resources",
            json={
                "id": "res:test",
                "catalog": "cat:test",
                "catalog_id": catalog["id"],
                "title": "Test Resource",
                "location": "https://example.com/resource",
            },
        )
        created = create_response.json()

        # Get
        response = await client.get(f"/resources/{created['id']}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created["id"]
        assert data["id"] == created["id"]

    async def test_list_resources(self, client: AsyncClient) -> None:
        """Test listing resources."""
        # Create catalog
        catalog_response = await client.post(
            "/catalogs",
            json={"id": "cat:test", "title": "Test Catalog"},
        )
        catalog = catalog_response.json()

        # Create resources
        for i in range(3):
            await client.post(
                "/resources",
                json={
                    "id": f"res:test{i}",
                    "catalog": "cat:test",
                    "catalog_id": catalog["id"],
                    "title": f"Resource {i}",
                    "location": f"https://example.com/resource{i}",
                },
            )

        # List
        response = await client.get("/resources")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["total"] == 3

    async def test_list_resources_filtered_by_catalog(
        self, client: AsyncClient
    ) -> None:
        """Test listing resources filtered by catalog."""
        # Create two catalogs
        catalog1_response = await client.post(
            "/catalogs",
            json={"id": "cat:1", "title": "Catalog 1"},
        )
        catalog1 = catalog1_response.json()

        catalog2_response = await client.post(
            "/catalogs",
            json={"id": "cat:2", "title": "Catalog 2"},
        )
        catalog2 = catalog2_response.json()

        # Create resources in catalog1
        for i in range(2):
            await client.post(
                "/resources",
                json={
                    "id": f"res:1-{i}",
                    "catalog": "cat:1",
                    "catalog_id": catalog1["id"],
                    "title": f"Resource 1-{i}",
                    "location": f"https://example.com/resource-1-{i}",
                },
            )

        # Create resource in catalog2
        await client.post(
            "/resources",
            json={
                "id": "res:2-0",
                "catalog": "cat:2",
                "catalog_id": catalog2["id"],
                "location": "https://example.com/resource-2-0",
                "title": "Resource 2-0",
            },
        )

        # List resources in catalog1
        response = await client.get(f"/resources?catalog_id={catalog1['id']}")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 2
