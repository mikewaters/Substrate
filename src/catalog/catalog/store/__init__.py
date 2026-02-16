"""catalog.store - Persistence layer.

SQLAlchemy-based storage with SQLite backend.
Exposes DatasetService for validated Pydantic model persistence.
All persistence including FTS and vector index wiring resides here.
"""

from catalog.store.cleanup import (
                                   IndexCleanup,
                                   cleanup_fts_for_document,
                                   cleanup_fts_for_inactive_documents,
                                   cleanup_stale_documents,
)
from catalog.store.database import (
                                   Base,
                                   CatalogBase,
                                   ContentBase,
                                   DatabaseRegistry,
                                   create_engine_for_path,
                                   get_engine,
                                   get_registry,
                                   get_session,
                                   get_session_factory,
)
from catalog.store.dataset import (
                                   DatasetExistsError,
                                   DatasetNotFoundError,
                                   DatasetService,
                                   DocumentNotFoundError,
                                   normalize_dataset_name,
)
from catalog.store.docstore import SQLiteDocumentStore
from catalog.store.fts import FTSManager, FTSResult, create_fts_table, drop_fts_table
from catalog.store.fts_chunk import (
                                   FTSChunkManager,
                                   FTSChunkResult,
                                   create_chunks_fts_table,
                                   drop_chunks_fts_table,
)
from catalog.store.llm_cache import LLMCache, LLMCacheEntry
from catalog.store.models import (
    Bookmark,
    BookmarkLink,
    BookmarkRelationKind,
    Catalog,
    CatalogEntry,
    CatalogEntryRelationKind,
    Collection,
    CollectionMember,
    Dataset,
    Document,
    DocumentKind,
    DocumentLink,
    DocumentLinkKind,
    Repository,
    RepositoryLink,
    Resource,
    ResourceKind,
)
from catalog.store.repositories import (
    BookmarkRepository,
    CatalogRepository,
    CollectionRepository,
    DatasetRepository,
    DocumentLinkRepository,
    DocumentRepository,
    RepoRepository,
)
from catalog.store.schemas import (
                                   DatasetCreate,
                                   DatasetInfo,
                                   DocumentCreate,
                                   DocumentInfo,
                                   DocumentUpdate,
)
from catalog.store.session_context import (
                                   SessionNotSetError,
                                   clear_session,
                                   current_session,
                                   session_or_new,
                                   use_session,
)
from catalog.store.vector import VectorStoreManager

__all__ = [
    # Database
    "Base",
    "CatalogBase",
    "ContentBase",
    "DatabaseRegistry",
    "create_engine_for_path",
    "get_engine",
    "get_registry",
    "get_session",
    "get_session_factory",
    # Models & Enums
    "Bookmark",
    "BookmarkLink",
    "BookmarkRelationKind",
    "Catalog",
    "CatalogEntry",
    "CatalogEntryRelationKind",
    "Collection",
    "CollectionMember",
    "Dataset",
    "Document",
    "DocumentKind",
    "DocumentLink",
    "DocumentLinkKind",
    "Repository",
    "RepositoryLink",
    "Resource",
    "ResourceKind",
    # Repositories
    "BookmarkRepository",
    "CatalogRepository",
    "CollectionRepository",
    "DatasetRepository",
    "DocumentLinkRepository",
    "DocumentRepository",
    "RepoRepository",
    # Schemas
    "DatasetCreate",
    "DatasetInfo",
    "DocumentCreate",
    "DocumentInfo",
    "DocumentUpdate",
    # Service
    "DatasetService",
    "DatasetExistsError",
    "DatasetNotFoundError",
    "DocumentNotFoundError",
    "normalize_dataset_name",
    # FTS (document-level)
    "FTSManager",
    "FTSResult",
    "create_fts_table",
    "drop_fts_table",
    # FTS (chunk-level)
    "FTSChunkManager",
    "FTSChunkResult",
    "create_chunks_fts_table",
    "drop_chunks_fts_table",
    # LLM Cache
    "LLMCache",
    "LLMCacheEntry",
    # Cleanup
    "IndexCleanup",
    "cleanup_fts_for_document",
    "cleanup_fts_for_inactive_documents",
    "cleanup_stale_documents",
    # LlamaIndex integration
    "SQLiteDocumentStore",
    "VectorStoreManager",
    # Session context
    "SessionNotSetError",
    "clear_session",
    "current_session",
    "session_or_new",
    "use_session",
]
