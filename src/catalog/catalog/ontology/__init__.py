"""catalog.ontology - Structured metadata ontology for catalog documents.

Provides the shared ``DocumentMeta`` schema and the ``VaultSchema`` base
class for mapping source-specific frontmatter into the ontology.
"""

from catalog.ontology.schema import DocumentMeta
from catalog.ontology.vault_schema import VaultSchema

__all__ = [
    "DocumentMeta",
    "VaultSchema",
]
