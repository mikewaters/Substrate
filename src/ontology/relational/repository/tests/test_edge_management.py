"""Tests for TopicEdgeRepository edge management and closure table.

This module tests edge creation, deletion, cycle detection, and hierarchy traversal.
"""

import pytest
from sqlalchemy import select

pytestmark = pytest.mark.asyncio
from ontology.relational.models import Taxonomy
from ontology.relational.models import (
    Topic as TopicORM,
    TopicEdge as TopicEdgeORM,
)  # TopicORM, TopicEdgeORM
from ontology.relational.repository import TopicRepository, TopicEdgeRepository


class TestEdgeCreation:
    """Tests for creating topic edges."""

    async def test_create_edge_basic(
        self,
        topic_repo: TopicRepository,
        edge_repo: TopicEdgeRepository,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        """Test creating a basic edge between two topics."""
        # Create two topics
        parent = await topic_repo.add(
            TopicORM(
                taxonomy_id=sample_taxonomy_domain.id,
                title="Parent Topic",
            )
        )
        child = await topic_repo.add(
            TopicORM(
                taxonomy_id=sample_taxonomy_domain.id,
                title="Child Topic",
            )
        )

        # Create edge
        edge = await edge_repo.add(
            TopicEdgeORM(
                parent_id=parent.id,
                child_id=child.id,
                role="broader",
                source="test",
                confidence=1.0,
            )
        )

        assert edge.parent_id == parent.id
        assert edge.child_id == child.id
        assert edge.role == "broader"
        assert edge.source == "test"
        assert edge.confidence == 1.0
        assert edge.is_primary is True

        updated_child = await topic_repo.get(child.id)
        assert updated_child is not None
        assert updated_child.path == f"/{parent.slug}/{child.slug}"

    async def test_create_edge_prevents_self_loop(
        self,
        topic_repo: TopicRepository,
        edge_repo: TopicEdgeRepository,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        """Test that creating a self-loop is prevented."""
        topic = await topic_repo.add(
            TopicORM(
                taxonomy_id=sample_taxonomy_domain.id,
                title="Topic",
            )
        )

        with pytest.raises(ValueError, match="Cannot create edge from topic to itself"):
            await edge_repo.add(
                TopicEdgeORM(
                    parent_id=topic.id,
                    child_id=topic.id,
                )
            )

    async def test_create_edge_with_nonexistent_topic(
        self, edge_repo: TopicEdgeRepository
    ) -> None:
        """Test that creating edge with nonexistent topic fails."""
        with pytest.raises(ValueError, match="Topic not found"):
            await edge_repo.add(
                TopicEdgeORM(
                    parent_id="tax:test",
                    child_id="tax:test",
                )
            )


class TestCycleDetection:
    """Tests for cycle detection."""

    async def test_create_edge_prevents_simple_cycle(
        self,
        topic_repo: TopicRepository,
        edge_repo: TopicEdgeRepository,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        """Test that creating a simple cycle (A->B->A) is prevented."""
        # Create topics
        topic_a = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Topic A")
        )
        topic_b = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Topic B")
        )

        # Create edge A -> B
        await edge_repo.add(TopicEdgeORM(parent_id=topic_a.id, child_id=topic_b.id))

        # Try to create edge B -> A (would create cycle)
        with pytest.raises(ValueError, match="would create cycle"):
            await edge_repo.add(TopicEdgeORM(parent_id=topic_b.id, child_id=topic_a.id))

    async def test_create_edge_prevents_complex_cycle(
        self,
        topic_repo: TopicRepository,
        edge_repo: TopicEdgeRepository,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        """Test that creating a complex cycle (A->B->C->A) is prevented."""
        # Create topics
        topic_a = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Topic A")
        )
        topic_b = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Topic B")
        )
        topic_c = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Topic C")
        )

        # Create edges A -> B -> C
        await edge_repo.add(TopicEdgeORM(parent_id=topic_a.id, child_id=topic_b.id))
        await edge_repo.add(TopicEdgeORM(parent_id=topic_b.id, child_id=topic_c.id))

        # Try to create edge C -> A (would create cycle)
        with pytest.raises(ValueError, match="would create cycle"):
            await edge_repo.add(TopicEdgeORM(parent_id=topic_c.id, child_id=topic_a.id))

    async def test_create_edge_allows_diamond(
        self,
        topic_repo: TopicRepository,
        edge_repo: TopicEdgeRepository,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        """Test that creating a diamond structure is allowed.

        Diamond: A -> B -> D
                 A -> C -> D
        This is NOT a cycle.
        """
        # Create topics
        topic_a = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Topic A")
        )
        topic_b = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Topic B")
        )
        topic_c = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Topic C")
        )
        topic_d = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Topic D")
        )

        # Create diamond structure
        await edge_repo.add(TopicEdgeORM(parent_id=topic_a.id, child_id=topic_b.id))
        await edge_repo.add(TopicEdgeORM(parent_id=topic_a.id, child_id=topic_c.id))
        await edge_repo.add(TopicEdgeORM(parent_id=topic_b.id, child_id=topic_d.id))
        # This should succeed (not a cycle)
        await edge_repo.add(TopicEdgeORM(parent_id=topic_c.id, child_id=topic_d.id))


