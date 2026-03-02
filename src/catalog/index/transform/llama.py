"""index.transform.llama - LlamaIndex TransformComponent wrappers for indexing.

Provides LlamaIndex-compatible transform components for the index pipeline:
- DocumentFTSTransform: indexes nodes in FTS5
- ChunkPersistenceTransform: persists chunks to FTS with metadata assignment

Example usage:
    from index.transform.llama import DocumentFTSTransform, ChunkPersistenceTransform
"""

import hashlib
import uuid
from dataclasses import dataclass, field
from typing import Any

from agentlayer.logging import get_logger
from llama_index.core.schema import BaseNode, TransformComponent

from index.store.fts import FTSManager
from index.store.fts_chunk import FTSChunkManager, extract_heading_body
from agentlayer.session import session_or_new

__all__ = [
    "DocumentFTSTransform",
    "ChunkPersistenceTransform",
    "ChunkPersistenceStats",
]

logger = get_logger(__name__)


def _compute_content_hash(content: str, metadata_json: str | None = None) -> str:
    """Compute SHA256 hash of content and metadata."""
    data = content
    if metadata_json:
        data += metadata_json
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


class DocumentFTSTransform(TransformComponent):
    """LlamaIndex TransformComponent that indexes nodes in FTS5.

    Passthrough transform that updates the FTS5 full-text search index
    for each node, then returns the nodes unchanged. This allows FTS
    indexing to be integrated into LlamaIndex ingestion pipelines.

    Uses ambient session via contextvars. The session must be set
    via `use_session()` before calling the transform.

    Attributes:
        doc_id_key: Metadata key containing the document ID (default: "doc_id").
        path_key: Metadata key containing the document path (default: "path").
    """

    doc_id_key: str = "doc_id"
    path_key: str = "path"

    # These are not Pydantic fields - set in __init__
    _fts_manager: FTSManager | None = None

    def __init__(
        self,
        *,
        fts_manager: FTSManager | None = None,
        doc_id_key: str = "doc_id",
        path_key: str = "path",
        **kwargs: Any,
    ) -> None:
        """Initialize the FTS indexer transform.

        Can optionally provide a pre-configured FTSManager instance.
        If not provided, a new FTSManager will be created using the
        ambient session from current_session().

        Args:
            fts_manager: Optional pre-configured FTSManager instance.
            doc_id_key: Metadata key for document ID (used as FTS rowid).
            path_key: Metadata key for document path.
            **kwargs: Additional arguments passed to TransformComponent.
        """
        super().__init__(**kwargs)

        self._fts_manager = fts_manager
        self.doc_id_key = doc_id_key
        self.path_key = path_key

    def _get_fts_manager(self) -> FTSManager:
        """Get the FTSManager instance to use.

        Returns:
            FTSManager instance. Uses explicit instance if provided,
            otherwise creates one using ambient session.
        """
        if self._fts_manager is not None:
            return self._fts_manager

        # Create using ambient session
        return FTSManager()

    def _get_doc_id(self, node: BaseNode) -> int | None:
        """Extract document ID from node metadata or ref_doc_id.

        Checks metadata first using doc_id_key, then falls back to
        ref_doc_id if available.

        Args:
            node: The node to extract doc_id from.

        Returns:
            Document ID as integer, or None if not found.
        """
        # Check metadata first
        if node.metadata and self.doc_id_key in node.metadata:
            doc_id = node.metadata[self.doc_id_key]
            if isinstance(doc_id, int):
                return doc_id
            # Try to convert string to int
            try:
                return int(doc_id)
            except (ValueError, TypeError):
                pass

        # Fall back to ref_doc_id
        if hasattr(node, "ref_doc_id") and node.ref_doc_id is not None:
            try:
                return int(node.ref_doc_id)
            except (ValueError, TypeError):
                pass

        return None

    def _get_path(self, node: BaseNode) -> str:
        """Extract document path from node metadata.

        Args:
            node: The node to extract path from.

        Returns:
            Document path, or empty string if not found.
        """
        if node.metadata and self.path_key in node.metadata:
            return str(node.metadata[self.path_key])
        return ""

    def __call__(
        self,
        nodes: list[BaseNode],
        **kwargs: Any,
    ) -> list[BaseNode]:
        """Index each node in the FTS5 index.

        For each node, extracts doc_id and path from metadata and
        calls FTSManager.upsert() to update the FTS index. Nodes
        without valid doc_id are skipped.

        Args:
            nodes: List of nodes to index.
            **kwargs: Additional arguments (unused).

        Returns:
            The same nodes unchanged (passthrough).
        """
        fts_manager = self._get_fts_manager()

        for node in nodes:
            doc_id = self._get_doc_id(node)
            if doc_id is None:
                # Skip nodes without valid doc_id

                continue

            path = self._get_path(node)
            body = node.text if hasattr(node, "text") else node.get_content()

            fts_manager.upsert(doc_id=doc_id, path=path, body=body)

        return nodes


