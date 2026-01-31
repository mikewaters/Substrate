"""Tests for topic query router endpoints."""

from datetime import datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from ontology.relational.models import Taxonomy, Topic, TopicEdge

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def sample_taxonomy(db_session: AsyncSession) -> Taxonomy:
    """Create a sample taxonomy for testing."""
    taxonomy = Taxonomy(
        id="test:taxonomy",
        title="Test Taxonomy",
        description="A taxonomy for testing",
    )
    db_session.add(taxonomy)
    await db_session.commit()
    await db_session.refresh(taxonomy)
    return taxonomy


@pytest_asyncio.fixture
async def sample_topics(
    db_session: AsyncSession, sample_taxonomy: Taxonomy
) -> list[Topic]:
    """Create sample topics for testing."""
    topics = [
        Topic(
            id="test:topic:1",
            taxonomy_id=sample_taxonomy.id,
            title="Active Topic",
            slug="active-topic",
            description="An active topic for testing",
            status="active",
        ),
        Topic(
            id="test:topic:2",
            taxonomy_id=sample_taxonomy.id,
            title="Draft Topic",
            slug="draft-topic",
            description="A draft topic for testing",
            status="draft",
        ),
        Topic(
            id="test:topic:3",
            taxonomy_id=sample_taxonomy.id,
            title="Deprecated Topic",
            slug="deprecated-topic",
            status="deprecated",
        ),
        Topic(
            id="test:topic:4",
            taxonomy_id=sample_taxonomy.id,
            title="Search Test Topic",
            slug="search-test-topic",
            description="This topic contains searchable content",
            status="active",
        ),
    ]

    for topic in topics:
        db_session.add(topic)

    await db_session.commit()

    for topic in topics:
        await db_session.refresh(topic)

    return topics


@pytest_asyncio.fixture
async def sample_edges(
    db_session: AsyncSession, sample_topics: list[Topic]
) -> list[TopicEdge]:
    """Create sample topic edges for testing relationships."""
    edges = [
        TopicEdge(
            parent_id=sample_topics[0].id,
            child_id=sample_topics[1].id,
            role="broader",
            is_primary=True,
        ),
        TopicEdge(
            parent_id=sample_topics[0].id,
            child_id=sample_topics[2].id,
            role="broader",
            is_primary=True,
        ),
        TopicEdge(
            parent_id=sample_topics[1].id,
            child_id=sample_topics[3].id,
            role="related",
            is_primary=False,
        ),
    ]

    for edge in edges:
        db_session.add(edge)

    await db_session.commit()

    for edge in edges:
        await db_session.refresh(edge)

    return edges


@pytest_asyncio.fixture
async def hierarchical_topics(
    db_session: AsyncSession, sample_taxonomy: Taxonomy
) -> dict[str, Topic]:
    """Create a hierarchical topic structure for advanced testing.

    Structure:
        Root
        ├── Programming
        │   ├── Python
        │   │   ├── Django
        │   │   └── FastAPI
        │   └── JavaScript
        │       ├── React
        │       └── Vue
        ├── Databases
        │   ├── SQL
        │   │   ├── PostgreSQL
        │   │   └── MySQL
        │   └── NoSQL
        │       └── MongoDB
        └── DevOps
            ├── Docker
            └── Kubernetes
    """
    topics_data = [
        ("root", "Root", "The root of all topics"),
        ("programming", "Programming", "Programming languages and frameworks"),
        ("python", "Python", "Python programming language"),
        ("django", "Django", "Django web framework"),
        ("fastapi", "FastAPI", "FastAPI web framework"),
        ("javascript", "JavaScript", "JavaScript programming language"),
        ("react", "React", "React UI library"),
        ("vue", "Vue", "Vue.js framework"),
        ("databases", "Databases", "Database systems"),
        ("sql", "SQL", "SQL databases"),
        ("postgresql", "PostgreSQL", "PostgreSQL database"),
        ("mysql", "MySQL", "MySQL database"),
        ("nosql", "NoSQL", "NoSQL databases"),
        ("mongodb", "MongoDB", "MongoDB database"),
        ("devops", "DevOps", "DevOps tools and practices"),
        ("docker", "Docker", "Docker containerization"),
        ("kubernetes", "Kubernetes", "Kubernetes orchestration"),
    ]

    topics = {}
    for slug, title, description in topics_data:
        topic = Topic(
            id=f"test:topic:hier:{slug}",
            taxonomy_id=sample_taxonomy.id,
            title=title,
            slug=slug,
            description=description,
            status="active",
        )
        db_session.add(topic)
        topics[slug] = topic

    await db_session.commit()

    for topic in topics.values():
        await db_session.refresh(topic)

    edges_data = [
        ("root", "programming", "broader"),
        ("root", "databases", "broader"),
        ("root", "devops", "broader"),
        ("programming", "python", "broader"),
        ("programming", "javascript", "broader"),
        ("python", "django", "broader"),
        ("python", "fastapi", "broader"),
        ("javascript", "react", "broader"),
        ("javascript", "vue", "broader"),
        ("databases", "sql", "broader"),
        ("databases", "nosql", "broader"),
        ("sql", "postgresql", "broader"),
        ("sql", "mysql", "broader"),
        ("nosql", "mongodb", "broader"),
        ("devops", "docker", "broader"),
        ("devops", "kubernetes", "broader"),
        ("django", "postgresql", "related"),
        ("fastapi", "postgresql", "related"),
    ]

    for parent_slug, child_slug, role in edges_data:
        edge = TopicEdge(
            parent_id=topics[parent_slug].id,
            child_id=topics[child_slug].id,
            role=role,
            is_primary=(role == "broader"),
        )
        db_session.add(edge)

    await db_session.commit()

    return topics


