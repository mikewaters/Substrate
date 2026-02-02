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
