"""Tests for the notes module."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio

# from ontology.notes import get_note_subject
from ontology.schema import TopicCreate, TaxonomyCreate
from ontology.relational.services import TopicTaxonomyService, TaxonomyService

# from ontology.domain import Taxonomy


@pytest_asyncio.fixture
async def taxonomy_with_topics(db_session: AsyncSession):
    """Create a taxonomy with some topics for testing."""
    # Create taxonomy
    taxonomy_service = TaxonomyService(session=db_session)
    taxonomy_data = TaxonomyCreate(title="Technology", description="Technology topics")
    taxonomy = await taxonomy_service.create(taxonomy_data)

    # Create topics
    topic_service = TopicTaxonomyService(session=db_session)

    # Topic 1: Exact title match test
    topic1_data = TopicCreate(
        taxonomy_id=taxonomy.id, title="Machine Learning", status="active"
    )
    topic1 = await topic_service.create(topic1_data)

    # Topic 2: Has aliases
    topic2_data = TopicCreate(
        taxonomy_id=taxonomy.id,
        title="Artificial Intelligence",
        aliases=["AI", "AI Technology", "Machine Intelligence"],
        status="active",
    )
    topic2 = await topic_service.create(topic2_data)

    return {"taxonomy": taxonomy, "topics": [topic1, topic2]}


@pytest_asyncio.fixture
async def empty_taxonomy(db_session: AsyncSession):
    """Create an empty taxonomy for testing topic creation."""
    taxonomy_service = TaxonomyService(session=db_session)
    taxonomy_data = TaxonomyCreate(title="Science", description="Science topics")
    return await taxonomy_service.create(taxonomy_data)


# class TestGetNoteSubject:
#     """Test cases for the get_note_subject function."""

#     async def test_find_existing_topic_by_exact_title(
#         self, taxonomy_with_topics, db_session
#     ):
#         """Test finding an existing topic by exact title match."""
#         result = await get_note_subject(
#             "Machine Learning", "tx:technology", session=db_session
#         )

#         assert isinstance(result, Topic)
#         assert result.title == "Machine Learning"
#         assert result.taxonomy_id == "tx:technology"
#         assert result.status == "active"

#     async def test_create_new_topic_when_not_found(self, empty_taxonomy, db_session):
#         """Test creating a new topic when no existing match is found."""
#         note_title = "Quantum Computing"
#         result = await get_note_subject(note_title, "tx:science", session=db_session)
#         assert isinstance(result, Topic)
#         assert result.title == note_title
#         assert result.taxonomy_id == "tx:science"
#         assert result.status == "draft"  # New topics should be draft by default
#         assert result.id is not None
#         assert result.created_at is not None
#         assert result.updated_at is not None

#     async def test_create_new_topic_generates_slug(self, empty_taxonomy, db_session):
#         """Test that creating a new topic auto-generates a slug."""
#         note_title = "Deep Learning Networks"
#         result = await get_note_subject(note_title, "tx:science", session=db_session)

#         assert result.title == note_title
#         assert result.slug == "deep-learning-networks"

#     async def test_case_sensitive_title_matching(
#         self, taxonomy_with_topics, db_session
#     ):
#         """Test that title matching is case-sensitive for exact matches."""
#         # This should create a new topic with a different title that doesn't conflict
#         result = await get_note_subject(
#             "Deep Learning", "tx:technology", session=db_session
#         )

#         assert result.title == "Deep Learning"
#         # Should be a new topic, not the existing "Machine Learning"
#         existing_topics = taxonomy_with_topics["topics"]
#         assert result.id not in [t.id for t in existing_topics]

#     @pytest.mark.skip(reason="Foreign key constraints not enforced in current SQLite config")
#     async def test_invalid_taxonomy_identifier_raises_error(self, db_session):
#         """Test that using an invalid taxonomy identifier raises an error.

#         TODO: This test is currently skipped because foreign key constraints are not
#         being enforced in the current SQLite configuration. To fix this:

#         1. Enable foreign key enforcement in SQLite by adding:
#            `PRAGMA foreign_keys = ON;` when creating database connections