async def test_list_taxonomy_topic_overviews_basic(
    client: AsyncClient,
    sample_taxonomy: Taxonomy,
    sample_topics: list[Topic],
    sample_edges: list[TopicEdge],
) -> None:
    """Test basic listing of topic overviews for a taxonomy."""
    response = await client.get(f"/taxonomies/{sample_taxonomy.id}/topics")

    assert response.status_code == 200
    data = response.json()

    assert "items" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data

    assert data["total"] == 4
    assert len(data["items"]) == 4
    assert data["limit"] == 50
    assert data["offset"] == 0

    first_item = data["items"][0]
    assert "topic" in first_item
    assert "child_count" in first_item
    assert "children" in first_item
    assert "parents" in first_item


async def test_list_taxonomy_topic_overviews_pagination(
    client: AsyncClient,
    sample_taxonomy: Taxonomy,
    sample_topics: list[Topic],
) -> None:
    """Test pagination of topic overviews."""
    response = await client.get(
        f"/taxonomies/{sample_taxonomy.id}/topics",
        params={"limit": 2, "offset": 0},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 4
    assert len(data["items"]) == 2
    assert data["limit"] == 2
    assert data["offset"] == 0

    response2 = await client.get(
        f"/taxonomies/{sample_taxonomy.id}/topics",
        params={"limit": 2, "offset": 2},
    )

    assert response2.status_code == 200
    data2 = response2.json()

    assert data2["total"] == 4
    assert len(data2["items"]) == 2
    assert data2["offset"] == 2


async def test_list_taxonomy_topic_overviews_status_filter(
    client: AsyncClient,
    sample_taxonomy: Taxonomy,
    sample_topics: list[Topic],
) -> None:
    """Test filtering topic overviews by status."""
    response = await client.get(
        f"/taxonomies/{sample_taxonomy.id}/topics",
        params={"status": "active"},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 2
    assert len(data["items"]) == 2

    for item in data["items"]:
        assert item["topic"]["status"] == "active"

    response_draft = await client.get(
        f"/taxonomies/{sample_taxonomy.id}/topics",
        params={"status": "draft"},
    )

    assert response_draft.status_code == 200
    draft_data = response_draft.json()
    assert draft_data["total"] == 1


async def test_list_taxonomy_topic_overviews_search(
    client: AsyncClient,
    sample_taxonomy: Taxonomy,
    sample_topics: list[Topic],
) -> None:
    """Test full-text search of topic overviews."""
    response = await client.get(
        f"/taxonomies/{sample_taxonomy.id}/topics",
        params={"search": "searchable"},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert "searchable" in data["items"][0]["topic"]["description"].lower()

    response_title = await client.get(
        f"/taxonomies/{sample_taxonomy.id}/topics",
        params={"search": "Search Test"},
    )

    assert response_title.status_code == 200
    title_data = response_title.json()
    assert title_data["total"] == 1


async def test_list_taxonomy_topic_overviews_sort_by_title_asc(
    client: AsyncClient,
    sample_taxonomy: Taxonomy,
    sample_topics: list[Topic],
) -> None:
    """Test sorting topic overviews by title ascending."""
    response = await client.get(
        f"/taxonomies/{sample_taxonomy.id}/topics",
        params={"sort_by": "title", "sort_order": "asc"},
    )

    assert response.status_code == 200
    data = response.json()

    titles = [item["topic"]["title"] for item in data["items"]]
    assert titles == sorted(titles)


async def test_list_taxonomy_topic_overviews_sort_by_title_desc(
    client: AsyncClient,
    sample_taxonomy: Taxonomy,
    sample_topics: list[Topic],
) -> None:
    """Test sorting topic overviews by title descending."""
    response = await client.get(
        f"/taxonomies/{sample_taxonomy.id}/topics",
        params={"sort_by": "title", "sort_order": "desc"},
    )

    assert response.status_code == 200
    data = response.json()

    titles = [item["topic"]["title"] for item in data["items"]]
    assert titles == sorted(titles, reverse=True)


async def test_list_taxonomy_topic_overviews_sort_by_status(
    client: AsyncClient,
    sample_taxonomy: Taxonomy,
    sample_topics: list[Topic],
) -> None:
    """Test sorting topic overviews by status."""
    response = await client.get(
        f"/taxonomies/{sample_taxonomy.id}/topics",
        params={"sort_by": "status", "sort_order": "asc"},
    )

    assert response.status_code == 200
    data = response.json()

    statuses = [item["topic"]["status"] for item in data["items"]]
    assert statuses == sorted(statuses)


async def test_list_taxonomy_topic_overviews_sort_by_child_count(
    client: AsyncClient,
    sample_taxonomy: Taxonomy,
    sample_topics: list[Topic],
    sample_edges: list[TopicEdge],
) -> None:
    """Test sorting topic overviews by child count."""
    response = await client.get(
        f"/taxonomies/{sample_taxonomy.id}/topics",
        params={"sort_by": "child_count", "sort_order": "desc"},
    )

    assert response.status_code == 200
    data = response.json()

    child_counts = [item["child_count"] for item in data["items"]]
    assert child_counts == sorted(child_counts, reverse=True)


async def test_list_taxonomy_topic_overviews_relationship_data(
    client: AsyncClient,
    sample_taxonomy: Taxonomy,
    sample_topics: list[Topic],
    sample_edges: list[TopicEdge],
) -> None:
    """Test that topic overviews include correct parent/child relationship data."""
    response = await client.get(f"/taxonomies/{sample_taxonomy.id}/topics")

    assert response.status_code == 200
    data = response.json()

    topics_by_id = {item["topic"]["id"]: item for item in data["items"]}

    active_topic = topics_by_id["test:topic:1"]
    assert active_topic["child_count"] == 2
    assert len(active_topic["children"]) == 2
    assert len(active_topic["parents"]) == 0

    child_ids = {child["id"] for child in active_topic["children"]}
    assert "test:topic:2" in child_ids
    assert "test:topic:3" in child_ids

    draft_topic = topics_by_id["test:topic:2"]
    assert draft_topic["child_count"] == 1
    assert len(draft_topic["parents"]) == 1
    assert draft_topic["parents"][0]["id"] == "test:topic:1"


async def test_list_taxonomy_topic_overviews_invalid_limit(
    client: AsyncClient,
    sample_taxonomy: Taxonomy,
) -> None:
    """Test that invalid limit values are rejected."""
    response = await client.get(
        f"/taxonomies/{sample_taxonomy.id}/topics",
        params={"limit": 0},
    )
    assert response.status_code == 422

    response = await client.get(
        f"/taxonomies/{sample_taxonomy.id}/topics",
        params={"limit": 101},
    )
    assert response.status_code == 422


async def test_list_taxonomy_topic_overviews_invalid_offset(
    client: AsyncClient,
    sample_taxonomy: Taxonomy,
) -> None:
    """Test that negative offset values are rejected."""
    response = await client.get(
        f"/taxonomies/{sample_taxonomy.id}/topics",
        params={"offset": -1},
    )
    assert response.status_code == 422


async def test_list_taxonomy_topic_overviews_invalid_sort_by(
    client: AsyncClient,
    sample_taxonomy: Taxonomy,
) -> None:
    """Test that invalid sort_by values are rejected."""
    response = await client.get(
        f"/taxonomies/{sample_taxonomy.id}/topics",
        params={"sort_by": "invalid_field"},
    )
    assert response.status_code == 422


async def test_list_taxonomy_topic_overviews_invalid_sort_order(
    client: AsyncClient,
    sample_taxonomy: Taxonomy,
) -> None:
    """Test that invalid sort_order values are rejected."""
    response = await client.get(
        f"/taxonomies/{sample_taxonomy.id}/topics",
        params={"sort_order": "invalid"},
    )
    assert response.status_code == 422


async def test_get_topic_overview_basic(
    client: AsyncClient,
    sample_topics: list[Topic],
    sample_edges: list[TopicEdge],
) -> None:
    """Test fetching a single topic overview."""
    topic_id = sample_topics[0].id
    response = await client.get(f"/topics/{topic_id}/overview")

    assert response.status_code == 200
    data = response.json()

    assert "topic" in data
    assert "child_count" in data
    assert "children" in data
    assert "parents" in data

    assert data["topic"]["id"] == topic_id
    assert data["topic"]["title"] == "Active Topic"
    assert data["child_count"] == 2
    assert len(data["children"]) == 2
    assert len(data["parents"]) == 0


async def test_get_topic_overview_with_relationships(
    client: AsyncClient,
    sample_topics: list[Topic],
    sample_edges: list[TopicEdge],
) -> None:
    """Test that topic overview includes correct parent and child data."""
    topic_id = sample_topics[1].id
    response = await client.get(f"/topics/{topic_id}/overview")

    assert response.status_code == 200
    data = response.json()

    assert data["topic"]["id"] == topic_id
    assert data["child_count"] == 1
    assert len(data["children"]) == 1
    assert len(data["parents"]) == 1

    assert data["children"][0]["id"] == "test:topic:4"
    assert data["parents"][0]["id"] == "test:topic:1"

    for child in data["children"]:
        assert "id" in child
        assert "title" in child
        assert "status" in child

    for parent in data["parents"]:
        assert "id" in parent
        assert "title" in parent
        assert "status" in parent


async def test_get_topic_overview_no_relationships(
    client: AsyncClient,
    db_session: AsyncSession,
    sample_taxonomy: Taxonomy,
) -> None:
    """Test fetching a topic overview for a topic with no relationships."""
    topic = Topic(
        id="test:topic:orphan",
        taxonomy_id=sample_taxonomy.id,
        title="Orphan Topic",
        slug="orphan-topic",
        status="active",
    )
    db_session.add(topic)
    await db_session.commit()
    await db_session.refresh(topic)

    response = await client.get(f"/topics/{topic.id}/overview")

    assert response.status_code == 200
    data = response.json()

    assert data["topic"]["id"] == topic.id
    assert data["child_count"] == 0
    assert len(data["children"]) == 0
    assert len(data["parents"]) == 0


async def test_get_topic_overview_not_found(
    client: AsyncClient,
) -> None:
    """Test fetching a topic overview for a non-existent topic."""
    response = await client.get("/topics/nonexistent:topic/overview")

    assert response.status_code == 404


async def test_list_taxonomy_topic_overviews_empty_taxonomy(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test listing topic overviews for an empty taxonomy."""
    taxonomy = Taxonomy(
        id="test:empty-taxonomy",
        title="Empty Taxonomy",
    )
    db_session.add(taxonomy)
    await db_session.commit()

    response = await client.get(f"/taxonomies/{taxonomy.id}/topics")

    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 0
    assert len(data["items"]) == 0


async def test_list_taxonomy_topic_overviews_combined_filters(
    client: AsyncClient,
    sample_taxonomy: Taxonomy,
    sample_topics: list[Topic],
) -> None:
    """Test combining multiple filters (status + search)."""
    response = await client.get(
        f"/taxonomies/{sample_taxonomy.id}/topics",
        params={"status": "active", "search": "Topic"},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 2
    for item in data["items"]:
        assert item["topic"]["status"] == "active"
        assert "Topic" in item["topic"]["title"]


async def test_topic_overview_response_schema(
    client: AsyncClient,
    sample_topics: list[Topic],
    sample_edges: list[TopicEdge],
) -> None:
    """Test that topic overview response matches expected schema."""
    topic_id = sample_topics[0].id
    response = await client.get(f"/topics/{topic_id}/overview")

    assert response.status_code == 200
    data = response.json()

    assert isinstance(data["topic"]["id"], str)
    assert isinstance(data["topic"]["taxonomy_id"], str)
    assert isinstance(data["topic"]["title"], str)
    assert isinstance(data["topic"]["slug"], str)
    assert isinstance(data["topic"]["status"], str)
    assert isinstance(data["topic"]["created_at"], str)
    assert isinstance(data["topic"]["updated_at"], str)

    assert isinstance(data["child_count"], int)
    assert isinstance(data["children"], list)
    assert isinstance(data["parents"], list)

    datetime.fromisoformat(data["topic"]["created_at"].replace("Z", "+00:00"))
    datetime.fromisoformat(data["topic"]["updated_at"].replace("Z", "+00:00"))


async def test_hierarchical_root_topic_children(
    client: AsyncClient,
    hierarchical_topics: dict[str, Topic],
) -> None:
    """Test that root topic has correct child count and children."""
    root = hierarchical_topics["root"]
    response = await client.get(f"/topics/{root.id}/overview")

    assert response.status_code == 200
    data = response.json()

    assert data["child_count"] == 3
    assert len(data["children"]) == 3
    assert len(data["parents"]) == 0

    child_titles = {child["title"] for child in data["children"]}
    assert child_titles == {"Programming", "Databases", "DevOps"}


async def test_hierarchical_mid_level_topic(
    client: AsyncClient,
    hierarchical_topics: dict[str, Topic],
) -> None:
    """Test mid-level topic has both parents and children."""
    programming = hierarchical_topics["programming"]
    response = await client.get(f"/topics/{programming.id}/overview")

    assert response.status_code == 200
    data = response.json()

    assert data["child_count"] == 2
    assert len(data["children"]) == 2
    assert len(data["parents"]) == 1

    assert data["parents"][0]["title"] == "Root"

    child_titles = {child["title"] for child in data["children"]}
    assert child_titles == {"Python", "JavaScript"}


async def test_hierarchical_leaf_topic(
    client: AsyncClient,
    hierarchical_topics: dict[str, Topic],
) -> None:
    """Test leaf topics have no children but have parents."""
    react = hierarchical_topics["react"]
    response = await client.get(f"/topics/{react.id}/overview")

    assert response.status_code == 200
    data = response.json()

    assert data["child_count"] == 0
    assert len(data["children"]) == 0
    assert len(data["parents"]) == 1

    assert data["parents"][0]["title"] == "JavaScript"


async def test_hierarchical_topic_with_multiple_parents(
    client: AsyncClient,
    hierarchical_topics: dict[str, Topic],
) -> None:
    """Test topic with multiple parent relationships (broader + related)."""
    postgresql = hierarchical_topics["postgresql"]
    response = await client.get(f"/topics/{postgresql.id}/overview")

    assert response.status_code == 200
    data = response.json()

    assert len(data["parents"]) == 3

    parent_titles = {parent["title"] for parent in data["parents"]}
    assert "SQL" in parent_titles
    assert "Django" in parent_titles
    assert "FastAPI" in parent_titles


async def test_hierarchical_list_with_child_count_sort(
    client: AsyncClient,
    sample_taxonomy: Taxonomy,
    hierarchical_topics: dict[str, Topic],
) -> None:
    """Test listing hierarchical topics sorted by child count."""
    response = await client.get(
        f"/taxonomies/{sample_taxonomy.id}/topics",
        params={"sort_by": "child_count", "sort_order": "desc", "limit": 100},
    )

    assert response.status_code == 200
    data = response.json()

    topics_by_id = {
        item["topic"]["id"]: item for item in data["items"]
    }

    root_item = topics_by_id[hierarchical_topics["root"].id]
    assert root_item["child_count"] == 3

    programming_item = topics_by_id[hierarchical_topics["programming"].id]
    assert programming_item["child_count"] == 2

    python_item = topics_by_id[hierarchical_topics["python"].id]
    assert python_item["child_count"] == 2

    react_item = topics_by_id[hierarchical_topics["react"].id]
    assert react_item["child_count"] == 0

    child_counts = [item["child_count"] for item in data["items"]]
    assert child_counts == sorted(child_counts, reverse=True)


async def test_hierarchical_search_across_levels(
    client: AsyncClient,
    sample_taxonomy: Taxonomy,
    hierarchical_topics: dict[str, Topic],
) -> None:
    """Test searching for topics across different hierarchy levels."""
    response = await client.get(
        f"/taxonomies/{sample_taxonomy.id}/topics",
        params={"search": "database"},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["total"] >= 5

    titles = {item["topic"]["title"] for item in data["items"]}
    assert "Databases" in titles
    assert "SQL" in titles or "PostgreSQL" in titles or "MySQL" in titles


async def test_hierarchical_pagination_consistency(
    client: AsyncClient,
    sample_taxonomy: Taxonomy,
    hierarchical_topics: dict[str, Topic],
) -> None:
    """Test that pagination maintains relationship data correctly."""
    response_page1 = await client.get(
        f"/taxonomies/{sample_taxonomy.id}/topics",
        params={"limit": 5, "offset": 0},
    )

    assert response_page1.status_code == 200
    page1_data = response_page1.json()
    assert len(page1_data["items"]) == 5

    for item in page1_data["items"]:
        assert "child_count" in item
        assert "children" in item
        assert "parents" in item
        assert item["child_count"] == len(item["children"])


async def test_hierarchical_deep_nesting(
    client: AsyncClient,
    hierarchical_topics: dict[str, Topic],
) -> None:
    """Test deeply nested topic (4 levels deep)."""
    fastapi = hierarchical_topics["fastapi"]
    response = await client.get(f"/topics/{fastapi.id}/overview")

    assert response.status_code == 200
    data = response.json()

    assert data["topic"]["title"] == "FastAPI"
    assert len(data["parents"]) == 1
    assert data["parents"][0]["title"] == "Python"


async def test_hierarchical_multiple_children_same_parent(
    client: AsyncClient,
    hierarchical_topics: dict[str, Topic],
) -> None:
    """Test parent with multiple children returns all children."""
    python = hierarchical_topics["python"]
    response = await client.get(f"/topics/{python.id}/overview")

    assert response.status_code == 200
    data = response.json()

    assert data["child_count"] == 2
    child_titles = {child["title"] for child in data["children"]}
    assert child_titles == {"Django", "FastAPI"}

    for child in data["children"]:
        assert "id" in child
        assert "title" in child
        assert "status" in child
        assert child["status"] == "active"


async def test_hierarchical_sibling_topics(
    client: AsyncClient,
    hierarchical_topics: dict[str, Topic],
) -> None:
    """Test sibling topics (same parent) are distinct."""
    react = hierarchical_topics["react"]
    vue = hierarchical_topics["vue"]

    react_response = await client.get(f"/topics/{react.id}/overview")
    vue_response = await client.get(f"/topics/{vue.id}/overview")

    assert react_response.status_code == 200
    assert vue_response.status_code == 200

    react_data = react_response.json()
    vue_data = vue_response.json()

    assert react_data["parents"][0]["title"] == "JavaScript"
    assert vue_data["parents"][0]["title"] == "JavaScript"

    assert react_data["topic"]["id"] != vue_data["topic"]["id"]


async def test_hierarchical_relationship_types(
    client: AsyncClient,
    hierarchical_topics: dict[str, Topic],
) -> None:
    """Test that topics can have both broader and related relationships."""
    postgresql = hierarchical_topics["postgresql"]
    response = await client.get(f"/topics/{postgresql.id}/overview")

    assert response.status_code == 200
    data = response.json()

    assert len(data["parents"]) == 3

    parent_ids = {parent["id"] for parent in data["parents"]}
    assert hierarchical_topics["sql"].id in parent_ids
    assert hierarchical_topics["django"].id in parent_ids
    assert hierarchical_topics["fastapi"].id in parent_ids


async def test_hierarchical_branch_isolation(
    client: AsyncClient,
    sample_taxonomy: Taxonomy,
    hierarchical_topics: dict[str, Topic],
) -> None:
    """Test that different branches of hierarchy are properly isolated."""
    response = await client.get(
        f"/taxonomies/{sample_taxonomy.id}/topics",
        params={"search": "Docker", "limit": 100},
    )

    assert response.status_code == 200
    data = response.json()

    topic_ids = {item["topic"]["id"] for item in data["items"]}

    assert hierarchical_topics["docker"].id in topic_ids

    programming_topics = {
        hierarchical_topics["python"].id,
        hierarchical_topics["javascript"].id,
        hierarchical_topics["django"].id,
    }
    assert not topic_ids.intersection(programming_topics)
