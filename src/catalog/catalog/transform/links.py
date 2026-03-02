"""catalog.transform.links - Generic inter-document link resolution.

Provides a protocol-based link resolution transform that delegates
extraction and lookup strategy to a LinkResolver implementation.
Each integration (Obsidian, Heptabase, etc.) provides its own resolver.

Runs **after** PersistenceTransform so that every document already has
a ``doc_id`` in its node metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from agentlayer.logging import get_logger
from llama_index.core.schema import BaseNode, TransformComponent

from catalog.store.models import DocumentLinkKind
from catalog.store.repositories import DocumentLinkRepository, DocumentRepository
from agentlayer.session import current_session

__all__ = [
    "LinkResolver",
    "LinkResolutionTransform",
    "LinkResolutionStats",
    "strip_link_fragments",
]

logger = get_logger(__name__)


def strip_link_fragments(links: list[object]) -> list[str]:
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


@runtime_checkable
class LinkResolver(Protocol):
    """Strategy for extracting and resolving inter-document links.

    Each integration implements this protocol to define how links are
    extracted from node metadata and how target names are resolved to
    document IDs.
    """

    link_kind: DocumentLinkKind

    def extract_links(self, node: BaseNode) -> list[str]:
        """Extract raw link target names from a node's metadata.

        Args:
            node: A document node with metadata.

        Returns:
            List of target names to resolve (e.g. wikilink stems, relative paths).
        """
        ...

    def build_lookup(
        self, dataset_id: int, doc_repo: DocumentRepository
    ) -> dict[str, int]:
        """Build a target_name -> doc_id mapping for the dataset.

        Args:
            dataset_id: ID of the dataset to scope the lookup to.
            doc_repo: Repository for querying documents.

        Returns:
            Mapping from target name to document ID.
        """
        ...


@dataclass
class LinkResolutionStats:
    """Statistics from a link resolution pass.

    Attributes:
        resolved: Number of links successfully resolved to document IDs.
        unresolved: Number of links that could not be matched.
        self_links: Number of self-links skipped.
        documents_processed: Number of documents that had links.
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
    """Resolve inter-document links and persist DocumentLink rows.

    Delegates link extraction and target resolution to a ``LinkResolver``
    strategy. Runs after PersistenceTransform so that every document
    already has a ``doc_id`` in its node metadata.

    Attributes:
        stats: LinkResolutionStats with counts of resolved/unresolved/self-links.
    """

    _dataset_id: int = 0
    _resolver: LinkResolver | None = None
    _stats: LinkResolutionStats | None = None

    def __init__(
        self,
        dataset_id: int,
        resolver: LinkResolver,
        **kwargs: Any,
    ) -> None:
        """Initialize the link resolution transform.

        Args:
            dataset_id: ID of the dataset whose documents to resolve against.
            resolver: Strategy for extracting and resolving links.
            **kwargs: Additional arguments passed to TransformComponent.
        """
        super().__init__(**kwargs)
        self._dataset_id = dataset_id
        self._resolver = resolver
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
        """Resolve links for all nodes and create DocumentLink rows.

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

        # Delegate lookup construction to the resolver.
        name_to_id = self._resolver.build_lookup(self._dataset_id, doc_repo)

        for node in nodes:
            if not node.metadata:
                continue
            targets = self._resolver.extract_links(node)
            if not targets:
                continue
            self._process_node(
                node, targets, name_to_id, link_repo, session
            )

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
        targets: list[str],
        name_to_id: dict[str, int],
        link_repo: DocumentLinkRepository,
        session,
    ) -> None:
        """Resolve links for a single node and create DocumentLink rows."""
        doc_id = node.metadata.get("doc_id")
        if doc_id is None:
            return

        self.stats.documents_processed += 1

        # Clear existing outgoing links for idempotent re-ingestion.
        # Flush after delete so new inserts don't conflict with pending deletes.
        link_repo.delete_outgoing(doc_id)
        session.flush()

        for target_name in targets:
            target_id = name_to_id.get(target_name)
            if target_id is None:
                logger.trace(f"Unresolved link: '{target_name}' from doc {doc_id}")
                self.stats.unresolved += 1
                continue

            if target_id == doc_id:
                self.stats.self_links += 1
                continue

            link_repo.upsert(doc_id, target_id, self._resolver.link_kind)
            self.stats.resolved += 1
