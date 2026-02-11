# import pytest

# pytestmark = pytest.mark.asyncio

# from ontology.models import Taxonomy
# from ontology.models import Topic


# class TestTopicDomain:
#     """Tests for Topic dataclass."""

#     async def test_generate_slug_at_init(
#         self, sample_taxonomy_domain: Taxonomy
#     ) -> None:
#         """Test basic slug generation when dataclass is initialized."""
#         topic = Topic(
#             taxonomy_id=sample_taxonomy_domain.id, title="Hello World"
#         )
#         assert topic.slug == "hello-world"
