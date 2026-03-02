"""catalog.integrations.heptabase.links - Heptabase link extraction and resolution.

Pure functions for extracting internal links from Heptabase markdown format,
plus the LinkResolver strategy for the ingest pipeline.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import List
from urllib.parse import unquote

from llama_index.core.schema import BaseNode

from catalog.store.models import DocumentLinkKind
from catalog.store.repositories import DocumentRepository
from catalog.transform.links import strip_link_fragments

__all__ = [
    "extract_heptabase_links",
    "HeptabaseLinkResolver",
]

# Matches [display text](./relative-path) where the target starts with ./
_HEPTABASE_LINK_RE = re.compile(r"\[([^\]]*)\]\(\./([^)]+)\)")


def extract_heptabase_links(text: str) -> List[str]:
    """Extract Heptabase internal links from text.

    Matches patterns like:
        - [Note name.md](./Note name.md)
        - [Display text](./some/path.md)

    The ``./`` prefix distinguishes internal vault links from external URLs.
    The note name is derived by stripping the ``.md`` extension from the
    target path's filename component.

    Args:
        text: Document text to extract links from.

    Returns:
        List of unique link target names (note stems, without .md extension).
    """
    matches = _HEPTABASE_LINK_RE.findall(text)
    links: List[str] = []
    seen: set[str] = set()
    for _display, target in matches:
        # URL-decode (e.g., LifeOS%20Utilities.md -> LifeOS Utilities.md)
        target = unquote(target)
        # Strip fragment identifiers (e.g., Note.md#section -> Note.md)
        target = target.split("#", 1)[0]
        # Get the filename stem (strip .md and any directory components)
        stem = Path(target).stem
        if stem in seen:
            continue
        links.append(stem)
        seen.add(stem)
    return links


class HeptabaseLinkResolver:
    """Resolve Heptabase markdown links by filename stem.

    Heptabase uses ``[text](./path.md)`` internal links. The reader extracts
    these into ``node.metadata["wikilinks"]`` as stems. Resolution uses the
    same stem-based, shortest-path-wins lookup as Obsidian.
    """

    link_kind = DocumentLinkKind.MARKDOWN_LINK

    def __init__(self, wikilinks_key: str = "wikilinks") -> None:
        """Initialize the resolver.

        Args:
            wikilinks_key: Metadata key containing link target names.
        """
        self._wikilinks_key = wikilinks_key

    def extract_links(self, node: BaseNode) -> list[str]:
        """Extract link targets from node metadata, stripping fragments.

        Args:
            node: A document node with links in metadata.

        Returns:
            Deduplicated list of link target names without fragments.
        """
        if not node.metadata:
            return []
        raw_links = node.metadata.get(self._wikilinks_key)
        if not raw_links or not isinstance(raw_links, list):
            return []
        return strip_link_fragments(raw_links)

    def build_lookup(
        self, dataset_id: int, doc_repo: DocumentRepository
    ) -> dict[str, int]:
        """Build stem -> doc_id mapping from all active documents in dataset.

        Uses shortest-path-wins rule for duplicate stems.

        Args:
            dataset_id: ID of the dataset to scope the lookup to.
            doc_repo: Repository for querying documents.

        Returns:
            Mapping from filename stem to document ID.
        """
        stem_to_id: dict[str, int] = {}
        stem_to_path: dict[str, str] = {}

        all_docs = doc_repo.list_by_parent(dataset_id, active_only=True)
        for doc in all_docs:
            stem = PurePosixPath(doc.path).stem
            existing_path = stem_to_path.get(stem)
            if existing_path is None or len(doc.path) < len(existing_path):
                stem_to_id[stem] = doc.id
                stem_to_path[stem] = doc.path

        return stem_to_id
