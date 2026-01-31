"""Repository for Catalog entities.

This module provides the repository layer for Catalog CRUD operations,
transforming between domain models (attrs) and ORM models (SQLAlchemy).
"""

from advanced_alchemy.repository import SQLAlchemyAsyncRepository

from ontology.relational.models import (
    Catalog,
    Purpose,
    Repository,
    Resource,
    Bookmark,
    Collection,
    Document,
    Note,
)

"""
Available Repository methods:
    add
    add_many
    delete
    delete_many
    delete_where
    exists
    get
    get_one
    get_one_or_none
    get_or_upsert
    get_and_update
    count
    update
    update_many
    list_and_count
    upsert
    upsert_many
    list
"""


class CatalogRepository(SQLAlchemyAsyncRepository[Catalog]):
    """Repository for Catalog entities.

    This repository handles CRUD operations for catalogs.
    """

    model_type = Catalog


class RepositoryRepository(SQLAlchemyAsyncRepository[Repository]):
    """Repository for Repository entities.

    This repository handles CRUD operations for repositories.
    """

    model_type = Repository


class PurposeRepository(SQLAlchemyAsyncRepository[Purpose]):
    """Repository for Purpose entities.

    This repository handles CRUD operations for purposes.
    """

    model_type = Purpose


class ResourceRepository(SQLAlchemyAsyncRepository[Resource]):
    """Repository for Resource entities.

    This repository handles CRUD operations for resources and all
    their subtypes (Bookmark, Collection, Document, Note).
    """

    model_type = Resource


class BookmarkRepository(SQLAlchemyAsyncRepository[Bookmark]):
    """Repository for Bookmark entities.

    This repository handles CRUD operations specifically for bookmarks.
    """

    model_type = Bookmark


class CollectionRepository(SQLAlchemyAsyncRepository[Collection]):
    """Repository for Collection entities.

    This repository handles CRUD operations specifically for collections.
    """

    model_type = Collection


class DocumentRepository(SQLAlchemyAsyncRepository[Document]):
    """Repository for Document entities.

    This repository handles CRUD operations specifically for documents.
    """

    model_type = Document


class NoteRepository(SQLAlchemyAsyncRepository[Note]):
    """Repository for Note entities.

    This repository handles CRUD operations specifically for notes.
    """

    model_type = Note
