"""catalog.integrations.obsidian - Obsidian vault integration.

Centralizes all Obsidian-specific code: vault reading, frontmatter schema
mapping, ingestion configuration, and wikilink resolution.
"""

from typing import TYPE_CHECKING

from catalog.integrations.obsidian.reader import (
    ObsidianMarkdownReader,
    ObsidianVaultReader,
    ObsidianVaultSource,
    extract_tasks,
    extract_wikilinks,
    parse_frontmatter,
)
from catalog.integrations.obsidian.schemas import IngestObsidianConfig
from catalog.integrations.obsidian.transforms import (
    LinkResolutionStats,
    LinkResolutionTransform,
)
from catalog.integrations.obsidian.vault_schema import VaultSchema

from catalog.ingest.sources import (
    create_reader,
    create_source,
    register_ingest_config_factory,
)

if TYPE_CHECKING:
    from catalog.ingest.job import SourceConfig


@register_ingest_config_factory("obsidian")
def create_obsidian_ingest_config(source_config: "SourceConfig") -> IngestObsidianConfig:
    """Create IngestObsidianConfig from generic SourceConfig.

    Interprets obsidian-specific options:
        - vault_schema: Dotted path to VaultSchema subclass for frontmatter mapping.

    Args:
        source_config: Generic source configuration from YAML job file.

    Returns:
        IngestObsidianConfig instance ready for create_source().
    """
    from catalog.ingest.job import _import_class

    vault_schema_path = source_config.options.get("vault_schema")
    vault_schema_cls = _import_class(vault_schema_path) if vault_schema_path else None
    dataset_name = source_config.dataset_name or source_config.source_path.name

    return IngestObsidianConfig(
        source_path=source_config.source_path,
        dataset_name=dataset_name,
        force=source_config.force,
        vault_schema=vault_schema_cls,
    )


@create_source.register
def _(config: IngestObsidianConfig):
    return ObsidianVaultSource(config.source_path, vault_schema=config.vault_schema)


@create_reader.register
def _(config: IngestObsidianConfig):
    return ObsidianVaultReader(config.source_path)


__all__ = [
    "IngestObsidianConfig",
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