class TestEdgeDeletion:
    """Tests for deleting edges."""

    async def test_delete_edge(
        self,
        topic_repo: TopicRepository,
        edge_repo: TopicEdgeRepository,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        """Test deleting an edge."""
        # Create topics and edge
        parent = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Parent")
        )
        child = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Child")
        )
        await edge_repo.add(TopicEdgeORM(parent_id=parent.id, child_id=child.id))

        # Delete edge
        success = await edge_repo.delete_edge(parent.id, child.id)
        assert success is True

    async def test_delete_nonexistent_edge(
        self,
        topic_repo: TopicRepository,
        edge_repo: TopicEdgeRepository,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        """Test deleting a nonexistent edge returns False."""
        topic_a = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Topic A")
        )
        topic_b = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Topic B")
        )

        success = await edge_repo.delete_edge(topic_a.id, topic_b.id)
        assert success is False


@pytest.mark.skip
class TestAncestorsDescendants:
    """Tests for querying ancestors and descendants."""

    async def test_get_ancestors_simple(
        self,
        topic_repo: TopicRepository,
        edge_repo: TopicEdgeRepository,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        """Test getting ancestors in a simple hierarchy."""
        # Create hierarchy: A -> B -> C
        topic_a = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Topic A")
        )
        topic_b = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Topic B")
        )
        topic_c = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Topic C")
        )

        await edge_repo.add(TopicEdgeORM(parent_id=topic_a.id, child_id=topic_b.id))
        await edge_repo.add(TopicEdgeORM(parent_id=topic_b.id, child_id=topic_c.id))

        # Get ancestors of C
        ancestors = await topic_repo.get_ancestors(topic_c.id)
        ancestor_ids = {t.id for t in ancestors}

        assert topic_b.id in ancestor_ids
        assert topic_a.id in ancestor_ids
        assert len(ancestors) == 2

    async def test_get_descendants_simple(
        self,
        topic_repo: TopicRepository,
        edge_repo: TopicEdgeRepository,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        """Test getting descendants in a simple hierarchy."""
        # Create hierarchy: A -> B -> C
        topic_a = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Topic A")
        )
        topic_b = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Topic B")
        )
        topic_c = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Topic C")
        )

        await edge_repo.add(TopicEdgeORM(parent_id=topic_a.id, child_id=topic_b.id))
        await edge_repo.add(TopicEdgeORM(parent_id=topic_b.id, child_id=topic_c.id))

        # Get descendants of A
        descendants = await topic_repo.get_descendants(topic_a.id)
        descendant_ids = {t.id for t in descendants}

        assert topic_b.id in descendant_ids
        assert topic_c.id in descendant_ids
        assert len(descendants) == 2

    async def test_get_ancestors_with_max_depth(
        self,
        topic_repo: TopicRepository,
        edge_repo: TopicEdgeRepository,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        """Test getting ancestors with max depth limit."""
        # Create hierarchy: A -> B -> C -> D
        topics = []
        for i in range(4):
            topic = await topic_repo.add(
                TopicORM(
                    taxonomy_id=sample_taxonomy_domain.id,
                    title=f"Topic {chr(65 + i)}",
                )
            )
            topics.append(topic)

        for i in range(3):
            await edge_repo.add(
                TopicEdgeORM(
                    parent_id=topics[i].id,
                    child_id=topics[i + 1].id,
                )
            )

        # Get ancestors of D with max_depth=1 (should only get C)
        ancestors = await topic_repo.get_ancestors(topics[3].id, max_depth=1)
        assert len(ancestors) == 1
        assert ancestors[0].id == topics[2].id

        # Get ancestors of D with max_depth=2 (should get C and B)
        ancestors = await topic_repo.get_ancestors(topics[3].id, max_depth=2)
        ancestor_ids = {t.id for t in ancestors}
        assert len(ancestors) == 2
        assert topics[2].id in ancestor_ids
        assert topics[1].id in ancestor_ids

    async def test_get_descendants_in_diamond(
        self,
        topic_repo: TopicRepository,
        edge_repo: TopicEdgeRepository,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        """Test getting descendants in a diamond structure."""
        # Create diamond: A -> B -> D
        #                 A -> C -> D
        topic_a = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Topic A")
        )
        topic_b = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Topic B")
        )
        topic_c = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Topic C")
        )
        topic_d = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Topic D")
        )

        await edge_repo.add(TopicEdgeORM(parent_id=topic_a.id, child_id=topic_b.id))
        await edge_repo.add(TopicEdgeORM(parent_id=topic_a.id, child_id=topic_c.id))
        await edge_repo.add(TopicEdgeORM(parent_id=topic_b.id, child_id=topic_d.id))
        await edge_repo.add(TopicEdgeORM(parent_id=topic_c.id, child_id=topic_d.id))

        # Get descendants of A
        descendants = await topic_repo.get_descendants(topic_a.id)
        descendant_ids = {t.id for t in descendants}

        # Should include B, C, and D (even though D appears twice in structure)
        assert topic_b.id in descendant_ids
        assert topic_c.id in descendant_ids
        assert topic_d.id in descendant_ids


