"""Repository for information entities.

This module exports all repository classes for the information domain.
"""

from ontology.relational.repository.topic import (
    TopicRepository,
    TopicEdgeRepository,
    TaxonomyRepository,
)
from ontology.relational.repository.classifier import (
    TopicSuggestionRepository,
    DocumentClassificationRepository,
    DocumentTopicAssignmentRepository,
)
from ontology.relational.repository.catalog import (
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
