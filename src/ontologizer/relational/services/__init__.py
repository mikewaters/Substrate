from __future__ import annotations

import logging

from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService

from ontologizer.relational.models import Taxonomy
from ontologizer.relational.repository import TaxonomyRepository
from ontologizer.relational.services.catalog import CatalogService, RepositoryService, ResourceService
from ontologizer.relational.services.topic_suggestion import TopicSuggestionService

# Classifier services have been moved to ontology.classifier.services
# Import them here for backwards compatibility during migration
from ontologizer.relational.services.document_classification import (
    DocumentClassificationService,
)
from ontologizer.relational.services.query import TopicQueryService
from ontologizer.relational.services.topic import TopicTaxonomyService

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
