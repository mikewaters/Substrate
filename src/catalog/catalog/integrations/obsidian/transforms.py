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

from catalog.ontology import FrontmatterSchema, DocumentMeta
from catalog.store.models import DocumentLinkKind
from catalog.store.repositories import DocumentLinkRepository, DocumentRepository
from catalog.store.session_context import current_session

__all__ = [
    "LinkResolutionTransform",
    "LinkResolutionStats",
]

from agentlayer.logging import logger

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


class FrontmatterTransform(TransformComponent):
    """Transform raw frontmatter into structured ontology metadata.

    For each node:

    1. Reads raw frontmatter from ``node.metadata[frontmatter_key]``.
    2. If a ``ontology_spec_cls`` is provided, validates through it and
       converts to :class:`DocumentMeta` via ``to_document_meta()``.
    3. Otherwise constructs a best-effort ``DocumentMeta`` from raw keys.
    4. Derives ``title`` (frontmatter -> aliases[0] -> note_name).
    5. Derives ``description`` (frontmatter -> summary key -> None).
    6. Writes ``title`` and ``description`` to ``node.metadata``.
    7. Promotes ``promote_keys`` fields to top-level ``node.metadata``
       so they are visible to embeddings and available as vector store
       filter keys.
    8. Writes ``_ontology_meta`` = ``DocumentMeta.to_dict()`` to ``node.metadata``.
    9. Removes the raw ``frontmatter`` key from ``node.metadata``.

    Attributes:
        ontology_spec_cls: Optional FrontmatterSchema-compatible class for typed validation.
        frontmatter_key: Metadata key where raw frontmatter lives.
        promote_keys: DocumentMeta field names to write as top-level
            node.metadata keys for downstream embedding/vector use.
            Defaults to ``["tags", "categories"]``. ``title`` and
            ``description`` are always promoted regardless of this setting.
            Set to ``[]`` to disable promotion beyond title/description.
        strict: If True, raise on validation errors instead of falling back.
    """

    ontology_spec_cls: type[FrontmatterSchema] | None = None
    frontmatter_key: str = "frontmatter"
    strict: bool = False

    # Valid promote targets (excludes title/description which are always
    # promoted, and extra which is a dict unsuitable for flat metadata).
    _PROMOTABLE_FIELDS: frozenset[str] = frozenset({"tags", "categories", "author"})

    def __init__(
        self,
        ontology_spec_cls: type[FrontmatterSchema] | None = None,
        *,
        frontmatter_key: str = "frontmatter",
        promote_keys: list[str] | None = None,
        strict: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.ontology_spec_cls = ontology_spec_cls
        self.frontmatter_key = frontmatter_key
        self.strict = strict

        if promote_keys is None:
            self._promote_keys = ["tags", "categories"]
        else:
            self._promote_keys = [
                k for k in promote_keys if k in self._PROMOTABLE_FIELDS
            ]

    def __call__(
        self,
        nodes: list[BaseNode],
        **kwargs: Any,
    ) -> list[BaseNode]:
        """Process nodes, converting frontmatter to ontology metadata."""
        enriched = 0
        for node in nodes:
            if not node.metadata:
                continue
            self._process_node(node)
            enriched += 1

        logger.info(f"FrontmatterTransform: processed {enriched}/{len(nodes)} nodes")
        return nodes

    def _process_node(self, node: BaseNode) -> None:
        """Process a single node."""
        meta = node.metadata
        fm = meta.get(self.frontmatter_key)
        if not isinstance(fm, dict):
            fm = {}

        # Build DocumentMeta from frontmatter.
        doc_meta = self._build_document_meta(fm)

        # Derive title: always use derivation logic (handles stripping/fallback).
        derived_title = self._derive_title(meta, fm)
        if derived_title:
            doc_meta.title = derived_title
        elif not doc_meta.title or not doc_meta.title.strip():
            doc_meta.title = ""

        # Derive description: always use derivation logic.
        derived_desc = self._derive_description(meta, fm)
        if derived_desc:
            doc_meta.description = derived_desc
        elif doc_meta.description and not doc_meta.description.strip():
            doc_meta.description = None

        # Write title and description to node metadata for PersistenceTransform.
        meta["title"] = doc_meta.title
        meta["description"] = doc_meta.description

        # Promote selected ontology fields to top-level metadata so they
        # are visible to embedding models and available as vector store
        # filter keys downstream.
        for key in self._promote_keys:
            value = getattr(doc_meta, key, None)
            if value is not None and value != [] and value != "":
                meta[key] = value

        # Write structured ontology metadata.
        meta["_ontology_meta"] = doc_meta.to_dict()

        # Remove raw frontmatter — it's been consumed.
        meta.pop(self.frontmatter_key, None)

    def _build_document_meta(self, fm: dict[str, Any]) -> DocumentMeta:
        """Build a DocumentMeta from frontmatter, optionally via FrontmatterSchema."""
        if self.ontology_spec_cls is not None:
            try:
                schema = self.ontology_spec_cls.from_frontmatter(fm)
                return schema.to_document_meta()
            except Exception:
                if self.strict:
                    raise
                logger.warning(
                    "VaultSchema validation failed, falling back to best-effort",
                    exc_info=True,
                )

        # Best-effort: pull known ontology keys directly from frontmatter.
        tags = _coerce_list(fm.get("tags"))
        categories = _coerce_list(fm.get("categories") or fm.get("type"))

        known_keys = {"title", "description", "tags", "categories", "type", "author"}
        extra = {k: v for k, v in fm.items() if k not in known_keys and v is not None}

        return DocumentMeta(
            title=fm.get("title") if isinstance(fm.get("title"), str) else None,
            description=fm.get("description") if isinstance(fm.get("description"), str) else None,
            tags=tags,
            categories=categories,
            author=fm.get("author") if isinstance(fm.get("author"), str) else None,
            extra=extra,
        )

    def _derive_title(self, meta: dict[str, Any], fm: dict[str, Any]) -> str:
        """Derive title from frontmatter or note_name.

        Priority:
        1. Explicit frontmatter ``title``
        2. First alias from frontmatter ``aliases``
        3. ``note_name`` from node metadata (filename stem)
        """
        # 1. Frontmatter title.
        fm_title = fm.get("title")
        if fm_title and isinstance(fm_title, str) and fm_title.strip():
            return fm_title.strip()

        # 2. First alias.
        aliases = fm.get("aliases")
        if isinstance(aliases, list) and aliases:
            first = aliases[0]
            if isinstance(first, str) and first.strip():
                return first.strip()

        # 3. note_name (filename stem from ObsidianVaultReader).
        note_name = meta.get("note_name")
        if note_name and isinstance(note_name, str):
            return note_name.strip()

        return ""

    def _derive_description(self, meta: dict[str, Any], fm: dict[str, Any]) -> str | None:
        """Derive description from frontmatter or upstream summary.

        Priority:
        1. Explicit frontmatter ``description``
        2. Upstream ``summary`` metadata key
        3. None
        """
        fm_desc = fm.get("description")
        if fm_desc and isinstance(fm_desc, str) and fm_desc.strip():
            return fm_desc.strip()

        summary = meta.get("summary")
        if summary and isinstance(summary, str) and summary.strip():
            return summary.strip()

        return None


def _coerce_list(value: Any) -> list[str]:
    """Coerce a value to a list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    return [str(value)]
