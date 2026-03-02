"""index.store - Index-specific persistence (FTS, vector, cleanup)."""

from index.store.fts import FTSManager, FTSResult, create_fts_table, drop_fts_table
from index.store.fts_chunk import (
    FTSChunkManager,
    FTSChunkResult,
    create_chunks_fts_table,
    drop_chunks_fts_table,
    extract_heading_body,
)
from index.store.vector import VectorStoreManager
from index.store.cleanup import (
    IndexCleanup,
    cleanup_fts_for_document,
    cleanup_fts_for_inactive_documents,
    cleanup_stale_documents,
)

__all__ = [
    "FTSManager",
    "FTSResult",
    "create_fts_table",
    "drop_fts_table",
    "FTSChunkManager",
    "FTSChunkResult",
    "create_chunks_fts_table",
    "drop_chunks_fts_table",
    "extract_heading_body",
    "VectorStoreManager",
    "IndexCleanup",
    "cleanup_fts_for_document",
    "cleanup_fts_for_inactive_documents",
    "cleanup_stale_documents",
]
