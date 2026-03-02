"""catalog.transform.llama - LlamaIndex TransformComponent wrappers.

Provides LlamaIndex-compatible transform components that wrap idx functionality
for use in ingestion pipelines. Uses ambient session via contextvars.

Example usage:
    from llama_index.core.ingestion import IngestionPipeline
    from catalog.transform.llama import TextNormalizerTransform, PersistenceTransform
    from catalog.store import get_session, use_session

    with get_session() as session:
        with use_session(session):
            persist = PersistenceTransform(dataset_id=1)
            pipeline = IngestionPipeline(
                transformations=[TextNormalizerTransform(), persist]
            )
            nodes = pipeline.run(documents=documents)
            print(f"Created: {persist.stats.created}")
"""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from agentlayer.logging import get_logger
from llama_index.core.schema import BaseNode, TransformComponent
from sqlalchemy.orm import Session

from catalog.store.models import Document
from catalog.store.repositories import DocumentRepository
from agentlayer.session import session_or_new
from agentlayer.normalize import TextNormalizer

__all__ = [
    "TextNormalizerTransform",
    "PersistenceTransform",
    "PersistenceStats",
]

logger = get_logger(__name__)


class TextNormalizerTransform(TransformComponent):
    """LlamaIndex TransformComponent that normalizes text content of nodes.

    Wraps catalog.transform.normalize.TextNormalizer to integrate with
    LlamaIndex ingestion pipelines. Normalizes line endings, collapses
    excessive whitespace, strips BOM, and performs other text cleanup.

    Attributes:
        strip_bom: Remove UTF-8 BOM if present.
        normalize_line_endings: Convert \\r\\n and \\r to \\n.
        collapse_blank_lines: Limit consecutive blank lines.
        max_consecutive_blank_lines: Maximum blank lines to allow.
        strip_trailing_whitespace: Remove trailing whitespace from lines.
    """

    strip_bom: bool = True
    normalize_line_endings: bool = True
    collapse_blank_lines: bool = True
    max_consecutive_blank_lines: int = 2
    strip_trailing_whitespace: bool = True

    def __init__(
        self,
        *,
        strip_bom: bool = True,
        normalize_line_endings: bool = True,
        collapse_blank_lines: bool = True,
        max_consecutive_blank_lines: int = 2,
        strip_trailing_whitespace: bool = True,
        **kwargs: Any,
    ) -> None:
        """Initialize the text normalizer transform.

        Args:
            strip_bom: Remove UTF-8 BOM if present.
            normalize_line_endings: Convert \\r\\n and \\r to \\n.
            collapse_blank_lines: Limit consecutive blank lines.
            max_consecutive_blank_lines: Maximum blank lines to allow.
            strip_trailing_whitespace: Remove trailing whitespace from lines.
            **kwargs: Additional arguments passed to TransformComponent.
        """
        super().__init__(**kwargs)
        self.strip_bom = strip_bom
        self.normalize_line_endings = normalize_line_endings
        self.collapse_blank_lines = collapse_blank_lines
        self.max_consecutive_blank_lines = max_consecutive_blank_lines
        self.strip_trailing_whitespace = strip_trailing_whitespace

    def __call__(
        self,
        nodes: list[BaseNode],
        **kwargs: Any,
    ) -> list[BaseNode]:
        """Normalize the text content of each node.

        Creates a TextNormalizer with the configured options and applies
        it to each node's text content.

        Args:
            nodes: List of nodes to normalize.
            **kwargs: Additional arguments (unused).

        Returns:
            The same nodes with normalized text content.
        """
        normalizer = TextNormalizer(
            strip_bom=self.strip_bom,
            normalize_line_endings=self.normalize_line_endings,
            collapse_blank_lines=self.collapse_blank_lines,
            max_consecutive_blank_lines=self.max_consecutive_blank_lines,
            strip_trailing_whitespace=self.strip_trailing_whitespace,
        )

        for node in nodes:
            original_text = node.get_content()
            normalized_text = normalizer.normalize(original_text)
            # Use set_content() which works for both Document and TextNode
            node.set_content(normalized_text)

        return nodes


