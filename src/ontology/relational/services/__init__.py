from __future__ import annotations

import logging

from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService

from ontology.relational.models import Taxonomy
from ontology.relational.repository import TaxonomyRepository
from ontology.relational.services.catalog import CatalogService, RepositoryService, ResourceService
from ontology.relational.services.topic_suggestion import TopicSuggestionService

# Classifier services have been moved to ontology.classifier.services
# Import them here for backwards compatibility during migration
from ontology.relational.services.document_classification import (
    DocumentClassificationService,
)
from ontology.relational.services.query import TopicQueryService
from ontology.relational.services.topic import TopicTaxonomyService

logger = logging.getLogger(__name__)


class TaxonomyService(SQLAlchemyAsyncRepositoryService[Taxonomy]):
    """Service for taxonomy operations.

    This service handles taxonomy business logic, converting between
    Pydantic schemas and domain models, and delegating to repositories.
    """

    repository_type = TaxonomyRepository


__all__ = [
    "TopicTaxonomyService",
    "TopicQueryService",
    "TaxonomyService",
    "TopicSuggestionService",
    "DocumentClassificationService",
    "CatalogService",
    "RepositoryService",
    "ResourceService",
]
