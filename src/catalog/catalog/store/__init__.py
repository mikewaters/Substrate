"""catalog.store - Persistence layer.

SQLAlchemy-based storage with SQLite backend.
Exposes DatasetService for validated Pydantic model persistence.
FTS, vector, and cleanup have moved to the `index` package.
"""

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
from agentlayer.llm_cache import LLMCache, LLMCacheEntry
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
from agentlayer.session import (
                                   SessionNotSetError,
                                   clear_session,
                                   current_session,
                                   register_session_factory,
                                   session_or_new,
                                   use_session,
)

# Register catalog's get_session as the session factory for agentlayer.session
register_session_factory(get_session)

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
    # LLM Cache
    "LLMCache",
    "LLMCacheEntry",
    # LlamaIndex integration
    "SQLiteDocumentStore",
    # Session context
    "SessionNotSetError",
    "clear_session",
    "current_session",
    "session_or_new",
    "use_session",
]
