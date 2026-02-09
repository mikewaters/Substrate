"""catalog.ontology - Structured metadata ontology for catalog documents.

Provides the shared ``DocumentMeta`` schema and the ``OntologyMappingSpec``
Protocol for source-agnostic ontology mapping.
"""

from catalog.ontology.schema import DocumentMeta, OntologyMappingSpec

__all__ = [
    "DocumentMeta",
    "OntologyMappingSpec",
]
