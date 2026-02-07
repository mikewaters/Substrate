"""catalog.integrations.heptabase - Heptabase export integration.

Reads markdown exports from Heptabase. Reuses Obsidian vault reading
infrastructure with Heptabase-specific link extraction and vault schema.
"""

from typing import TYPE_CHECKING

from catalog.integrations.heptabase.links import extract_heptabase_links
from catalog.integrations.heptabase.reader import (
    HeptabaseVaultReader,
    HeptabaseVaultSource,
)
from catalog.integrations.heptabase.source import SourceHeptabaseConfig
from catalog.integrations.heptabase.vault_schema import HeptabaseVaultSchema

from catalog.ingest.sources import (
    create_reader,
    create_source,
    register_ingest_config_factory,
)

if TYPE_CHECKING:
    from catalog.ingest.job import SourceConfig


@register_ingest_config_factory("heptabase")
def create_heptabase_ingest_config(source_config: "SourceConfig") -> SourceHeptabaseConfig:
    """Create IngestHeptabaseConfig from generic SourceConfig.

    Interprets heptabase-specific options:
        - vault_schema: Dotted path to VaultSchema subclass for frontmatter mapping.

    Args:
        source_config: Generic source configuration from YAML job file.

    Returns:
        IngestHeptabaseConfig instance ready for create_source().
    """
    from catalog.ingest.job import _import_class

    vault_schema_path = source_config.options.get("vault_schema")
    vault_schema_cls = _import_class(vault_schema_path) if vault_schema_path else None
    dataset_name = source_config.dataset_name or source_config.source_path.name

    return SourceHeptabaseConfig(
        source_path=source_config.source_path,
        dataset_name=dataset_name,
        catalog_name=source_config.catalog_name,
        force=source_config.force,
        incremental=source_config.incremental,
        if_modified_since=source_config.if_modified_since,
        vault_schema=vault_schema_cls,
    )


@create_source.register
def _(config: SourceHeptabaseConfig):
    return HeptabaseVaultSource(
        config.source_path,
        vault_schema=config.vault_schema,
        if_modified_since=config.if_modified_since,
    )


@create_reader.register
def _(config: SourceHeptabaseConfig):
    return HeptabaseVaultReader(config.source_path)


__all__ = [
    "HeptabaseVaultReader",
    "HeptabaseVaultSchema",
    "HeptabaseVaultSource",
    "SourceHeptabaseConfig",
    "extract_heptabase_links",
]
