"""catalog.integrations.obsidian - Obsidian vault integration.

Centralizes all Obsidian-specific code: vault reading, frontmatter schema
mapping, ingestion configuration, and wikilink resolution.
"""

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

from catalog.ingest.sources import create_reader, create_source

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