class TestClosureTableMaintenance:
    """Integration tests for closure table maintenance."""

    async def test_closure_table_maintained_on_edge_creation(
        self,
        topic_repo: TopicRepository,
        edge_repo: TopicEdgeRepository,
        sample_taxonomy_domain: Taxonomy,
        db_session,
    ) -> None:
        """Test that closure table is properly maintained when creating edges."""
        from ontology.relational.models import TopicClosure

        # Create hierarchy: A -> B -> C
        topic_a = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Topic A")
        )
        topic_b = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Topic B")
        )
        topic_c = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Topic C")
        )

        # Create edge A -> B
        await edge_repo.add(TopicEdgeORM(parent_id=topic_a.id, child_id=topic_b.id))

        # Check closure table has self-loops and direct edge
        closures = await db_session.execute(select(TopicClosure))  # .all()
        closure_tuples = {
            (c[0].ancestor_id, c[0].descendant_id, c[0].depth) for c in closures.all()
        }

        # Should have self-loops for A and B, plus A->B
        assert (topic_a.id, topic_a.id, 0) in closure_tuples
        assert (topic_b.id, topic_b.id, 0) in closure_tuples
        assert (topic_a.id, topic_b.id, 1) in closure_tuples

        # Create edge B -> C
        await edge_repo.add(TopicEdgeORM(parent_id=topic_b.id, child_id=topic_c.id))

        # Check closure table now includes paths through C
        closures = await db_session.execute(select(TopicClosure))
        closure_tuples = {
            (c[0].ancestor_id, c[0].descendant_id, c[0].depth) for c in closures.all()
        }

        # Should have paths A->B->C
        assert (topic_c.id, topic_c.id, 0) in closure_tuples  # Self-loop for C
        assert (topic_b.id, topic_c.id, 1) in closure_tuples  # B -> C
        assert (topic_a.id, topic_c.id, 2) in closure_tuples  # A -> B -> C

    async def test_closure_table_cleaned_on_edge_deletion(
        self,
        topic_repo: TopicRepository,
        edge_repo: TopicEdgeRepository,
        sample_taxonomy_domain: Taxonomy,
        db_session,
    ) -> None:
        """Test that closure table is properly cleaned when deleting edges."""
        from ontology.relational.models import TopicClosure

        # Create hierarchy: A -> B -> C
        topic_a = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Topic A")
        )
        topic_b = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Topic B")
        )
        topic_c = await topic_repo.add(
            TopicORM(taxonomy_id=sample_taxonomy_domain.id, title="Topic C")
        )

        await edge_repo.add(TopicEdgeORM(parent_id=topic_a.id, child_id=topic_b.id))
        await edge_repo.add(TopicEdgeORM(parent_id=topic_b.id, child_id=topic_c.id))

        # Delete edge B -> C
        await edge_repo.delete_edge(topic_b.id, topic_c.id)

        # Check closure table no longer has paths through B -> C
        closures = await db_session.execute(select(TopicClosure))  # .all()

        closure_tuples = {
            (c[0].ancestor_id, c[0].descendant_id, c[0].depth) for c in closures.all()
        }

        # Should still have A -> B
        assert (topic_a.id, topic_b.id, 1) in closure_tuples

        # Should NOT have B -> C or A -> C
        assert (topic_b.id, topic_c.id, 1) not in closure_tuples
        assert (topic_a.id, topic_c.id, 2) not in closure_tuples