@dataclass
class PersistenceStats:
    """Statistics from a persistence operation.

    Attributes:
        created: Number of new documents created.
        updated: Number of existing documents updated.
        skipped: Number of unchanged documents skipped.
        failed: Number of documents that failed to process.
        errors: List of error messages for failed documents.
    """

    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def total_processed(self) -> int:
        """Total number of documents processed (excluding failures)."""
        return self.created + self.updated + self.skipped

    def reset(self) -> None:
        """Reset all statistics to zero."""
        self.created = 0
        self.updated = 0
        self.skipped = 0
        self.failed = 0
        self.errors = []


def _compute_content_hash(content: str, metadata_json: str | None = None) -> str:
    """Compute SHA256 hash of content and metadata."""
    data = content
    if metadata_json:
        data += metadata_json
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


class PersistenceTransform(TransformComponent):
    """LlamaIndex TransformComponent that persists nodes to the database.

    This transform handles database persistence within the pipeline:
    1. Check if document exists (by path from node metadata)
    2. Create new documents or update existing ones
    3. Track statistics

    Change detection is handled upstream by LlamaIndex's docstore mechanism
    (using SHA256 of text + metadata). Only new or changed documents reach
    this transform.

    The transform uses the ambient session from the current context (set via
    ``use_session()``). Statistics are available via the ``stats`` property.

    Example:
        with get_session() as session:
            with use_session(session):
                persist = PersistenceTransform(dataset_id=dataset_id)
                pipeline = IngestionPipeline(
                    transformations=[TextNormalizerTransform(), persist]
                )
                pipeline.run(documents=documents)
                print(f"Created {persist.stats.created} documents")

    Attributes:
        stats: PersistenceStats with counts of created/updated/failed.
    """

    # Private attributes (not Pydantic fields)
    _dataset_id: int = 0
    _dataset_name: str = ""
    _path_key: str = "relative_path"
    _stats: PersistenceStats | None = None

    def __init__(
        self,
        dataset_id: int,
        dataset_name: str = "",
        *,
        path_key: str = "relative_path",
        **kwargs: Any,
    ) -> None:
        """Initialize the persistence transform.

        Args:
            dataset_id: ID of the dataset to persist documents to.
            dataset_name: Normalized name of the dataset (used for URI generation).
            path_key: Metadata key for the document path (default: "relative_path").
            **kwargs: Additional arguments passed to TransformComponent.
        """
        super().__init__(**kwargs)
        self._dataset_id = dataset_id
        self._dataset_name = dataset_name
        self._path_key = path_key
        self._stats = PersistenceStats()

    @property
    def stats(self) -> PersistenceStats:
        """Get persistence statistics."""
        if self._stats is None:
            self._stats = PersistenceStats()
        return self._stats

    def __call__(
        self,
        nodes: list[BaseNode],
        **kwargs: Any,
    ) -> list[BaseNode]:
        """Persist each node to the database.

        For each node:
        - Extracts path from metadata
        - Computes content hash
        - Creates or updates the Document record
        - Tracks statistics

        Uses `session_or_new()`: the ambient session if set, otherwise a
        new session for this run (e.g. in worker processes or threads).

        Args:
            nodes: List of nodes to persist.
            **kwargs: Additional arguments (unused).

        Returns:
            All input nodes with doc_id added to metadata.

        Raises:
            SessionNotSetError: If no ambient session is set (only when
                session_or_new cannot create one).
        """
        with session_or_new() as session:
            logger.info(f"PersistenceTransform: persisting {len(nodes)} documents")

            # Reset stats for this run
            self.stats.reset()

            doc_repo = DocumentRepository()

            # Pre-fetch existing documents for efficiency
            existing_paths = doc_repo.list_paths_by_parent(
                self._dataset_id, active_only=False
            )
            existing_docs: dict[str, Document | None] = {
                path: doc_repo.get_by_path(self._dataset_id, path)
                for path in existing_paths
            }

            output_nodes: list[BaseNode] = []
            for node in nodes:
                try:
                    # Use a savepoint so a single node failure (e.g. URI
                    # collision) doesn't poison the entire session.
                    nested = session.begin_nested()
                    try:
                        changed = self._process_node(
                            session=session,
                            doc_repo=doc_repo,
                            node=node,
                            existing_docs=existing_docs,
                        )
                        nested.commit()
                        if changed:
                            output_nodes.append(node)
                    except Exception:
                        nested.rollback()
                        raise
                except Exception as e:
                    path = self._get_path(node)
                    logger.error(f"Failed to persist {path}: {e}")
                    self.stats.failed += 1
                    self.stats.errors.append(f"{path}: {e}")

            session.flush()

            logger.info(
                f"PersistenceTransform complete: "
                f"created={self.stats.created}, updated={self.stats.updated}, "
                f"failed={self.stats.failed}, "
                f"passing {len(output_nodes)}/{len(nodes)} nodes downstream"
            )

            return output_nodes

    def _get_path(self, node: BaseNode) -> str:
        """Extract document path from node metadata."""
        if node.metadata and self._path_key in node.metadata:
            return str(node.metadata[self._path_key])
        # Fall back to node_id (which we set to relative_path)
        return node.node_id

    def _get_metadata(self, node: BaseNode) -> dict[str, Any] | None:
        """Extract metadata payload.

        Prefers structured ontology metadata if present (written by
        OntologyMapper). Falls back to filtered raw metadata.
        """
        if not node.metadata:
            return None

        # Prefer structured ontology if OntologyMapper ran.
        ontology = node.metadata.get("_ontology_meta")
        if ontology is not None:
            return ontology

        # Fallback: original behavior.
        filtered = {
            k: v for k, v in node.metadata.items()
            if not k.startswith("_") and k not in ("file_path",)
        }
        return filtered if filtered else None

    def _process_node(
        self,
        session: Session,
        doc_repo: DocumentRepository,
        node: BaseNode,
        existing_docs: dict[str, Document | None],
    ) -> bool:
        """Process a single node for persistence.

        Every node that reaches this transform is new or changed (LlamaIndex
        docstore filters unchanged documents upstream). This method always
        creates or updates.

        Returns:
            True (all nodes pass downstream).
        """
        path = self._get_path(node)
        body = node.get_content()
        metadata_payload = self._get_metadata(node)
        metadata_json = json.dumps(metadata_payload) if metadata_payload else None
        content_hash = _compute_content_hash(body, metadata_json)

        # Extract source metadata for etag/last_modified
        etag = node.metadata.get("etag") if node.metadata else None
        last_modified_str = node.metadata.get("last_modified") if node.metadata else None
        last_modified = None
        if last_modified_str:
            from datetime import datetime
            try:
                last_modified = datetime.fromisoformat(last_modified_str)
            except (ValueError, TypeError):
                pass

        # Extract title, description, and resource-level fields from node metadata
        title = node.metadata.get("title") if node.metadata else None
        description = node.metadata.get("description") if node.metadata else None
        format_ = node.metadata.get("_format") if node.metadata else None
        media_type = node.metadata.get("_media_type") if node.metadata else None
        subject = node.metadata.get("_subject") if node.metadata else None

        existing = existing_docs.get(path)

        if existing is not None:
            # Update existing document
            existing.content_hash = content_hash
            existing.body = body
            existing.etag = etag
            existing.last_modified = last_modified
            existing.active = True
            existing.metadata_json = metadata_payload
            if title is not None:
                existing.title = title
            if description is not None:
                existing.description = description
            if format_ is not None:
                existing.format = format_
            if media_type is not None:
                existing.media_type = media_type
            if subject is not None:
                existing.subject = subject
            session.flush()

            node.metadata["doc_id"] = existing.id

            self.stats.updated += 1
            return True
        else:
            # New document - create
            doc = doc_repo.create(
                parent_id=self._dataset_id,
                path=path,
                content_hash=content_hash,
                body=body,
                title=title,
                description=description,
                format=format_,
                media_type=media_type,
                subject=subject,
                etag=etag,
                last_modified=last_modified,
                metadata_json=metadata_payload,
            )
            session.flush()

            node.metadata["doc_id"] = doc.id

            # Add to existing_docs cache for any future nodes with same path
            existing_docs[path] = doc

            self.stats.created += 1
            return True
