"""catalog.integrations.heptabase.reader - Heptabase export source reader.

Extends ObsidianVaultReader with Heptabase-specific link extraction.
Heptabase uses standard markdown links of the form ``[Note name.md](./Note name.md)``
where the ``./`` prefix distinguishes internal links from external URLs.
"""

from __future__ import annotations

from datetime import datetime
from functools import cached_property
from pathlib import Path
from typing import Any, List

from agentlayer.logging import get_logger
from llama_index.core import Document
from llama_index.core.node_parser import MarkdownNodeParser

from catalog.integrations.heptabase.links import extract_heptabase_links
from catalog.integrations.obsidian.reader import (
    ObsidianMarkdownNormalize,
    ObsidianVaultReader,
)
from catalog.integrations.obsidian.transforms import LinkResolutionTransform
from catalog.ingest.sources import BaseSource
from catalog.ontology import OntologyMappingSpec
from catalog.store.models import DocumentLinkKind

__all__ = [
    "HeptabaseVaultReader",
    "HeptabaseVaultSource",
    "extract_heptabase_links",
]

logger = get_logger(__name__)


class HeptabaseVaultReader(ObsidianVaultReader):
    """Reader for Heptabase markdown exports.

    Extends ObsidianVaultReader with Heptabase-specific link extraction.
    All other behavior (frontmatter parsing, file traversal, task extraction,
    backlink building) is inherited.

    Args:
        input_dir: Path to the Heptabase export directory.
        **kwargs: Additional arguments passed to ObsidianVaultReader.
    """

    def _extract_links(self, text: str) -> List[str]:
        """Extract Heptabase internal links from document text.

        Overrides the default wikilink extraction with Heptabase's
        standard markdown link format: ``[Name.md](./Name.md)``.

        Args:
            text: Document text.

        Returns:
            List of unique link target names (note stems).
        """
        return extract_heptabase_links(text)


class HeptabaseVaultSource(BaseSource):
    """Populates a Dataset from a Heptabase export directory."""

    type_name = "heptabase"

    def __init__(
        self,
        path: str | Path,
        ontology_spec: type[OntologyMappingSpec] | None = None,
        if_modified_since: datetime | None = None,
    ) -> None:
        """Initialize Heptabase source.

        Args:
            path: Path to the Heptabase export root directory.
            ontology_spec: Optional OntologyMappingSpec subclass for frontmatter mapping.
            if_modified_since: If set, only ingest files modified at or after
                this timestamp.
        """
        self.path = Path(path).resolve()
        self.ontology_spec = ontology_spec
        self.reader = HeptabaseVaultReader(input_dir=self.path)

        if if_modified_since is not None:
            ts = if_modified_since.timestamp()
            self.reader.input_files = [
                p for p in self.path.rglob("*.md")
                if p.stat().st_mtime >= ts
            ]
            logger.info(
                f"Filtered to {len(self.reader.input_files)} files "
                f"modified since {if_modified_since}"
            )

        logger.debug(f"Initialized HeptabaseVaultSource for path: {self.path}")

    def transforms(self, dataset_id: int) -> tuple[list, list]:
        """Get the list of transforms to apply for this source.

        Returns:
            Tuple of (pre-persist transforms, post-persist transforms).
        """
        parser = MarkdownNodeParser(
            include_metadata=True,
            include_prev_next_rel=True,
            header_path_separator=" / ",
        )
        transforms = (
            [],
            [
                LinkResolutionTransform(
                    dataset_id=dataset_id,
                    link_kind=DocumentLinkKind.MARKDOWN_LINK,
                ),
                ObsidianMarkdownNormalize(),
                parser,
            ],
        )
        return transforms

    @cached_property
    def documents(self) -> list[Document]:
        """Load and return all documents from the Heptabase export."""
        logger.info(f"Loading documents from Heptabase export at: {self.path}")
        docs = self.reader.load_data()
        return docs
