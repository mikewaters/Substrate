"""Tests for TopicService.

This module tests the service layer for topics, including CRUD operations,
search, and discovery features.
"""

import pytest

from ontologizer.schema.taxonomy import TaxonomyCreate

pytestmark = pytest.mark.asyncio

from ontologizer.relational.models import Taxonomy
from ontologizer.relational.models import Topic as TopicORM
from ontologizer.schema import (
    TopicCreate,
    TopicEdgeCreate,
    TopicSearchRequest,
    TopicUpdate,
)
from ontologizer.relational.services import TopicQueryService, TopicTaxonomyService

# class TestTopicServiceHierarchy:
#     """Tests for hierarchy methods"""

#     async def test_get_tree(
#         self, topic_service: TopicTaxonomyService, sample_taxonomy_domain: Taxonomy
#     ) -> None:


class TestTopicServiceCreate:
    """Tests for creating topics via service."""

    async def test_add_topic_with_all_fields(
        self, topic_service: TopicTaxonomyService, sample_taxonomy_domain: Taxonomy
    ) -> None:
        """Test creating a topic with all fields."""
        schema = TopicCreate(
            taxonomy_id=sample_taxonomy_domain.id,
            title="Test Topic",
            slug="test-topic",
            description="A test topic",
            status="draft",
            aliases=["alias1", "alias2"],
            external_refs={"key": "value"},
        )

        response = await topic_service.create(schema)
        # breakpoint()
        assert isinstance(response, TopicORM)

        assert response.title == "Test Topic"
        assert response.slug == "test-topic"
        assert response.description == "A test topic"
        assert response.status == "draft"
        assert response.aliases == ["alias1", "alias2"]
        assert response.external_refs == {"key": "value"}
        assert response.id is not None

    async def test_add_topic_auto_slug(
        self, topic_service: TopicTaxonomyService, sample_taxonomy_domain: Taxonomy
    ) -> None:
        """Test creating a topic with auto-generated slug."""
        schema = TopicCreate(
            taxonomy_id=sample_taxonomy_domain.id, title="Auto Slug Topic"
        )

        response = await topic_service.create(schema)

        assert response.title == "Auto Slug Topic"
        assert response.slug == "auto-slug-topic"


