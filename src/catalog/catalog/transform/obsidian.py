"""catalog.transform.obsidian - Obsidian vault metadata enrichment transform.

Derives title, description, and link relationship metadata from
ObsidianVaultReader node metadata for use in LlamaIndex ingestion pipelines.

Should run *before* PersistenceTransform so that derived title/description
values are available when documents are persisted.
"""

from typing import Any

from agentlayer.logging import get_logger
from llama_index.core.schema import BaseNode, TransformComponent

__all__ = [
    "ObsidianEnrichmentTransform",
]

logger = get_logger(__name__)


class ObsidianEnrichmentTransform(TransformComponent):
    """Enriches nodes with title, description, and link metadata from Obsidian.

    For each node, derives:

    **Title** (priority order):
    1. ``frontmatter.title`` — explicit YAML frontmatter title
    2. ``frontmatter.aliases[0]`` — first Obsidian alias
    3. ``note_name`` — filename stem (always present from ObsidianVaultReader)

    **Description** (priority order):
    1. ``frontmatter.description`` — explicit YAML frontmatter description
    2. Value from a configurable summary metadata key (e.g. upstream summarizer)
    3. ``None``

    **Links:**
    - Reads ``wikilinks`` and ``backlinks`` from node metadata
    - Normalizes them into ``_obsidian_wikilinks`` and ``_obsidian_backlinks``
    - Prefixed keys are excluded from embedding metadata by convention

    Attributes:
        title_key: Metadata key to write the derived title to.
        description_key: Metadata key to write the derived description to.
        summary_key: Metadata key to read an upstream summary from.
        frontmatter_key: Metadata key where the frontmatter dict lives.
    """

    title_key: str = "title"
    description_key: str = "description"
    summary_key: str = "summary"
    frontmatter_key: str = "frontmatter"

    def __init__(
        self,
        *,
        title_key: str = "title",
        description_key: str = "description",
        summary_key: str = "summary",
        frontmatter_key: str = "frontmatter",
        **kwargs: Any,
    ) -> None:
        """Initialize the Obsidian enrichment transform.

        Args:
            title_key: Metadata key to write the derived title to.
            description_key: Metadata key to write the derived description to.
            summary_key: Metadata key to read an upstream summary from.
            frontmatter_key: Metadata key where the frontmatter dict lives.
            **kwargs: Additional arguments passed to TransformComponent.
        """
        super().__init__(**kwargs)
        self.title_key = title_key
        self.description_key = description_key
        self.summary_key = summary_key
        self.frontmatter_key = frontmatter_key

    def __call__(
        self,
        nodes: list[BaseNode],
        **kwargs: Any,
    ) -> list[BaseNode]:
        """Enrich each node with derived title, description, and link metadata.

        Args:
            nodes: List of nodes from ObsidianVaultReader.
            **kwargs: Additional arguments (unused).

        Returns:
            The same nodes with enriched metadata.
        """
        enriched = 0
        for node in nodes:
            if not node.metadata:
                continue
            self._enrich_node(node)
            enriched += 1

        logger.info(f"ObsidianEnrichmentTransform: enriched {enriched}/{len(nodes)} nodes")
        return nodes

    def _enrich_node(self, node: BaseNode) -> None:
        """Enrich a single node with derived metadata."""
        meta = node.metadata
        fm = meta.get(self.frontmatter_key)
        if not isinstance(fm, dict):
            fm = {}

        # --- Title derivation ---
        title = self._derive_title(meta, fm)
        meta[self.title_key] = title

        # --- Description derivation ---
        description = self._derive_description(meta, fm)
        meta[self.description_key] = description

        # --- Link normalization ---
        self._normalize_links(meta)

    def _derive_title(self, meta: dict[str, Any], fm: dict[str, Any]) -> str:
        """Derive title from frontmatter or note_name.

        Args:
            meta: Full node metadata dict.
            fm: Parsed frontmatter dict.

        Returns:
            Derived title string.
        """
        # 1. Explicit frontmatter title
        fm_title = fm.get("title")
        if fm_title and isinstance(fm_title, str) and fm_title.strip():
            return fm_title.strip()

        # 2. First alias
        aliases = fm.get("aliases")
        if isinstance(aliases, list) and aliases:
            first = aliases[0]
            if isinstance(first, str) and first.strip():
                return first.strip()

        # 3. note_name (filename stem from ObsidianVaultReader)
        note_name = meta.get("note_name")
        if note_name and isinstance(note_name, str):
            return note_name.strip()

        # Last resort: empty string (shouldn't happen with ObsidianVaultReader)
        return ""

    def _derive_description(self, meta: dict[str, Any], fm: dict[str, Any]) -> str | None:
        """Derive description from frontmatter or upstream summary.

        Args:
            meta: Full node metadata dict.
            fm: Parsed frontmatter dict.

        Returns:
            Derived description string, or None if unavailable.
        """
        # 1. Explicit frontmatter description
        fm_desc = fm.get("description")
        if fm_desc and isinstance(fm_desc, str) and fm_desc.strip():
            return fm_desc.strip()

        # 2. Upstream summary
        summary = meta.get(self.summary_key)
        if summary and isinstance(summary, str) and summary.strip():
            return summary.strip()

        return None

    def _normalize_links(self, meta: dict[str, Any]) -> None:
        """Normalize wikilinks and backlinks into prefixed metadata keys.

        Args:
            meta: Node metadata dict (modified in-place).
        """
        wikilinks = meta.get("wikilinks")
        if isinstance(wikilinks, list):
            meta["_obsidian_wikilinks"] = wikilinks

        backlinks = meta.get("backlinks")
        if isinstance(backlinks, list):
            meta["_obsidian_backlinks"] = backlinks
