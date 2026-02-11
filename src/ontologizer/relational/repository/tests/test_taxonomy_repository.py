"""Tests for TaxonomyRepository.

This module tests the TaxonomyRepository, ensuring proper CRUD operations,
domain model conversion, and database interactions in async mode.
"""

import pytest
from advanced_alchemy.exceptions import NotFoundError
from advanced_alchemy.filters import LimitOffset

from ontologizer.relational.models import Taxonomy
from ontologizer.relational.models import Taxonomy as TaxonomyORM
from ontologizer.relational.models import Topic as TopicORM
from ontologizer.relational.repository.topic import TaxonomyRepository

pytestmark = pytest.mark.asyncio


class TestTaxonomyRepositoryCreate:
    """Tests for taxonomy creation."""

    async def test_create_taxonomy_with_all_fields(
        self, taxonomy_repo: TaxonomyRepository
    ) -> None:
        """Test creating a taxonomy with all fields."""
        create_data = TaxonomyORM(
            title="Software Development",
            description="Topics related to software development",
            skos_uri="http://example.org/taxonomy/software",
        )

        taxonomy = await taxonomy_repo.add(create_data)

        assert isinstance(taxonomy, TaxonomyORM)
        assert isinstance(taxonomy.id, str)
        assert taxonomy.title == "Software Development"
        assert taxonomy.description == "Topics related to software development"
        assert taxonomy.skos_uri == "http://example.org/taxonomy/software"
        assert taxonomy.created_at is not None
        assert taxonomy.updated_at is not None

    async def test_create_taxonomy_with_minimal_fields(
        self, taxonomy_repo: TaxonomyRepository
    ) -> None:
        """Test creating a taxonomy with only required fields."""
        create_data = TaxonomyORM(title="Minimal Taxonomy")

        taxonomy = await taxonomy_repo.add(create_data)

        assert taxonomy.title == "Minimal Taxonomy"
        assert taxonomy.description is None
        assert taxonomy.skos_uri is None


class TestTaxonomyRepositoryRead:
    """Tests for taxonomy retrieval."""

    async def test_get_taxonomy_by_id(
        self, taxonomy_repo: TaxonomyRepository, sample_taxonomy_domain: Taxonomy
    ) -> None:
        """Test retrieving a taxonomy by ID."""
        taxonomy = await taxonomy_repo.get(sample_taxonomy_domain.id)

        assert taxonomy is not None
        assert taxonomy.id == sample_taxonomy_domain.id
        assert taxonomy.title == sample_taxonomy_domain.title

    async def test_get_taxonomy_not_found(
        self, taxonomy_repo: TaxonomyRepository
    ) -> None:
        """Test retrieving a non-existent taxonomy."""
        with pytest.raises(NotFoundError):
            await taxonomy_repo.get("tax:nonexistent")

    async def test_list_taxonomies_empty(
        self, taxonomy_repo: TaxonomyRepository
    ) -> None:
        """Test listing taxonomies when none exist."""
        taxonomies, count = await taxonomy_repo.list_and_count()

        assert taxonomies == []
        assert count == 0

    async def test_list_taxonomies_with_data(
        self, taxonomy_repo: TaxonomyRepository
    ) -> None:
        """Test listing taxonomies with data."""
        for i in range(5):
            await taxonomy_repo.add(TaxonomyORM(title=f"Taxonomy {i}"))

        taxonomies, count = await taxonomy_repo.list_and_count()

        assert len(taxonomies) == 5
        assert count == 5
        assert all(isinstance(t, TaxonomyORM) for t in taxonomies)

    async def test_list_taxonomies_with_pagination(
        self, taxonomy_repo: TaxonomyRepository
    ) -> None:
        """Test listing taxonomies with pagination."""
        for i in range(10):
            await taxonomy_repo.add(TaxonomyORM(title=f"Taxonomy {i}"))

        taxonomies_page1, count = await taxonomy_repo.list_and_count(
            LimitOffset(limit=5, offset=0)
        )
        assert len(taxonomies_page1) == 5
        assert count == 10

        taxonomies_page2, count = await taxonomy_repo.list_and_count(
            LimitOffset(limit=5, offset=5)
        )
        assert len(taxonomies_page2) == 5
        assert count == 10

        page1_ids = {t.id for t in taxonomies_page1}
        page2_ids = {t.id for t in taxonomies_page2}
        assert not page1_ids & page2_ids


