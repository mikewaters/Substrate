"""Tests for SQLAlchemy database models.

This module tests the Topic and Taxonomy database models, verifying table creation,
constraints, and basic CRUD operations.
"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ontologizer.relational.models import Match
from ontologizer.relational.models.topic import Taxonomy, Topic, TopicClosure, TopicEdge


pytestmark = pytest.mark.asyncio


class TestTaxonomyModel:
    """Tests for Taxonomy model."""

    async def test_create_taxonomy(self, db_session: AsyncSession) -> None:
        """Test creating a taxonomy with all fields."""
        taxonomy = Taxonomy(
            title="Software Development",
            description="Topics related to software development",
            skos_uri="http://example.org/taxonomy/software",
        )
        db_session.add(taxonomy)
        await db_session.commit()

        assert taxonomy.id is not None
        assert isinstance(taxonomy.id, str)
        assert taxonomy.title == "Software Development"
        assert taxonomy.created_at is not None
        assert taxonomy.updated_at is not None

    async def test_taxonomy_defaults(self, db_session: AsyncSession) -> None:
        """Test taxonomy with default values."""
        taxonomy = Taxonomy(title="Test Taxonomy")
        db_session.add(taxonomy)
        await db_session.commit()

        assert taxonomy.description is None
        assert taxonomy.skos_uri is None

    async def test_taxonomy_title_required(self, db_session: AsyncSession) -> None:
        """Test that title is required."""
        taxonomy = Taxonomy()
        db_session.add(taxonomy)
        with pytest.raises(IntegrityError):
            await db_session.commit()


class TestTopicModel:
    """Tests for Topic model."""

    async def test_create_topic(
        self, db_session: AsyncSession, sample_taxonomy: Taxonomy
    ) -> None:
        """Test creating a topic with all fields."""
        topic = Topic(
            taxonomy_id=sample_taxonomy.id,
            title="Python Programming",
            slug="python-programming",
            description="The Python programming language",
            status="active",
            aliases=["Python", "Py"],
            external_refs={"wikidata": "Q28865"},
            path="/programming/languages/python",
        )
        db_session.add(topic)
        await db_session.commit()

        assert topic.id is not None
        assert topic.taxonomy_id == sample_taxonomy.id
        assert topic.slug == "python-programming"
        assert topic.status == "active"
        assert "Python" in topic.aliases
        assert topic.external_refs["wikidata"] == "Q28865"

    async def test_topic_defaults(
        self, db_session: AsyncSession, sample_taxonomy: Taxonomy
    ) -> None:
        """Test topic with default values."""
        topic = Topic(
            taxonomy_id=sample_taxonomy.id,
            title="Test Topic",
            slug="test-topic",
        )
        db_session.add(topic)
        await db_session.commit()

        assert topic.status == "draft"
        assert topic.aliases == []
        assert topic.external_refs == {}
        assert topic.description is None
        assert topic.path is None

    async def test_topic_unique_slug_per_taxonomy(
        self, db_session: AsyncSession, sample_taxonomy: Taxonomy
    ) -> None:
        """Test that slug must be unique within a taxonomy."""
        topic1 = Topic(
            taxonomy_id=sample_taxonomy.id,
            title="Topic 1",
            slug="test-slug",
        )
        db_session.add(topic1)
        await db_session.commit()

        # Try to create another topic with same slug in same taxonomy
        topic2 = Topic(
            taxonomy_id=sample_taxonomy.id,
            title="Topic 2",
            slug="test-slug",
        )
        db_session.add(topic2)
        with pytest.raises(IntegrityError):
            await db_session.commit()

    async def test_topic_cascade_delete(
        self, db_session: AsyncSession, sample_taxonomy: Taxonomy
    ) -> None:
        """Test that deleting taxonomy deletes topics."""
        topic = Topic(
            taxonomy_id=sample_taxonomy.id,
            title="Test Topic",
            slug="test-topic",
        )
        db_session.add(topic)
        await db_session.commit()

        topic_id = topic.id

        # Delete taxonomy
        await db_session.delete(sample_taxonomy)
        await db_session.commit()

        # Topic should also be deleted
        result = await db_session.get(Topic, topic_id)
        # breakpoint()
        assert result is None


class TestTopicEdgeModel:
    """Tests for TopicEdge model."""

    async def test_create_edge(
        self, db_session: AsyncSession, sample_taxonomy: Taxonomy
    ) -> None:
        """Test creating a topic edge."""
        parent = Topic(taxonomy_id=sample_taxonomy.id, title="Parent", slug="parent")
        child = Topic(taxonomy_id=sample_taxonomy.id, title="Child", slug="child")
        db_session.add_all([parent, child])
        await db_session.flush()

        edge = TopicEdge(
            parent_id=parent.id,
            child_id=child.id,
            role="broader",
            source="manual",
            confidence=0.95,
        )
        db_session.add(edge)
        await db_session.commit()

        assert edge.parent_id == parent.id
        assert edge.child_id == child.id
        assert edge.role == "broader"
        assert edge.confidence == 0.95

    async def test_edge_no_self_loop(
        self, db_session: AsyncSession, sample_taxonomy: Taxonomy
    ) -> None:
        """Test that topic cannot have edge to itself."""
        topic = Topic(taxonomy_id=sample_taxonomy.id, title="Topic", slug="topic")
        db_session.add(topic)
        await db_session.flush()

        edge = TopicEdge(
            parent_id=topic.id,
            child_id=topic.id,
            role="broader",
        )
        db_session.add(edge)
        with pytest.raises(IntegrityError):
            await db_session.commit()


class TestTopicClosureModel:
    """Tests for TopicClosure model."""

    async def test_create_closure(
        self, db_session: AsyncSession, sample_taxonomy: Taxonomy
    ) -> None:
        """Test creating a closure entry."""
        ancestor = Topic(
            taxonomy_id=sample_taxonomy.id, title="Ancestor", slug="ancestor"
        )
        descendant = Topic(
            taxonomy_id=sample_taxonomy.id, title="Descendant", slug="descendant"
        )
        db_session.add_all([ancestor, descendant])
        await db_session.flush()

        closure = TopicClosure(
            ancestor_id=ancestor.id,
            descendant_id=descendant.id,
            depth=1,
        )
        db_session.add(closure)
        await db_session.commit()

        assert closure.depth == 1


class TestMatchModel:
    """Tests for Match model."""

    async def test_create_match(
        self, db_session: AsyncSession, sample_topic: Topic
    ) -> None:
        """Test creating a match."""
        match = Match(
            entity_type="topic",
            entity_id=sample_topic.id,
            system="wikidata",
            external_id="Q28865",
            match_type="exactMatch",
            confidence=0.99,
            evidence={"method": "manual", "verified_by": "curator"},
        )
        db_session.add(match)
        await db_session.commit()

        assert match.id is not None
        assert match.system == "wikidata"
        assert match.match_type == "exactMatch"
        assert match.evidence["method"] == "manual"

    async def test_match_unique_constraint(
        self, db_session: AsyncSession, sample_topic: Topic
    ) -> None:
        """Test that same match cannot be created twice."""
        match1 = Match(
            entity_type="topic",
            entity_id=sample_topic.id,
            system="wikidata",
            external_id="Q28865",
            match_type="exactMatch",
        )
        db_session.add(match1)
        await db_session.commit()

        # Try to create duplicate
        match2 = Match(
            entity_type="topic",
            entity_id=sample_topic.id,
            system="wikidata",
            external_id="Q28865",
            match_type="exactMatch",
        )
        db_session.add(match2)
        with pytest.raises(IntegrityError):
            await db_session.commit()