class TestTopicServiceRead:
    """Tests for reading topics via service."""

    async def test_get_topic_by_id(
        self, topic_service: TopicTaxonomyService, sample_taxonomy_domain: Taxonomy
    ) -> None:
        """Test getting a topic by ID."""
        # Create
        schema = TopicCreate(taxonomy_id=sample_taxonomy_domain.id, title="Test Topic")
        created = await topic_service.create(schema)
        # Get
        retrieved = await topic_service.get(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.title == created.title


class TestTopicServiceUpdate:
    """Tests for updating topics via service."""

    async def test_update_topic_title(
        self, topic_service: TopicTaxonomyService, sample_taxonomy_domain: Taxonomy
    ) -> None:
        """Test updating a topic's title."""
        # Create
        schema = TopicCreate(
            taxonomy_id=sample_taxonomy_domain.id, title="Original Title"
        )
        created = await topic_service.create(schema)

        # Update
        update_schema = TopicUpdate(title="Updated Title")  # , slug="updated-title")
        updated = await topic_service.update(update_schema, created.id)

        assert updated is not None
        assert updated.title == "Updated Title"
        assert updated.id == created.id

    async def test_deprecate_topic(
        self, topic_service: TopicTaxonomyService, sample_taxonomy_domain: Taxonomy
    ) -> None:
        """Test deprecating a topic."""
        # Create
        schema = TopicCreate(
            taxonomy_id=sample_taxonomy_domain.id, title="Test Topic", status="active"
        )
        created = await topic_service.create(schema)

        # Deprecate
        deprecated = await topic_service.update({"status": "deprecated"}, created.id)

        assert deprecated is not None
        assert deprecated.status == "deprecated"


class TestTopicServiceSearch:
    """Tests for topic search features."""

    async def test_search_topics_by_title(
        self,
        topic_service: TopicTaxonomyService,
        query_service: TopicQueryService,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        """Test searching topics by title."""
        # Create topics
        await topic_service.create(
            TopicCreate(
                taxonomy_id=sample_taxonomy_domain.id, title="Python Programming"
            )
        )
        await topic_service.create(
            TopicCreate(
                taxonomy_id=sample_taxonomy_domain.id, title="JavaScript Programming"
            )
        )
        await topic_service.create(
            TopicCreate(taxonomy_id=sample_taxonomy_domain.id, title="Data Science")
        )

        # Search for "Programming"
        request = TopicSearchRequest(query="Programming")
        response = await query_service.search_topics(request)

        assert response.total == 2
        assert len(response.items) == 2
        titles = {item.title for item in response.items}
        assert "Python Programming" in titles
        assert "JavaScript Programming" in titles

    async def test_search_topics_case_insensitive(
        self,
        topic_service: TopicTaxonomyService,
        query_service: TopicQueryService,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        """Test case-insensitive search."""
        # Create topic
        await topic_service.create(
            TopicCreate(
                taxonomy_id=sample_taxonomy_domain.id, title="Python Programming"
            )
        )

        # Search with different case
        request = TopicSearchRequest(query="python")
        response = await query_service.search_topics(request)

        assert response.total == 1
        assert response.items[0].title == "Python Programming"


class TestTopicServiceMaterializedPath:
    """Tests for materialized path behaviour via the service layer."""

    async def test_create_edge_marks_primary(
        self, topic_service: TopicTaxonomyService, sample_taxonomy_domain: Taxonomy
    ) -> None:
        parent = await topic_service.create(
            TopicCreate(taxonomy_id=sample_taxonomy_domain.id, title="Parent")
        )
        child = await topic_service.create(
            TopicCreate(taxonomy_id=sample_taxonomy_domain.id, title="Child")
        )

        edge_response = await topic_service.create_edge(
            TopicEdgeCreate(
                parent_id=parent.id,
                child_id=child.id,
                role="broader",
                is_primary=True,
            )
        )

        assert edge_response.is_primary is True

        updated_child = await topic_service.get(child.id)
        assert updated_child is not None
        assert updated_child.path == f"/{parent.slug}/{child.slug}"

    async def test_search_topics_with_taxonomy_filter(
        self,
        topic_service: TopicTaxonomyService,
        query_service: TopicQueryService,
        taxonomy_service,
    ) -> None:
        """Test searching topics with taxonomy filter."""
        # from ontology.schema import TaxonomyCreate

        # Create two taxonomies
        tax1 = await taxonomy_service.create(TaxonomyCreate(title="Taxonomy 1"))
        tax2 = await taxonomy_service.create(TaxonomyCreate(title="Taxonomy 2"))

        # Create topics in different taxonomies
        await topic_service.create(
            TopicCreate(taxonomy_id=tax1.id, title="Python Programming")
        )
        await topic_service.create(
            TopicCreate(taxonomy_id=tax2.id, title="Python Data Science")
        )

        # Search with taxonomy filter
        request = TopicSearchRequest(query="Python", taxonomy_id=tax1.id)
        response = await query_service.search_topics(request)

        assert response.total == 1
        assert response.items[0].taxonomy_id == tax1.id


class TestTopicServiceDiscovery:
    """Tests for topic discovery features."""

    async def test_find_orphan_topics(
        self,
        topic_service: TopicTaxonomyService,
        query_service: TopicQueryService,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        """Test finding orphan topics (no parents)."""
        # Create topics
        parent = await topic_service.create(
            TopicCreate(taxonomy_id=sample_taxonomy_domain.id, title="Parent Topic")
        )
        child = await topic_service.create(
            TopicCreate(taxonomy_id=sample_taxonomy_domain.id, title="Child Topic")
        )
        orphan = await topic_service.create(
            TopicCreate(taxonomy_id=sample_taxonomy_domain.id, title="Orphan Topic")
        )

        # Create edge (parent -> child)
        await topic_service.create_edge(
            TopicEdgeCreate(parent_id=parent.id, child_id=child.id)
        )

        # Find orphans
        orphans = await query_service.find_orphan_topics(sample_taxonomy_domain.id)

        # Parent and orphan should be orphans (no incoming edges)
        orphan_ids = {t.id for t in orphans}
        assert parent.id in orphan_ids
        assert orphan.id in orphan_ids
        assert child.id not in orphan_ids  # Child has a parent

    async def test_find_multi_parent_topics(
        self,
        topic_service: TopicTaxonomyService,
        query_service: TopicQueryService,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        """Test finding topics with multiple parents."""
        # Create topics
        parent1 = await topic_service.create(
            TopicCreate(taxonomy_id=sample_taxonomy_domain.id, title="Parent 1")
        )
        parent2 = await topic_service.create(
            TopicCreate(taxonomy_id=sample_taxonomy_domain.id, title="Parent 2")
        )
        child = await topic_service.create(
            TopicCreate(
                taxonomy_id=sample_taxonomy_domain.id, title="Multi-Parent Child"
            )
        )

        # Create edges (two parents -> one child)
        await topic_service.create_edge(
            TopicEdgeCreate(parent_id=parent1.id, child_id=child.id)
        )
        await topic_service.create_edge(
            TopicEdgeCreate(parent_id=parent2.id, child_id=child.id)
        )

        # Find multi-parent topics
        multi_parents = await query_service.find_multi_parent_topics(
            min_parents=2, taxonomy_id=sample_taxonomy_domain.id
        )

        assert len(multi_parents) == 1
        assert multi_parents[0].id == child.id


class TestTopicServiceEdgeOperations:
    """Tests for edge operations via service."""

    async def test_create_edge(
        self, topic_service: TopicTaxonomyService, sample_taxonomy_domain: Taxonomy
    ) -> None:
        """Test creating a topic edge."""
        # Create topics
        parent = await topic_service.create(
            TopicCreate(taxonomy_id=sample_taxonomy_domain.id, title="Parent")
        )
        child = await topic_service.create(
            TopicCreate(taxonomy_id=sample_taxonomy_domain.id, title="Child")
        )

        # Create edge
        edge_schema = TopicEdgeCreate(
            parent_id=parent.id, child_id=child.id, role="broader", confidence=0.9
        )
        edge = await topic_service.create_edge(edge_schema)

        assert edge.parent_id == parent.id
        assert edge.child_id == child.id
        assert edge.role == "broader"
        assert edge.confidence == 0.9

    async def test_create_edge_prevents_cycle(
        self, topic_service: TopicTaxonomyService, sample_taxonomy_domain: Taxonomy
    ) -> None:
        """Test that creating a cycle is prevented."""
        # Create topics
        topic_a = await topic_service.create(
            TopicCreate(taxonomy_id=sample_taxonomy_domain.id, title="Topic A")
        )
        topic_b = await topic_service.create(
            TopicCreate(taxonomy_id=sample_taxonomy_domain.id, title="Topic B")
        )

        # Create edge A -> B
        await topic_service.create_edge(
            TopicEdgeCreate(parent_id=topic_a.id, child_id=topic_b.id)
        )

        # Try to create edge B -> A (would create cycle)
        with pytest.raises(ValueError, match="would create cycle"):
            await topic_service.create_edge(
                TopicEdgeCreate(parent_id=topic_b.id, child_id=topic_a.id)
            )

    async def test_get_ancestors(
        self, topic_service: TopicTaxonomyService, sample_taxonomy_domain: Taxonomy
    ) -> None:
        """Test getting ancestors."""
        # Create hierarchy: A -> B -> C
        topic_a = await topic_service.create(
            TopicCreate(taxonomy_id=sample_taxonomy_domain.id, title="Topic A")
        )
        topic_b = await topic_service.create(
            TopicCreate(taxonomy_id=sample_taxonomy_domain.id, title="Topic B")
        )
        topic_c = await topic_service.create(
            TopicCreate(taxonomy_id=sample_taxonomy_domain.id, title="Topic C")
        )

        await topic_service.create_edge(
            TopicEdgeCreate(parent_id=topic_a.id, child_id=topic_b.id)
        )
        await topic_service.create_edge(
            TopicEdgeCreate(parent_id=topic_b.id, child_id=topic_c.id)
        )

        # Get ancestors of C
        ancestors = await topic_service.get_ancestors(topic_c.id)

        ancestor_ids = {t.id for t in ancestors}
        assert topic_a.id in ancestor_ids
        assert topic_b.id in ancestor_ids


class TestTopicServiceFiltering:
    """Tests for filtering topics."""

    async def test_list_topics_by_status(
        self, topic_service: TopicTaxonomyService, sample_taxonomy_domain: Taxonomy
    ) -> None:
        """Test filtering topics by status."""
        # Create topics with different statuses
        await topic_service.create(
            TopicCreate(
                taxonomy_id=sample_taxonomy_domain.id,
                title="Draft Topic",
                status="draft",
            )
        )
        await topic_service.create(
            TopicCreate(
                taxonomy_id=sample_taxonomy_domain.id,
                title="Active Topic",
                status="active",
            )
        )

        # Filter by status
        response = await topic_service.list(status="active")

        assert len(response) == 1
        assert response[0].status == "active"

    async def test_list_topics_by_taxonomy(
        self, topic_service: TopicTaxonomyService, taxonomy_service
    ) -> None:
        """Test filtering topics by taxonomy."""
        from ontologizer.schema.taxonomy import TaxonomyCreate

        # Create two taxonomies
        tax1 = await taxonomy_service.create(TaxonomyCreate(title="Taxonomy 1"))
        tax2 = await taxonomy_service.create(TaxonomyCreate(title="Taxonomy 2"))

        # Create topics in different taxonomies
        await topic_service.create(TopicCreate(taxonomy_id=tax1.id, title="Topic 1"))
        await topic_service.create(TopicCreate(taxonomy_id=tax2.id, title="Topic 2"))

        # Filter by taxonomy
        response = await topic_service.list(taxonomy_id=tax1.id)

        assert len(response) == 1
        assert response[0].taxonomy_id == tax1.id
