"""Tests for topic API endpoints with async client."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

@pytest.mark.skip
class TestTopicCreate:
    """Tests for POST /topics."""

    async def test_create_topic(self, client: AsyncClient) -> None:
        """Test creating a topic."""
        # Create taxonomy first
        tax_response = await client.post("/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy = tax_response.json()

        # Create topic
        response = await client.post(
            "/topics",
            json={
                "taxonomy_id": taxonomy["id"],
                "title": "Test Topic",
                "description": "A test topic",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Test Topic"
        assert data["description"] == "A test topic"
        assert data["slug"] == "test-topic"
        assert "id" in data

@pytest.mark.skip
class TestTopicRead:
    """Tests for GET /topics endpoints."""

    async def test_get_topic(self, client: AsyncClient) -> None:
        """Test getting a topic by ID."""
        # Create taxonomy and topic
        tax_response = await client.post("/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy = tax_response.json()

        create_response = await client.post(
            "/topics",
            json={"taxonomy_id": taxonomy["id"], "title": "Test Topic"},
        )
        created = create_response.json()

        # Get
        response = await client.get(f"/topics/{created['id']}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created["id"]
        assert data["title"] == created["title"]

    async def test_get_topic_not_found(self, client: AsyncClient) -> None:
        """Test getting a non-existent topic returns 404."""
        response = await client.get("/topics/00000000-0000-0000-0000-000000000000")

        assert response.status_code == 404

@pytest.mark.skip
class TestTopicUpdate:
    """Tests for PUT /topics/{id}."""

    async def test_update_topic(self, client: AsyncClient) -> None:
        """Test updating a topic."""
        # Create taxonomy and topic
        tax_response = await client.post("/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy = tax_response.json()

        create_response = await client.post(
            "/topics",
            json={"taxonomy_id": taxonomy["id"], "title": "Original Title"},
        )
        created = create_response.json()

        # Update
        response = await client.put(
            f"/topics/{created['id']}",
            json={"title": "Updated Title"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"

    async def test_deprecate_topic(self, client: AsyncClient) -> None:
        """Test deprecating a topic."""
        # Create taxonomy and topic
        tax_response = await client.post("/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy = tax_response.json()

        create_response = await client.post(
            "/topics",
            json={
                "taxonomy_id": taxonomy["id"],
                "title": "Test Topic",
                "status": "active",
            },
        )
        created = create_response.json()

        # Deprecate
        response = await client.post(f"/topics/{created['id']}/deprecate")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deprecated"

@pytest.mark.skip
class TestTopicSearch:
    """Tests for POST /topics/search."""

    async def test_search_topics(self, client: AsyncClient) -> None:
        """Test searching topics."""
        # Create taxonomy
        tax_response = await client.post("/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy = tax_response.json()

        # Create topics
        await client.post(
            "/topics",
            json={"taxonomy_id": taxonomy["id"], "title": "Python Programming"},
        )
        await client.post(
            "/topics",
            json={"taxonomy_id": taxonomy["id"], "title": "JavaScript Programming"},
        )
        await client.post(
            "/topics",
            json={"taxonomy_id": taxonomy["id"], "title": "Data Science"},
        )

        # Search
        response = await client.post(
            "/topics/search",
            json={"query": "Programming"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2


@pytest.mark.skip("need to fix the list filtering to add more fields")
class TestTopicList:
    """Tests for GET /topics."""

    async def test_list_topics(self, client: AsyncClient) -> None:
        """Test listing topics."""
        # Create taxonomy
        tax_response = await client.post("/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy = tax_response.json()

        # Create topics
        for i in range(3):
            await client.post(
                "/topics",
                json={"taxonomy_id": taxonomy["id"], "title": f"Topic {i}"},
            )

        # List
        response = await client.get("/topics")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    async def test_list_topics_with_status_filter(self, client: AsyncClient) -> None:
        """Test listing topics with status filter."""
        # Create taxonomy
        tax_response = await client.post("/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy = tax_response.json()

        # Create topics
        await client.post(
            "/topics",
            json={
                "taxonomy_id": taxonomy["id"],
                "title": "Draft Topic",
                "status": "draft",
            },
        )
        await client.post(
            "/topics",
            json={
                "taxonomy_id": taxonomy["id"],
                "title": "Active Topic",
                "status": "active",
            },
        )

        # List with filter
        response = client.get("/topics?status=active")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "active"

    def test_list_topics_with_path_prefix(self, client: AsyncClient) -> None:
        """Test listing topics filtered by materialized path prefix."""
        tax_response = client.post("/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy = tax_response.json()

        root = client.post(
            "/topics",
            json={"taxonomy_id": taxonomy["id"], "title": "Root"},
        ).json()

        child = client.post(
            "/topics",
            json={"taxonomy_id": taxonomy["id"], "title": "Child"},
        ).json()

        other = client.post(
            "/topics",
            json={"taxonomy_id": taxonomy["id"], "title": "Other"},
        ).json()

        client.post(
            "/topics/edges",
            json={"parent_id": root["id"], "child_id": child["id"], "role": "broader"},
        )

        response = client.get(f"/topics?path_prefix=/{root['slug']}")

        assert response.status_code == 200
        data = response.json()
        ids = {item["id"] for item in data["items"]}
        assert root["id"] in ids
        assert child["id"] in ids
        assert other["id"] not in ids

@pytest.mark.skip
class TestTopicDiscovery:
    """Tests for discovery endpoints."""

    async def test_find_orphan_topics(self, client: AsyncClient) -> None:
        """Test finding orphan topics."""
        # Create taxonomy
        tax_response = await client.post("/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy = tax_response.json()

        # Create topics
        parent_response = await client.post(
            "/topics",
            json={"taxonomy_id": taxonomy["id"], "title": "Parent Topic"},
        )
        parent = parent_response.json()

        child_response = await client.post(
            "/topics",
            json={"taxonomy_id": taxonomy["id"], "title": "Child Topic"},
        )
        child = child_response.json()

        orphan_response = await client.post(
            "/topics",
            json={"taxonomy_id": taxonomy["id"], "title": "Orphan Topic"},
        )
        orphan = orphan_response.json()

        # Create edge
        await client.post(
            "/topics/edges",
            json={"parent_id": parent["id"], "child_id": child["id"]},
        )

        # Find orphans
        response = await client.get("/topics/orphans")

        assert response.status_code == 200
        data = response.json()
        orphan_ids = [t["id"] for t in data]
        assert parent["id"] in orphan_ids
        assert orphan["id"] in orphan_ids
        assert child["id"] not in orphan_ids

    async def test_find_multi_parent_topics(self, client: AsyncClient) -> None:
        """Test finding topics with multiple parents."""
        # Create taxonomy
        tax_response = await client.post("/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy = tax_response.json()

        # Create topics
        p1_response = await client.post(
            "/topics",
            json={"taxonomy_id": taxonomy["id"], "title": "Parent 1"},
        )
        p1 = p1_response.json()

        p2_response = await client.post(
            "/topics",
            json={"taxonomy_id": taxonomy["id"], "title": "Parent 2"},
        )
        p2 = p2_response.json()

        child_response = await client.post(
            "/topics",
            json={"taxonomy_id": taxonomy["id"], "title": "Multi-Parent Child"},
        )
        child = child_response.json()

        # Create edges
        await client.post(
            "/topics/edges", json={"parent_id": p1["id"], "child_id": child["id"]}
        )
        await client.post(
            "/topics/edges", json={"parent_id": p2["id"], "child_id": child["id"]}
        )

        # Find multi-parent topics
        response = await client.get("/topics/multi-parent")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == child["id"]

@pytest.mark.skip
class TestTopicHierarchy:
    """Tests for hierarchy traversal endpoints."""

    async def test_get_ancestors(self, client: AsyncClient) -> None:
        """Test getting ancestors."""
        # Create taxonomy
        tax_response = await client.post("/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy = tax_response.json()

        # Create hierarchy: A -> B -> C
        a_response = await client.post(
            "/topics",
            json={"taxonomy_id": taxonomy["id"], "title": "Topic A"},
        )
        a = a_response.json()

        b_response = await client.post(
            "/topics",
            json={"taxonomy_id": taxonomy["id"], "title": "Topic B"},
        )
        b = b_response.json()

        c_response = await client.post(
            "/topics",
            json={"taxonomy_id": taxonomy["id"], "title": "Topic C"},
        )
        c = c_response.json()

        await client.post(
            "/topics/edges", json={"parent_id": a["id"], "child_id": b["id"]}
        )
        await client.post(
            "/topics/edges", json={"parent_id": b["id"], "child_id": c["id"]}
        )

        # Get ancestors of C
        response = await client.get(f"/topics/{c['id']}/ancestors")

        assert response.status_code == 200
        data = response.json()
        ancestor_ids = [t["id"] for t in data]
        assert a["id"] in ancestor_ids
        assert b["id"] in ancestor_ids

    async def test_get_descendants(self, client: AsyncClient) -> None:
        """Test getting descendants."""
        # Create taxonomy
        tax_response = await client.post("/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy = tax_response.json()

        # Create hierarchy: A -> B -> C
        a_response = await client.post(
            "/topics",
            json={"taxonomy_id": taxonomy["id"], "title": "Topic A"},
        )
        a = a_response.json()

        b_response = await client.post(
            "/topics",
            json={"taxonomy_id": taxonomy["id"], "title": "Topic B"},
        )
        b = b_response.json()

        c_response = await client.post(
            "/topics",
            json={"taxonomy_id": taxonomy["id"], "title": "Topic C"},
        )
        c = c_response.json()

        await client.post(
            "/topics/edges", json={"parent_id": a["id"], "child_id": b["id"]}
        )
        await client.post(
            "/topics/edges", json={"parent_id": b["id"], "child_id": c["id"]}
        )

        # Get descendants of A
        response = await client.get(f"/topics/{a['id']}/descendants")

        assert response.status_code == 200
        data = response.json()
        descendant_ids = [t["id"] for t in data]
        assert b["id"] in descendant_ids
        assert c["id"] in descendant_ids

@pytest.mark.skip
class TestTopicEdges:
    """Tests for edge endpoints."""

    async def test_create_edge(self, client: AsyncClient) -> None:
        """Test creating an edge."""
        # Create taxonomy and topics
        tax_response = await client.post("/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy = tax_response.json()

        parent_response = await client.post(
            "/topics",
            json={"taxonomy_id": taxonomy["id"], "title": "Parent"},
        )
        parent = parent_response.json()

        child_response = await client.post(
            "/topics",
            json={"taxonomy_id": taxonomy["id"], "title": "Child"},
        )
        child = child_response.json()

        # Create edge
        response = await client.post(
            "/topics/edges",
            json={
                "parent_id": parent["id"],
                "child_id": child["id"],
                "role": "broader",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["parent_id"] == parent["id"]
        assert data["child_id"] == child["id"]
        assert data["role"] == "broader"

    async def test_create_edge_prevents_cycle(self, client: AsyncClient) -> None:
        """Test that creating a cycle is prevented."""
        # Create taxonomy and topics
        tax_response = await client.post("/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy = tax_response.json()

        a_response = await client.post(
            "/topics",
            json={"taxonomy_id": taxonomy["id"], "title": "Topic A"},
        )
        a = a_response.json()

        b_response = await client.post(
            "/topics",
            json={"taxonomy_id": taxonomy["id"], "title": "Topic B"},
        )
        b = b_response.json()

        # Create edge A -> B
        await client.post(
            "/topics/edges",
            json={"parent_id": a["id"], "child_id": b["id"]},
        )

        # Try to create edge B -> A (would create cycle)
        response = await client.post(
            "/topics/edges",
            json={"parent_id": b["id"], "child_id": a["id"]},
        )

        assert response.status_code == 422
        assert "cycle" in response.text.lower()

    async def test_delete_edge(self, client: AsyncClient) -> None:
        """Test deleting an edge."""
        # Create taxonomy and topics
        tax_response = await client.post("/taxonomies", json={"title": "Test Taxonomy"})
        taxonomy = tax_response.json()

        parent_response = await client.post(
            "/topics",
            json={"taxonomy_id": taxonomy["id"], "title": "Parent"},
        )
        parent = parent_response.json()

        child_response = await client.post(
            "/topics",
            json={"taxonomy_id": taxonomy["id"], "title": "Child"},
        )
        child = child_response.json()

        # Create edge
        await client.post(
            "/topics/edges",
            json={"parent_id": parent["id"], "child_id": child["id"]},
        )

        # Delete edge
        response = await client.delete(f"/topics/edges/{parent['id']}/{child['id']}")

        assert response.status_code == 204
