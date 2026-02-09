"""catalog.integrations.heptabase - Heptabase export integration.

Reads markdown exports from Heptabase. Reuses Obsidian vault reading
infrastructure with Heptabase-specific link extraction and ontology specs.
"""

from typing import TYPE_CHECKING

from catalog.integrations.heptabase.links import extract_heptabase_links
from catalog.integrations.heptabase.reader import (
    HeptabaseVaultReader,
    HeptabaseVaultSource,
)
from catalog.integrations.heptabase.source import SourceHeptabaseConfig
from catalog.integrations.heptabase.vault_schema import HeptabaseVaultSpec

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
        - ontology_spec: Dotted path to VaultSpec subclass for frontmatter mapping.

    Args:
        source_config: Generic source configuration from YAML job file.

    Returns:
        IngestHeptabaseConfig instance ready for create_source().
    """
    from catalog.ingest.job import _import_class

    ontology_spec_path = source_config.options.get("ontology_spec")
    ontology_spec_cls = _import_class(ontology_spec_path) if ontology_spec_path else None
    dataset_name = source_config.dataset_name or source_config.source_path.name

    return SourceHeptabaseConfig(
        source_path=source_config.source_path,
        dataset_name=dataset_name,
        catalog_name=source_config.catalog_name,
        force=source_config.force,
        incremental=source_config.incremental,
        if_modified_since=source_config.if_modified_since,
        ontology_spec=ontology_spec_cls,
    )


@create_source.register
def _(config: SourceHeptabaseConfig):
    return HeptabaseVaultSource(
        config.source_path,
        ontology_spec=config.ontology_spec,
        if_modified_since=config.if_modified_since,
    )


@create_reader.register
def _(config: SourceHeptabaseConfig):
    return HeptabaseVaultReader(config.source_path)


__all__ = [
    "HeptabaseVaultReader",
    "HeptabaseVaultSpec",
    "HeptabaseVaultSource",
    "SourceHeptabaseConfig",
    "extract_heptabase_links",
]
