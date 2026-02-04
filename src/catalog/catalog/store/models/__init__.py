"""catalog.store.models - SQLAlchemy ORM models for catalog and content databases.

Re-exports all models from catalog.py and content.py.
CatalogBase is aliased as Base for backward compatibility.
"""

from catalog.store.models.catalog import (
    Bookmark,
    BookmarkLink,
    BookmarkRelationKind,
    Catalog,
    CatalogBase,
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
from catalog.store.models.content import ContentBase

# Backward compatibility: Base is an alias for CatalogBase
Base = CatalogBase

__all__ = [
    # Bases
    "Base",  # Backward compat alias for CatalogBase
    "CatalogBase",
    "ContentBase",
    # Models & Enums from catalog.py
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
]
