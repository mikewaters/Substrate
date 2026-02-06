"""catalog.integrations.obsidian.transforms - Obsidian-specific pipeline transforms.

Provides LinkResolutionTransform which resolves Obsidian wikilink note names
to document IDs and persists DocumentLink rows. Uses Obsidian's stem-based
lookup convention (shortest-path wins for duplicate stems).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agentlayer.logging import get_logger
from llama_index.core.schema import BaseNode, TransformComponent
from sqlalchemy.orm import Session

from catalog.store.models import DocumentLinkKind
from catalog.store.repositories import DocumentLinkRepository, DocumentRepository
from catalog.store.session_context import current_session

__all__ = [
    "LinkResolutionTransform",
    "LinkResolutionStats",
]

logger = get_logger(__name__)


def _strip_fragments(links: list[object]) -> list[str]:
    """Strip fragment identifiers from link names and deduplicate.

    ``"Note#Section"`` -> ``"Note"``; ``"#Section"`` (empty note name) is
    excluded. Order-preserving deduplication via ``dict.fromkeys``.
    """
    stripped: list[str] = []
    for raw in links:
        name = str(raw).split("#", 1)[0]
        if name:
            stripped.append(name)
    return list(dict.fromkeys(stripped))


@dataclass
class LinkResolutionStats:
    """Statistics from a link resolution pass.

    Attributes:
        resolved: Number of wikilinks successfully resolved to document IDs.
        unresolved: Number of wikilinks that could not be matched.
        self_links: Number of self-links skipped.
        documents_processed: Number of documents that had wikilinks.
    """

    resolved: int = 0
    unresolved: int = 0
    self_links: int = 0
    documents_processed: int = 0

    def reset(self) -> None:
        """Reset all statistics to zero."""
        self.resolved = 0
        self.unresolved = 0
        self.self_links = 0
        self.documents_processed = 0


class LinkResolutionTransform(TransformComponent):
    """Resolve wikilink note names to document IDs and persist DocumentLink rows.

    Runs **after** PersistenceTransform so that every document already has a
    ``doc_id`` in its node metadata. Reads ``wikilinks`` from each node
    (as written by ObsidianVaultReader), strips fragment identifiers
    internally, looks up the target document by filename stem, and creates
    ``DocumentLink`` rows for resolved links.

    Attributes:
        stats: LinkResolutionStats with counts of resolved/unresolved/self-links.
    """

    _dataset_id: int = 0
    _wikilinks_key: str = "wikilinks"
    _link_kind: DocumentLinkKind = DocumentLinkKind.WIKILINK
    _stats: LinkResolutionStats | None = None

    def __init__(
        self,
        dataset_id: int,
        *,
        wikilinks_key: str = "wikilinks",
        link_kind: DocumentLinkKind = DocumentLinkKind.WIKILINK,
        **kwargs: Any,
    ) -> None:
        """Initialize the link resolution transform.

        Args:
            dataset_id: ID of the dataset whose documents to resolve against.
            wikilinks_key: Metadata key containing wikilink target names.
            link_kind: Kind of link to create (default: WIKILINK).
            **kwargs: Additional arguments passed to TransformComponent.
        """
        super().__init__(**kwargs)
        self._dataset_id = dataset_id
        self._wikilinks_key = wikilinks_key
        self._link_kind = link_kind
        self._stats = LinkResolutionStats()

    @property
    def stats(self) -> LinkResolutionStats:
        """Get link resolution statistics."""
        if self._stats is None:
            self._stats = LinkResolutionStats()
        return self._stats

    def __call__(
        self,
        nodes: list[BaseNode],
        **kwargs: Any,
    ) -> list[BaseNode]:
        """Resolve wikilinks for all nodes and create DocumentLink rows.

        Args:
            nodes: List of nodes (with ``doc_id`` in metadata).
            **kwargs: Additional arguments (unused).

        Returns:
            The same nodes unchanged (passthrough).
        """
        self.stats.reset()

        session = current_session()
        doc_repo = DocumentRepository()
        link_repo = DocumentLinkRepository()

        # Build stem -> doc_id mapping from all documents in dataset.
        # Prefer shorter paths for duplicate stems (Obsidian shortest-path rule).
        stem_to_id: dict[str, int] = {}
        stem_to_path: dict[str, str] = {}
        all_docs = doc_repo.list_by_parent(self._dataset_id, active_only=True)
        for doc in all_docs:
            from pathlib import PurePosixPath
            stem = PurePosixPath(doc.path).stem
            existing_path = stem_to_path.get(stem)
            if existing_path is None or len(doc.path) < len(existing_path):
                stem_to_id[stem] = doc.id
                stem_to_path[stem] = doc.path

        for node in nodes:
            #breakpoint()
            if not node.metadata:
                continue
            raw_wikilinks = node.metadata.get(self._wikilinks_key)
            if not raw_wikilinks or not isinstance(raw_wikilinks, list):
                continue
            # Strip fragments internally before resolution.
            normalized = _strip_fragments(raw_wikilinks)
            self._process_node(node, normalized, stem_to_id, link_repo, session)

        session.flush()

        logger.info(
            f"LinkResolutionTransform complete: "
            f"resolved={self.stats.resolved}, "
            f"unresolved={self.stats.unresolved}, "
            f"self_links={self.stats.self_links}, "
            f"documents={self.stats.documents_processed}"
        )

        return nodes

    def _process_node(
        self,
        node: BaseNode,
        wikilinks: list[str],
        stem_to_id: dict[str, int],
        link_repo: DocumentLinkRepository,
        session: Session,
    ) -> None:
        """Resolve wikilinks for a single node and create DocumentLink rows."""
        doc_id = node.metadata.get("doc_id")
        name = node.metadata.get("note_name")
        if doc_id is None:
            return

        self.stats.documents_processed += 1

        # Clear existing outgoing links for idempotent re-ingestion.
        # Flush after delete so new inserts don't conflict with pending deletes.
        link_repo.delete_outgoing(doc_id)
        session.flush()

        for target_name in wikilinks:
            target_id = stem_to_id.get(target_name)
            if target_id is None:
                logger.debug(f"Unresolved wikilink: '{target_name}' from doc {doc_id} '{name}'")
                self.stats.unresolved += 1
                continue

            if target_id == doc_id:
                self.stats.self_links += 1
                continue

            link_repo.upsert(doc_id, target_id, self._link_kind)
            self.stats.resolved += 1