class TestTaxonomyRepositoryUpdate:
    """Tests for taxonomy updates."""

    async def test_update_taxonomy_title(
        self, taxonomy_repo: TaxonomyRepository, sample_taxonomy_domain: Taxonomy
    ) -> None:
        """Test updating a taxonomy title."""
        obj = await taxonomy_repo.get(sample_taxonomy_domain.id)
        obj.title = "Updated Title"

        taxonomy = await taxonomy_repo.update(obj)

        assert taxonomy is not None
        assert taxonomy.title == "Updated Title"
        assert taxonomy.description == sample_taxonomy_domain.description

    async def test_update_taxonomy_multiple_fields(
        self, taxonomy_repo: TaxonomyRepository, sample_taxonomy_domain: Taxonomy
    ) -> None:
        """Test updating multiple taxonomy fields."""
        obj = await taxonomy_repo.get(sample_taxonomy_domain.id)
        obj.title = "New Title"
        obj.description = "New description"
        obj.skos_uri = "http://example.org/new"

        taxonomy = await taxonomy_repo.update(obj)

        assert taxonomy is not None
        assert taxonomy.title == "New Title"
        assert taxonomy.description == "New description"
        assert taxonomy.skos_uri == "http://example.org/new"

    async def test_update_taxonomy_partial(
        self, taxonomy_repo: TaxonomyRepository, sample_taxonomy_domain: Taxonomy
    ) -> None:
        """Test partial update (only some fields)."""
        original_title = sample_taxonomy_domain.title
        obj = await taxonomy_repo.get(sample_taxonomy_domain.id)
        obj.description = "New description only"

        taxonomy = await taxonomy_repo.update(obj)

        assert taxonomy is not None
        assert taxonomy.title == original_title
        assert taxonomy.description == "New description only"


class TestTaxonomyRepositoryDelete:
    """Tests for taxonomy deletion."""

    async def test_delete_taxonomy(
        self, taxonomy_repo: TaxonomyRepository, sample_taxonomy_domain: Taxonomy
    ) -> None:
        """Test deleting a taxonomy."""
        obj = await taxonomy_repo.delete(sample_taxonomy_domain.id)

        assert obj.id == sample_taxonomy_domain.id

        with pytest.raises(NotFoundError):
            await taxonomy_repo.get(sample_taxonomy_domain.id)

    async def test_delete_taxonomy_not_found(
        self, taxonomy_repo: TaxonomyRepository
    ) -> None:
        """Test deleting a non-existent taxonomy."""
        with pytest.raises(NotFoundError):
            await taxonomy_repo.delete("tax:nonexistent")

    async def test_delete_taxonomy_with_cascade(
        self,
        taxonomy_repo: TaxonomyRepository,
        topic_repo,
        sample_taxonomy_domain: Taxonomy,
    ) -> None:
        """Test deleting a taxonomy cascades to topics."""
        topic = await topic_repo.add(
            TopicORM(
                taxonomy_id=sample_taxonomy_domain.id,
                title="Test Topic",
            )
        )

        await taxonomy_repo.delete(sample_taxonomy_domain.id)

        with pytest.raises(NotFoundError):
            await topic_repo.get(topic.id)


# class TestTaxonomyRepositoryDomainConversion:
#     """Tests for ORM to domain model conversion."""

#     def test_to_domain_conversion(self, taxonomy_repo: TaxonomyRepository) -> None:
#         """Test conversion from ORM to domain model."""
#         create_data = TaxonomyORM(
#             title="Test Taxonomy",
#             description="Test description",
#             skos_uri="http://example.org/test",
#         )

#         taxonomy = taxonomy_repo.add(create_data)

#         # Verify all fields are correctly converted
#         assert isinstance(taxonomy, TaxonomyORM)
#         assert isinstance(taxonomy.id, str)
#         assert isinstance(taxonomy.title, str)
#         assert isinstance(taxonomy.description, str)
#         assert isinstance(taxonomy.skos_uri, str)
#         assert taxonomy.created_at is not None
#         assert taxonomy.updated_at is not None
