"""catalog.integrations.obsidian.links - Obsidian wikilink resolution strategy.

Implements the LinkResolver protocol for Obsidian vaults. Resolves
wikilink note names using stem-based lookup with shortest-path-wins
for duplicate stems (matching Obsidian's convention).
"""

from __future__ import annotations

from pathlib import PurePosixPath

from llama_index.core.schema import BaseNode

from catalog.store.models import DocumentLinkKind
from catalog.store.repositories import DocumentRepository
from catalog.transform.links import strip_link_fragments

__all__ = [
    "ObsidianWikilinkResolver",
]


class ObsidianWikilinkResolver:
    """Resolve Obsidian wikilinks by filename stem (shortest-path wins).

    Extracts wikilinks from node metadata and resolves them against
    the dataset's documents using Obsidian's stem-based convention:
    when multiple documents share a stem, the one with the shortest
    path wins.
    """

    link_kind = DocumentLinkKind.WIKILINK

    def __init__(self, wikilinks_key: str = "wikilinks") -> None:
        """Initialize the resolver.

        Args:
            wikilinks_key: Metadata key containing wikilink target names.
        """
        self._wikilinks_key = wikilinks_key

    def extract_links(self, node: BaseNode) -> list[str]:
        """Extract wikilink targets from node metadata, stripping fragments.

        Args:
            node: A document node with wikilinks in metadata.

        Returns:
            Deduplicated list of wikilink target names without fragments.
        """
        if not node.metadata:
            return []
        raw_wikilinks = node.metadata.get(self._wikilinks_key)
        if not raw_wikilinks or not isinstance(raw_wikilinks, list):
            return []
        return strip_link_fragments(raw_wikilinks)

    def build_lookup(
        self, dataset_id: int, doc_repo: DocumentRepository
    ) -> dict[str, int]:
        """Build stem -> doc_id mapping from all active documents in dataset.

        Uses Obsidian's shortest-path rule: when multiple documents share
        a filename stem, the one with the shortest path wins.

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
