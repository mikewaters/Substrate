"""catalog.integrations.obsidian - Obsidian vault integration.

Centralizes all Obsidian-specific code: vault reading, frontmatter schema
mapping, ingestion configuration, and wikilink resolution.
"""

from typing import TYPE_CHECKING

from catalog.integrations.obsidian.reader import (
    ObsidianMarkdownReader,
    ObsidianVaultReader,
    extract_tasks,
    extract_wikilinks,
    parse_frontmatter,
)
from catalog.integrations.obsidian.source import ObsidianVaultSource, SourceObsidianConfig
from catalog.integrations.obsidian.transforms import (
    LinkResolutionStats,
    LinkResolutionTransform,
)
from catalog.integrations.obsidian.ontology import VaultSchema

from catalog.ingest.sources import (
    create_reader,
    create_source,
    register_ingest_config_factory,
)

if TYPE_CHECKING:
    from catalog.ingest.job import SourceConfig


@register_ingest_config_factory("obsidian")
def create_obsidian_ingest_config(source_config: "SourceConfig") -> SourceObsidianConfig:
    """Create IngestObsidianConfig from generic SourceConfig.

    Interprets obsidian-specific options:
        - ontology_spec: Dotted path to VaultSchema subclass for frontmatter mapping.

    Args:
        source_config: Generic source configuration from YAML job file.

    Returns:
        IngestObsidianConfig instance ready for create_source().
    """
    from catalog.ingest.job import _import_class

    ontology_spec_path = source_config.options.get("ontology_spec")
    ontology_spec_cls = _import_class(ontology_spec_path) if ontology_spec_path else None
    dataset_name = source_config.dataset_name or source_config.source_path.name

    return SourceObsidianConfig(
        source_path=source_config.source_path,
        dataset_name=dataset_name,
        catalog_name=source_config.catalog_name,
        force=source_config.force,
        incremental=source_config.incremental,
        if_modified_since=source_config.if_modified_since,
        ontology_spec=ontology_spec_cls,
    )


@create_source.register
def _(config: SourceObsidianConfig):
    return ObsidianVaultSource(
        config.source_path,
        ontology_spec=config.ontology_spec,
        if_modified_since=config.if_modified_since,
    )


@create_reader.register
def _(config: SourceObsidianConfig):
    return ObsidianVaultReader(config.source_path)


__all__ = [
    "SourceObsidianConfig",
    "LinkResolutionStats",
    "LinkResolutionTransform",
    "ObsidianMarkdownReader",
    "ObsidianVaultReader",
    "ObsidianVaultSource",
    "VaultSchema",
    "extract_tasks",
    "extract_wikilinks",
    "parse_frontmatter",
]
