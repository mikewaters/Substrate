"""catalog.ontology - Structured metadata ontology for catalog documents.

Provides the shared ``DocumentMeta`` schema and the ``FrontmatterSchema``
Protocol for source-agnostic frontmatter mapping.
"""

from catalog.ontology.schema import DocumentMeta, FrontmatterSchema

__all__ = [
    "DocumentMeta",
    "FrontmatterSchema",
]
