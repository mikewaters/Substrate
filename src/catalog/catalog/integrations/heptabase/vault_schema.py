"""catalog.integrations.heptabase.vault_schema - Heptabase frontmatter schema.

Provides a Heptabase-specific VaultSchema. Currently inherits all behavior
from the base VaultSchema -- customize fields here as Heptabase frontmatter
conventions are established.

Example::

    class MyHeptabaseSchema(HeptabaseVaultSchema):
        tags: list[str] = Field(default_factory=list, json_schema_extra={"maps_to": "tags"})
        type: str | None = Field(None, json_schema_extra={"maps_to": "categories"})
"""

from __future__ import annotations

from catalog.integrations.obsidian.ontology import VaultSchema


class HeptabaseVaultSchema(VaultSchema):
    """Heptabase-specific frontmatter schema.

    Inherits all from_frontmatter/to_document_meta behavior from VaultSchema.
    Override or add fields here to customize Heptabase frontmatter mapping.
    """

    pass
