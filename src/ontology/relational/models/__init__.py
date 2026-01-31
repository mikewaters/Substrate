"""ORM models for the ontology package."""

from ontology.relational.models.catalog import (
    Catalog,
    Repository,
    Purpose,
    Resource,
    Bookmark,
    Collection,
    Document,
    Note,
    resource_related_resources,
    resource_related_topics
)

from ontology.relational.models.topic import (
    Taxonomy,
    Topic,
    TopicEdge,
    TopicClosure,
)

from ontology.relational.models.classifier import (
    TopicSuggestion,
    Match,
    DocumentClassification,
    DocumentTopicAssignment,
)
from ontology.relational.models.work import (
    Activity
)

__all__ = [
    # Catalog models
    "Catalog",
    "Repository",
    "Purpose",
    "Resource",
    "Bookmark",
    "Collection",
    "Document",
    "Note",
    "resource_related_resources",
    "resource_related_topics",
    # Topic/Taxonomy models
    "Taxonomy",
    "Topic",
    "TopicEdge",
    "TopicClosure",
    # Classifier models
    "TopicSuggestion",
    "Match",
    "DocumentClassification",
    "DocumentTopicAssignment",
    # Work models
    "Activity",
]
