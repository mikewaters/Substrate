"""catalog.integrations.heptabase.vault_schema - Heptabase frontmatter schema.

Provides a Heptabase-specific VaultSpec. Currently inherits all behavior
from the base VaultSpec -- customize fields here as Heptabase frontmatter
conventions are established.

Example::

    class MyHeptabaseSchema(HeptabaseVaultSpec):
        tags: list[str] = Field(default_factory=list, json_schema_extra={"maps_to": "tags"})
        type: str | None = Field(None, json_schema_extra={"maps_to": "categories"})
"""

from __future__ import annotations

from catalog.integrations.obsidian.ontology import VaultSpec


class HeptabaseVaultSpec(VaultSpec):
    """Heptabase-specific frontmatter schema.

    Inherits all from_frontmatter/to_document_meta behavior from VaultSpec.
    Override or add fields here to customize Heptabase frontmatter mapping.
    """

    pass
