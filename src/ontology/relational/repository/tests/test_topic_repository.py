"""Tests for TopicRepository.

This module tests the TopicRepository, ensuring proper CRUD operations,
slug generation, search functionality, and database interactions.
"""

import pytest

pytestmark = pytest.mark.asyncio
from advanced_alchemy.exceptions import DuplicateKeyError, NotFoundError
from advanced_alchemy.filters import LimitOffset
from ontology.relational.models import Taxonomy
from ontology.relational.repository import TopicRepository, TopicEdgeRepository

from ontology.relational.models import (
    Topic as TopicORM,
    TopicEdge as TopicEdgeORM,
)


"""
Refactor:
    add --> add
    get_topic - get
    get topic by slug - get
    update topic - get and update | update
    deprecate topic - get and update | update
    delete topic - delete | delete where
    search topics- list
    list topics - list
    count topics by status - count
    count topics by taxonomy - count
    get topics for suggestions - list
    to_domain
    create edge - add
    delete edge - delete | delete where
    get ancestorsa - list
    get descendants - listy

"""


class TestTopicRepositoryCreate:
    """Tests for topic creation."""

    async def test_add_with_all_fields(
        self,
        topic_repo: TopicRepository,
        edge_repo: TopicEdgeRepository,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        """Test creating a topic with all fields."""
        create_data = TopicORM(
            taxonomy_id=sample_taxonomy_domain.id,
            title="Python Programming",
            slug="python-programming",
            description="The Python programming language",
            status="active",
            aliases=["Python", "Py"],
            external_refs={"wikidata": "Q28865"},
        )

        topic = await topic_repo.add(create_data)

        assert isinstance(topic, TopicORM)
        assert isinstance(topic.id, str)
        assert topic.taxonomy_id == sample_taxonomy_domain.id
        assert topic.title == "Python Programming"
        assert topic.slug == "python-programming"
        assert topic.description == "The Python programming language"
        assert topic.status == "active"
        assert topic.aliases == ["Python", "Py"]
        assert topic.external_refs == {"wikidata": "Q28865"}
        assert topic.path == "/python-programming"

    async def test_add_auto_generate_slug(
        self,
        topic_repo: TopicRepository,
        edge_repo: TopicEdgeRepository,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        """Test creating a topic with auto-generated slug."""
        create_data = TopicORM(
            taxonomy_id=sample_taxonomy_domain.id,
            title="Hello World Topic",
        )

        topic = await topic_repo.add(create_data)

        assert topic.slug == "hello-world-topic"
        assert topic.path == "/hello-world-topic"

    async def test_add_duplicate_slug_fails(
        self,
        topic_repo: TopicRepository,
        edge_repo: TopicEdgeRepository,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        """Test that creating a topic with duplicate slug fails."""
        # Create first topic
        await topic_repo.add(
            TopicORM(
                taxonomy_id=sample_taxonomy_domain.id,
                title="Topic 1",
                slug="duplicate-slug",
            )
        )

        # Try to create second topic with same slug in same taxonomy
        with pytest.raises(DuplicateKeyError, match="already exists"):
            await topic_repo.add(
                TopicORM(
                    taxonomy_id=sample_taxonomy_domain.id,
                    title="Topic 2",
                    slug="duplicate-slug",
                )
            )


class TestTopicRepositoryRead:
    """Tests for topic retrieval."""

    async def test_get_topic_by_id(
        self,
        topic_repo: TopicRepository,
        edge_repo: TopicEdgeRepository,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        """Test retrieving a topic by ID."""
        created = await topic_repo.add(
            TopicORM(
                taxonomy_id=sample_taxonomy_domain.id,
                title="Test Topic",
            )
        )

        topic = await topic_repo.get(created.id)

        assert topic is not None
        assert topic.id == created.id
        assert topic.title == "Test Topic"

    async def test_get_topic_not_found(
        self, topic_repo: TopicRepository, edge_repo: TopicEdgeRepository
    ) -> None:
        """Test retrieving a non-existent topic."""
        with pytest.raises(NotFoundError):
            topic = await topic_repo.get("tax:test")


class TestTopicRepositoryUpdate:
    """Tests for topic updates."""

    async def test_update_topic_title(
        self,
        topic_repo: TopicRepository,
        edge_repo: TopicEdgeRepository,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        """Test updating a topic title."""
        created = await topic_repo.add(
            TopicORM(
                taxonomy_id=sample_taxonomy_domain.id,
                title="Original Title",
                # slug='x'
            )
        )

        created.title = "Updated Title"
        topic = await topic_repo.update(created)

        assert topic is not None
        assert topic.title == "Updated Title"

    async def test_update_topic_multiple_fields(
        self,
        topic_repo: TopicRepository,
        edge_repo: TopicEdgeRepository,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        """Test updating multiple topic fields."""
        created = await topic_repo.add(
            TopicORM(
                taxonomy_id=sample_taxonomy_domain.id, title="Test Topic", slug="a"
            )
        )

        created.title = "New Title"
        created.description = "New description"
        created.aliases = ["Alias1", "Alias2"]
        topic = await topic_repo.update(created)

        assert topic is not None
        assert topic.title == "New Title"
        assert topic.description == "New description"
        assert topic.aliases == ["Alias1", "Alias2"]

    async def test_update_topic_slug_unique_check(
        self,
        topic_repo: TopicRepository,
        edge_repo: TopicEdgeRepository,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        """Test that updating slug validates uniqueness."""
        # Create two topics
        topic1 = await topic_repo.add(
            TopicORM(
                taxonomy_id=sample_taxonomy_domain.id,
                title="Topic 1",
                slug="topic-1",
            )
        )
        await topic_repo.add(
            TopicORM(
                taxonomy_id=sample_taxonomy_domain.id,
                title="Topic 2",
                slug="topic-2",
            )
        )

        # Try to update topic1's slug to topic2's slug
        topic1.slug = "topic-2"
        with pytest.raises(DuplicateKeyError, match="already exists"):
            await topic_repo.update(topic1)


# class TestTopicRepositoryDeprecate:
#     """Tests for topic deprecation."""

#     async def test_deprecate_topic(
#         self, topic_repo: TopicRepository, sample_taxonomy_domain: Taxonomy
#     ) -> None:
#         """Test deprecating a topic."""
#         created = await topic_repo.add(
#             TopicORM(
#                 taxonomy_id=sample_taxonomy_domain.id,
#                 title="Test Topic",
#                 status="active",
#             )
#         )

#         topic = topic_repo.deprecate_topic(created.id)

#         assert topic is not None
#         assert topic.status == "deprecated"


class TestTopicRepositoryDelete:
    """Tests for topic deletion."""

    async def test_delete_topic(
        self,
        topic_repo: TopicRepository,
        edge_repo: TopicEdgeRepository,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        """Test deleting a topic."""
        created = await topic_repo.add(
            TopicORM(
                taxonomy_id=sample_taxonomy_domain.id,
                title="Test Topic",
            )
        )
        await topic_repo.delete(created.id)
        # assert success is True

        # Verify it's gone
        with pytest.raises(NotFoundError):
            _ = await topic_repo.get(created.id)

    async def test_delete_topic_not_found(
        self, topic_repo: TopicRepository, edge_repo: TopicEdgeRepository
    ) -> None:
        """Test deleting a non-existent topic."""
        with pytest.raises(NotFoundError):
            _ = await topic_repo.delete("tax:test")


class TestTopicRepositoryList:
    """Tests for topic listing."""

    async def test_list_topics_all(
        self,
        topic_repo: TopicRepository,
        edge_repo: TopicEdgeRepository,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        """Test listing all topics."""
        # Create multiple topics
        for i in range(5):
            await topic_repo.add(
                TopicORM(
                    taxonomy_id=sample_taxonomy_domain.id,
                    title=f"Topic {i}",
                )
            )

        topics = await topic_repo.list()

        assert len(topics) == 5

    async def test_list_topics_by_taxonomy(
        self,
        topic_repo: TopicRepository,
        edge_repo: TopicEdgeRepository,
        taxonomy_repo,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        """Test listing topics filtered by taxonomy."""
        from ontology.relational.models import Taxonomy as TaxonomyORM

        # Create another taxonomy
        taxonomy2 = await taxonomy_repo.add(TaxonomyORM(title="Taxonomy 2"))

        # Create topics in different taxonomies
        for i in range(3):
            await topic_repo.add(
                TopicORM(
                    taxonomy_id=sample_taxonomy_domain.id,
                    title=f"Topic {i}",
                )
            )
        for i in range(2):
            await topic_repo.add(
                TopicORM(
                    taxonomy_id=taxonomy2.id,
                    title=f"Topic {i}",
                )
            )

        # List only topics in first taxonomy
        topics = await topic_repo.list(taxonomy_id=sample_taxonomy_domain.id)

        assert len(topics) == 3
        # assert count == 3
        assert all(t.taxonomy_id == sample_taxonomy_domain.id for t in topics)

    async def test_list_topics_by_status(
        self,
        topic_repo: TopicRepository,
        edge_repo: TopicEdgeRepository,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        """Test listing topics filtered by status."""
        # Create topics with different statuses
        await topic_repo.add(
            TopicORM(
                taxonomy_id=sample_taxonomy_domain.id,
                title="Draft Topic",
                status="draft",
            )
        )
        await topic_repo.add(
            TopicORM(
                taxonomy_id=sample_taxonomy_domain.id,
                title="Active Topic",
                status="active",
            )
        )

        # List only active topics
        topics = await topic_repo.list(status="active")

        assert len(topics) == 1
        assert topics[0].status == "active"

    async def test_list_topics_with_pagination(
        self,
        topic_repo: TopicRepository,
        edge_repo: TopicEdgeRepository,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        """Test listing topics with pagination."""
        # Create multiple topics
        for i in range(10):
            await topic_repo.add(
                TopicORM(
                    taxonomy_id=sample_taxonomy_domain.id,
                    title=f"Topic {i}",
                )
            )

        # Get first page
        topics_page1, count = await topic_repo.list_and_count(
            LimitOffset(limit=5, offset=0)
        )
        assert len(topics_page1) == 5
        assert count == 10
        # Get second page
        topics_page2, count = await topic_repo.list_and_count(
            LimitOffset(limit=5, offset=5)
        )
        assert len(topics_page2) == 5
        assert count == 10

        # Ensure no overlap
        page1_ids = {t.id for t in topics_page1}
        page2_ids = {t.id for t in topics_page2}
        assert len(page1_ids & page2_ids) == 0


class TestMaterializedPathMaintenance:
    """Tests for materialized path updates."""

    async def test_paths_update_with_primary_parent(
        self,
        topic_repo: TopicRepository,
        edge_repo: TopicEdgeRepository,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        parent = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Parent")
        )
        child = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Child")
        )
        grandchild = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Grandchild")
        )

        await edge_repo.add(
            TopicEdgeORM(parent_id=parent.id, child_id=child.id, role="broader")
        )
        await edge_repo.add(
            TopicEdgeORM(parent_id=child.id, child_id=grandchild.id, role="broader")
        )

        updated_child = await topic_repo.get(child.id)
        updated_grandchild = await topic_repo.get(grandchild.id)

        assert updated_child is not None
        assert updated_child.path == f"/{parent.slug}/{child.slug}"
        assert updated_grandchild is not None
        assert (
            updated_grandchild.path == f"/{parent.slug}/{child.slug}/{grandchild.slug}"
        )

    async def test_paths_switch_when_primary_changes(
        self,
        topic_repo: TopicRepository,
        edge_repo: TopicEdgeRepository,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        parent_a = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Parent A")
        )
        parent_b = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Parent B")
        )
        child = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Child")
        )

        await edge_repo.add(
            TopicEdgeORM(parent_id=parent_a.id, child_id=child.id, role="broader")
        )
        await edge_repo.add(
            TopicEdgeORM(
                parent_id=parent_b.id,
                child_id=child.id,
                role="broader",
                is_primary=True,
            )
        )

        updated_child = await topic_repo.get(child.id)
        assert updated_child is not None
        assert updated_child.path == f"/{parent_b.slug}/{child.slug}"

    async def test_paths_recalculate_when_primary_deleted(
        self,
        topic_repo: TopicRepository,
        edge_repo: TopicEdgeRepository,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        parent_a = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Parent A")
        )
        parent_b = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Parent B")
        )
        child = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Child")
        )

        await edge_repo.add(
            TopicEdgeORM(parent_id=parent_a.id, child_id=child.id, role="broader")
        )
        await edge_repo.add(
            TopicEdgeORM(parent_id=parent_b.id, child_id=child.id, role="broader")
        )

        await edge_repo.delete_edge(parent_a.id, child.id)

        updated_child = await topic_repo.get(child.id)
        assert updated_child is not None
        assert updated_child.path == f"/{parent_b.slug}/{child.slug}"

        await edge_repo.delete_edge(parent_b.id, child.id)
        updated_child = await topic_repo.get(child.id)
        assert updated_child is not None
        assert updated_child.path == f"/{child.slug}"

    async def test_paths_update_on_slug_change(
        self,
        topic_repo: TopicRepository,
        edge_repo: TopicEdgeRepository,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        parent = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Parent")
        )
        child = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Child")
        )
        descendant = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Descendant")
        )

        await edge_repo.add(
            TopicEdgeORM(parent_id=parent.id, child_id=child.id, role="broader")
        )
        await edge_repo.add(
            TopicEdgeORM(parent_id=child.id, child_id=descendant.id, role="broader")
        )

        child.slug = "child-updated"
        await topic_repo.update(child)

        updated_child = await topic_repo.get(child.id)
        updated_descendant = await topic_repo.get(descendant.id)

        assert updated_child is not None
        assert updated_child.path == f"/{parent.slug}/child-updated"
        assert updated_descendant is not None
        assert (
            updated_descendant.path == f"/{parent.slug}/child-updated/{descendant.slug}"
        )