@dataclass
class ChunkPersistenceStats:
    """Statistics from a chunk persistence operation.

    Attributes:
        created: Number of new chunks created in FTS index.
        updated: Number of existing chunks updated.
        skipped: Number of unchanged chunks skipped (currently unused).
        failed: Number of chunks that failed to process.
        errors: List of error messages for failed chunks.
    """

    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def total_processed(self) -> int:
        """Total number of chunks processed (excluding failures)."""
        return self.created + self.updated + self.skipped

    def reset(self) -> None:
        """Reset all statistics to zero."""
        self.created = 0
        self.updated = 0
        self.skipped = 0
        self.failed = 0
        self.errors = []


class ChunkPersistenceTransform(TransformComponent):
    """LlamaIndex TransformComponent that persists chunks to the FTS index.

    This transform handles chunk persistence after MarkdownNodeParser:
    1. Assigns stable node IDs in format `{content_hash}:{chunk_seq}`
    2. Sets metadata fields (source_doc_id, doc_id, chunk_seq, chunk_pos)
    3. Upserts chunks to FTSChunkManager (chunks_fts table)
    4. Tracks statistics (created, updated, skipped, failed)

    The transform uses the ambient session from the current context (set via
    `use_session()`). Statistics are available via the `stats` property.

    Attributes:
        stats: ChunkPersistenceStats with counts of created/updated/skipped/failed.
    """

    # Private attributes (not Pydantic fields)
    _dataset_name: str = ""
    _path_key: str = "relative_path"
    _doc_id_key: str = "doc_id"
    _content_hash_key: str = "content_hash"
    _stats: ChunkPersistenceStats | None = None

    def __init__(
        self,
        dataset_name: str,
        *,
        path_key: str = "relative_path",
        doc_id_key: str = "doc_id",
        content_hash_key: str = "content_hash",
        **kwargs: Any,
    ) -> None:
        """Initialize the chunk persistence transform.

        Args:
            dataset_name: Name of the dataset (e.g., "obsidian").
            path_key: Metadata key for the document path (default: "relative_path").
            doc_id_key: Metadata key for the document ID (default: "doc_id").
            content_hash_key: Metadata key for content hash (default: "content_hash").
            **kwargs: Additional arguments passed to TransformComponent.
        """
        super().__init__(**kwargs)
        self._dataset_name = dataset_name
        self._path_key = path_key
        self._doc_id_key = doc_id_key
        self._content_hash_key = content_hash_key
        self._stats = ChunkPersistenceStats()

    @property
    def stats(self) -> ChunkPersistenceStats:
        """Get chunk persistence statistics."""
        if self._stats is None:
            self._stats = ChunkPersistenceStats()
        return self._stats

    def __call__(
        self,
        nodes: list[BaseNode],
        **kwargs: Any,
    ) -> list[BaseNode]:
        """Persist each chunk to the FTS index.

        For each node:
        - Assigns stable node ID as `{content_hash}:{chunk_seq}`
        - Sets metadata fields (source_doc_id, doc_id, chunk_seq, chunk_pos)
        - Upserts to FTSChunkManager
        - Tracks statistics

        Uses `session_or_new()`: the ambient session if set, otherwise a
        new session for this run (e.g. in worker processes or threads).

        Args:
            nodes: List of TextNodes to persist (typically from MarkdownNodeParser).
            **kwargs: Additional arguments (unused).

        Returns:
            The same nodes with assigned IDs and metadata (pass-through).

        Raises:
            SessionNotSetError: If no ambient session is set and
                session_or_new cannot create one.
        """
        with session_or_new():
            logger.info(f"ChunkPersistenceTransform: persisting {len(nodes)} chunks")

            # Reset stats for this run
            self.stats.reset()

            fts_chunk = FTSChunkManager()

            # Group nodes by source document to assign chunk sequences
            doc_chunks: dict[str, list[BaseNode]] = {}
            for node in nodes:
                # Get source document identifier
                ref_doc_id = getattr(node, "ref_doc_id", None) or node.node_id
                source_key = self._get_source_key(node, ref_doc_id)
                if source_key not in doc_chunks:
                    doc_chunks[source_key] = []
                doc_chunks[source_key].append(node)

            # Process nodes grouped by document
            for source_key, chunk_nodes in doc_chunks.items():
                for chunk_seq, node in enumerate(chunk_nodes):
                    try:
                        self._process_chunk(
                            fts_chunk=fts_chunk,
                            node=node,
                            chunk_seq=chunk_seq,
                        )
                    except Exception as e:
                        node_id = getattr(node, "node_id", "unknown")
                        logger.error(f"Failed to persist chunk {node_id}: {e}")
                        self.stats.failed += 1
                        self.stats.errors.append(f"{node_id}: {e}")

            logger.info(
                f"ChunkPersistenceTransform complete: "
                f"created={self.stats.created}, failed={self.stats.failed}"
            )

            return nodes

    def _get_source_key(self, node: BaseNode, ref_doc_id: str) -> str:
        """Get a key to group chunks by source document.

        Args:
            node: The chunk node.
            ref_doc_id: Reference document ID from the node.

        Returns:
            Grouping key (path or ref_doc_id).
        """
        path = self._get_path(node)
        return path if path else ref_doc_id

    def _get_content_hash(self, node: BaseNode) -> str:
        """Get content hash from node metadata or compute it.

        Args:
            node: The chunk node.

        Returns:
            Content hash string.
        """
        # First check metadata for existing hash
        if node.metadata and self._content_hash_key in node.metadata:
            return str(node.metadata[self._content_hash_key])

        # Compute from source document content if available
        # Fall back to computing from node's own text
        text = node.get_content()
        return _compute_content_hash(text)

    def _get_path(self, node: BaseNode) -> str:
        """Extract document path from node metadata.

        Tries multiple keys in order of preference:
        1. relative_path (default key)
        2. file_name (Obsidian reader)
        3. note_name + .md extension (Obsidian reader)

        Args:
            node: The chunk node.

        Returns:
            Document path string.
        """
        if not node.metadata:
            return ""

        # Try the configured path key first (default: relative_path)
        if self._path_key in node.metadata:
            return str(node.metadata[self._path_key])

        # Fallback to file_name (used by Obsidian reader)
        if "file_name" in node.metadata:
            return str(node.metadata["file_name"])

        # Fallback to note_name + .md extension
        if "note_name" in node.metadata:
            return f"{node.metadata['note_name']}.md"

        return ""

    def _get_doc_id(self, node: BaseNode) -> int | None:
        """Extract document ID from node metadata.

        Args:
            node: The chunk node.

        Returns:
            Document ID as integer, or None if not available.
        """
        if node.metadata and self._doc_id_key in node.metadata:
            doc_id = node.metadata[self._doc_id_key]
            if isinstance(doc_id, int):
                return doc_id
            try:
                return int(doc_id)
            except (ValueError, TypeError):
                pass
        return None

    def _process_chunk(
        self,
        fts_chunk: FTSChunkManager,
        node: BaseNode,
        chunk_seq: int,
    ) -> None:
        """Process a single chunk for persistence.

        Args:
            fts_chunk: FTSChunkManager instance.
            node: The chunk node.
            chunk_seq: 0-indexed chunk sequence within the document.
        """
        # Get content hash for stable ID
        content_hash = self._get_content_hash(node)
        path = self._get_path(node)
        doc_id = self._get_doc_id(node)

        # Build source_doc_id in format {dataset_name}:{path}
        source_doc_id = f"{self._dataset_name}:{path}"

        # Generate a deterministic UUID from content_hash and chunk_seq
        # This is required because Qdrant only accepts UUID-formatted point IDs
        # Using UUID5 ensures the same content always produces the same UUID
        id_input = f"{content_hash}:{chunk_seq}"
        node_id = str(uuid.uuid5(uuid.NAMESPACE_OID, id_input))
        node.id_ = node_id

        # Set metadata fields
        node.metadata["source_doc_id"] = source_doc_id
        node.metadata["dataset_name"] = self._dataset_name
        node.metadata["chunk_seq"] = chunk_seq
        if doc_id is not None:
            node.metadata["doc_id"] = doc_id

        # Try to get character offset if available (from parser)
        if "start_char_idx" in node.metadata:
            node.metadata["chunk_pos"] = node.metadata["start_char_idx"]
        elif hasattr(node, "start_char_idx") and node.start_char_idx is not None:
            node.metadata["chunk_pos"] = node.start_char_idx

        # Get chunk text
        text = node.get_content()

        # Split heading lines from body for heading-bias mitigation.
        # Body text goes to embeddings; full text still goes to FTS upsert
        # which runs its own extract_heading_body internally.
        heading_text, body_text = extract_heading_body(text)
        node.metadata["heading_text"] = heading_text
        node.metadata["body_text"] = body_text
        # Use body-only text for embeddings to reduce heading bias.
        # If body is empty (heading-only chunk), fall back to heading.
        node.set_content(body_text if body_text.strip() else heading_text)

        # Check if chunk already exists by searching for existing node_id
        # For FTS5, we use upsert which handles both insert and update
        # Since upsert does DELETE then INSERT, we count all as "updated"
        # unless we can detect it's truly new

        # Upsert to FTS
        fts_chunk.upsert(node_id=node_id, text=text, source_doc_id=source_doc_id)

        # Count as created (we can't easily distinguish update vs create with FTS5)
        # A more sophisticated implementation could query first to check existence
        self.stats.created += 1

        #logger.debug(
        #    f"Persisted chunk {node_id} (seq={chunk_seq}) from {source_doc_id}"
        #)
