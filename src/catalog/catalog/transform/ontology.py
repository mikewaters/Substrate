"""catalog.transform.ontology - Ontology mapping transform.

Maps raw frontmatter (from source readers) into canonical ontology metadata
for persistence and indexing.
"""

from __future__ import annotations

from typing import Any

from agentlayer.logging import get_logger
from llama_index.core.schema import BaseNode, TransformComponent

from catalog.ontology import DocumentMeta, OntologyMappingSpec

logger = get_logger(__name__)


class OntologyMapper(TransformComponent):
    """Transform raw frontmatter into structured ontology metadata.

    For each node:

    1. Reads raw frontmatter from ``node.metadata[frontmatter_key]``.
    2. If an ``ontology_spec_cls`` is provided, validates through it and
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
        ontology_spec_cls: Optional OntologyMappingSpec-compatible class for typed validation.
        frontmatter_key: Metadata key where raw frontmatter lives.
        promote_keys: DocumentMeta field names to write as top-level
            node.metadata keys for downstream embedding/vector use.
            Defaults to ``["tags", "categories"]``. ``title`` and
            ``description`` are always promoted regardless of this setting.
            Set to ``[]`` to disable promotion beyond title/description.
        strict: If True, raise on validation errors instead of falling back.
    """

    ontology_spec_cls: type[OntologyMappingSpec] | None = None
    frontmatter_key: str = "frontmatter"
    strict: bool = False

    # Valid promote targets (excludes title/description which are always
    # promoted, and extra which is a dict unsuitable for flat metadata).
    _PROMOTABLE_FIELDS: frozenset[str] = frozenset({"tags", "categories", "author"})

    def __init__(
        self,
        ontology_spec_cls: type[OntologyMappingSpec] | None = None,
        *,
        frontmatter_key: str = "frontmatter",
        promote_keys: list[str] | None = None,
        strict: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize the ontology mapper.

        Args:
            ontology_spec_cls: Optional mapping spec class for typed validation.
            frontmatter_key: Metadata key where raw frontmatter lives.
            promote_keys: DocumentMeta field names to promote to top-level metadata.
            strict: If True, raise on validation errors.
            **kwargs: Additional args passed to TransformComponent.
        """
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

        logger.info(f"OntologyMapper: processed {enriched}/{len(nodes)} nodes")
        return nodes

    def _process_node(self, node: BaseNode) -> None:
        """Process a single node."""
        meta = node.metadata
        fm = meta.get(self.frontmatter_key)
        if not isinstance(fm, dict):
            fm = {}

        has_frontmatter = bool(fm)
        has_note_name = isinstance(meta.get("note_name"), str) and meta.get("note_name").strip()
        has_summary = isinstance(meta.get("summary"), str) and meta.get("summary").strip()
        has_title = isinstance(meta.get("title"), str) and meta.get("title").strip()
        has_description = isinstance(meta.get("description"), str) and meta.get("description").strip()
        if not any((has_frontmatter, has_note_name, has_summary, has_title, has_description)):
            return

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
        """Build a DocumentMeta from frontmatter, optionally via OntologyMappingSpec."""
        if self.ontology_spec_cls is not None:
            try:
                schema = self.ontology_spec_cls.from_frontmatter(fm)
                return schema.to_document_meta()
            except Exception:
                if self.strict:
                    raise
                logger.warning(
                    "Ontology spec validation failed, falling back to best-effort",
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
        3. Existing ``title`` in node metadata
        4. ``note_name`` from node metadata (filename stem)
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

        # 3. Existing metadata title.
        meta_title = meta.get("title")
        if meta_title and isinstance(meta_title, str) and meta_title.strip():
            return meta_title.strip()

        # 4. note_name (filename stem from ObsidianVaultReader).
        note_name = meta.get("note_name")
        if note_name and isinstance(note_name, str):
            return note_name.strip()

        return ""

    def _derive_description(self, meta: dict[str, Any], fm: dict[str, Any]) -> str | None:
        """Derive description from frontmatter or upstream summary.

        Priority:
        1. Explicit frontmatter ``description``
        2. Existing ``description`` in node metadata
        3. Upstream ``summary`` metadata key
        4. None
        """
        fm_desc = fm.get("description")
        if fm_desc and isinstance(fm_desc, str) and fm_desc.strip():
            return fm_desc.strip()

        meta_desc = meta.get("description")
        if meta_desc and isinstance(meta_desc, str) and meta_desc.strip():
            return meta_desc.strip()

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