#         2. Update database session configuration in src/ontology/database/session.py
#            to ensure foreign keys are enforced for all connections

#         3. Once FK constraints are enforced, this test should pass and verify that
#            attempting to create a Topic with a non-existent taxonomy_id raises an
#            IntegrityError (foreign key violation)

#         Expected behavior: Creating a topic with taxonomy_id="tx:nonexistent" when
#         no such taxonomy exists should raise a ForeignKeyError or IntegrityError.
#         """
#         with pytest.raises(
#             Exception  # Foreign key constraint error from SQLAlchemy
#         ):
#             await get_note_subject("Some Topic", "tx:nonexistent", session=db_session)

#     async def test_empty_note_title(self, empty_taxonomy, db_session):
#         """Test handling of empty note title."""
#         # Empty titles should raise a validation error
#         with pytest.raises(Exception):  # ValidationError from Pydantic
#             await get_note_subject("", "tx:science", session=db_session)

#     async def test_whitespace_handling(self, empty_taxonomy, db_session):
#         """Test handling of whitespace in note titles."""
#         note_title = "  Spaced Title  "
#         result = await get_note_subject(note_title, "tx:science", session=db_session)

#         # Should preserve the whitespace as provided
#         assert result.title == note_title
#         assert result.taxonomy_id == "tx:science"

#     async def test_special_characters_in_title(self, empty_taxonomy, db_session):
#         """Test handling of special characters in note titles."""
#         note_title = "C++ Programming & Memory Management (Advanced)"
#         result = await get_note_subject(note_title, "tx:science", session=db_session)

#         assert result.title == note_title
#         assert result.taxonomy_id == "tx:science"
#         # Slug should be properly sanitized
#         assert "/" not in result.slug
#         assert "(" not in result.slug

#     async def test_unicode_characters_in_title(self, empty_taxonomy, db_session):
#         """Test handling of Unicode characters in note titles."""
#         note_title = "机器学习与人工智能"
#         result = await get_note_subject(note_title, "tx:science", session=db_session)

#         assert result.title == note_title
#         assert result.taxonomy_id == "tx:science"

#     async def test_multiple_calls_same_title_return_same_topic(
#         self, empty_taxonomy, db_session
#     ):
#         """Test that multiple calls with the same title return the same topic."""
#         note_title = "Consistent Topic"

#         # First call creates the topic
#         result1 = await get_note_subject(note_title, "tx:science", session=db_session)

#         # Second call should return the same topic
#         result2 = await get_note_subject(note_title, "tx:science", session=db_session)

#         assert result1.id == result2.id
#         assert result1.title == result2.title
#         assert result1.created_at == result2.created_at

#     async def test_exact_match_preferred_over_partial(
#         self, taxonomy_with_topics, db_session
#     ):
#         """Test that exact title matches are preferred over partial matches in aliases."""
#         # Create a topic that has "Machine" in its aliases
#         topic_service = TopicTaxonomyService(session=db_session)
#         topic_data = TopicCreate(
#             taxonomy_id=taxonomy_with_topics["taxonomy"].id,
#             title="Hardware",
#             aliases=["Machine Hardware", "Physical Machine"],
#             status="active",
#         )
#         await topic_service.create(topic_data)

#         # This should match the existing "Machine Learning" by exact title,
#         # not the "Hardware" topic by alias partial match
#         result = await get_note_subject(
#             "Machine Learning", "tx:technology", session=db_session
#         )

#         assert result.title == "Machine Learning"
#         assert result.title != "Hardware"


# class TestGetNoteSubjectEdgeCases:
#     """Test edge cases and error conditions for get_note_subject."""

#     async def test_database_session_handling(self, empty_taxonomy, db_session):
#         """Test that database sessions are properly managed."""
#         # This test mainly ensures no session leaks or connection issues
#         note_title = "Session Test Topic"

#         # Make multiple sequential calls
#         for i in range(3):
#             result = await get_note_subject(
#                 f"{note_title} {i}", "tx:science", session=db_session
#             )
#             assert result.title == f"{note_title} {i}"
#             assert result.taxonomy_id == "tx:science"
