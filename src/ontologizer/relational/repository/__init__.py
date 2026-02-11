"""Repository for information entities.

This module exports all repository classes for the information domain.
"""

from ontologizer.relational.repository.topic import (
    TopicRepository,
    TopicEdgeRepository,
    TaxonomyRepository,
)
from ontologizer.relational.repository.classifier import (
    TopicSuggestionRepository,
    DocumentClassificationRepository,
    DocumentTopicAssignmentRepository,
)
from ontologizer.relational.repository.catalog import (
    CatalogRepository,
    RepositoryRepository,
    ResourceRepository,
)

__all__ = [
    "TopicRepository",
    "TopicEdgeRepository",
    "TaxonomyRepository",
    "TopicSuggestionRepository",
    "DocumentClassificationRepository",
    "DocumentTopicAssignmentRepository",
    "CatalogRepository",
    "RepositoryRepository",
    "ResourceRepository",
]
