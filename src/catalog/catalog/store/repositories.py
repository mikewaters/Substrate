"""catalog.store.repositories - Repository classes for data access.

Repositories abstract database access patterns for all Resource models.
Supports both explicit session injection and ambient session via contextvars.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

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
)
from catalog.store.session_context import current_session

__all__ = [
    "BookmarkRepository",
    "CatalogRepository",
    "CollectionRepository",
    "DatasetRepository",
    "DocumentLinkRepository",
    "DocumentRepository",
    "RepoRepository",
]


class _BaseRepository:
    """Shared session-management mixin for all repositories."""

    def __init__(self, session: Session | None = None) -> None:
        """Initialize with a database session.

        Args:
            session: SQLAlchemy session instance. If None, uses the
                ambient session from current_session().
        """
        self._explicit_session = session

    @property
    def _session(self) -> Session:
        """Get the session to use for database operations."""
        if self._explicit_session is not None:
            return self._explicit_session
        return current_session()


class DatasetRepository(_BaseRepository):
    """Repository for Dataset model operations."""

    def create(
        self,
        name: str,
        uri: str,
        source_type: str,
        source_path: str,
        *,
        title: str | None = None,
        description: str | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> Dataset:
        """Create a new dataset.

        Args:
            name: Unique name identifier.
            uri: Full URI for the dataset.
            source_type: Type of source.
            source_path: Filesystem path to the source.
            title: Optional human-readable title.
            description: Optional description.
            metadata_json: Optional metadata payload.

        Returns:
            The created Dataset instance.
        """
        dataset = Dataset(
            name=name,
            uri=uri,
            source_type=source_type,
            source_path=source_path,
            title=title,
            description=description,
            metadata_json=metadata_json,
        )
        self._session.add(dataset)
        return dataset

    def get_by_id(self, dataset_id: int) -> Dataset | None:
        """Get a dataset by ID.

        Args:
            dataset_id: The dataset's primary key.

        Returns:
            The Dataset if found, None otherwise.
        """
        return self._session.get(Dataset, dataset_id)

    def get_by_name(self, name: str) -> Dataset | None:
        """Get a dataset by name.

        Args:
            name: The dataset's unique name.

        Returns:
            The Dataset if found, None otherwise.
        """
        stmt = select(Dataset).where(Dataset.name == name)
        return self._session.execute(stmt).scalar_one_or_none()

    def get_by_uri(self, uri: str) -> Resource | None:
        """Get a resource by URI.

        Args:
            uri: The resource's URI.

        Returns:
            The Resource if found, None otherwise.
        """
        stmt = select(Resource).where(Resource.uri == uri)
        return self._session.execute(stmt).scalar_one_or_none()

    def list_all(self) -> list[Dataset]:
        """List all datasets.

        Returns:
            List of all Dataset instances.
        """
        stmt = select(Dataset).order_by(Dataset.name)
        return list(self._session.execute(stmt).scalars().all())

    def delete(self, dataset: Dataset) -> None:
        """Delete a dataset.

        Args:
            dataset: The dataset to delete.
        """
        self._session.delete(dataset)

    def exists_by_name(self, name: str) -> bool:
        """Check if a dataset exists with the given name.

        Args:
            name: The dataset name to check.

        Returns:
            True if a dataset with this name exists.
        """
        stmt = select(func.count()).select_from(Dataset).where(Dataset.name == name)
        count = self._session.execute(stmt).scalar()
        return count is not None and count > 0


class DocumentRepository(_BaseRepository):
    """Repository for Document model operations."""

    def create(
        self,
        parent_id: int,
        uri: str,
        path: str,
        content_hash: str,
        body: str,
        *,
        title: str | None = None,
        description: str | None = None,
        doc_type: DocumentKind = DocumentKind.OTHER,
        etag: str | None = None,
        last_modified: datetime | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> Document:
        """Create a new document.

        Args:
            parent_id: Parent resource ID.
            uri: Unique URI for the document.
            path: Relative path within the parent.
            content_hash: SHA256 hash of content.
            body: Full normalized text content.
            title: Optional human-readable title.
            description: Optional description.
            doc_type: Document type classification.
            etag: Optional source etag.
            last_modified: Optional source modification time.
            metadata_json: Optional metadata payload.

        Returns:
            The created Document instance.
        """
        doc = Document(
            parent_id=parent_id,
            uri=uri,
            path=path,
            content_hash=content_hash,
            body=body,
            title=title,
            description=description,
            doc_type=doc_type,
            etag=etag,
            last_modified=last_modified,
            metadata_json=metadata_json,
        )
        self._session.add(doc)
        return doc

    def get_by_id(self, doc_id: int) -> Document | None:
        """Get a document by ID.

        Args:
            doc_id: The document's primary key.

        Returns:
            The Document if found, None otherwise.
        """
        return self._session.get(Document, doc_id)

    def get_by_path(self, parent_id: int, path: str) -> Document | None:
        """Get a document by parent and path.

        Args:
            parent_id: The parent resource's ID.
            path: The document's path within the parent.

        Returns:
            The Document if found, None otherwise.
        """
        stmt = select(Document).where(
            Document.parent_id == parent_id,
            Document.path == path,
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def list_by_parent(
        self,
        parent_id: int,
        *,
        active_only: bool = False,
    ) -> list[Document]:
        """List documents under a parent resource.

        Args:
            parent_id: The parent resource's ID.
            active_only: If True, only return active documents.

        Returns:
            List of Document instances.
        """
        stmt = select(Document).where(Document.parent_id == parent_id)
        if active_only:
            stmt = stmt.where(Document.active == True)  # noqa: E712
        stmt = stmt.order_by(Document.path)
        return list(self._session.execute(stmt).scalars().all())

    def list_paths_by_parent(
        self,
        parent_id: int,
        *,
        active_only: bool = False,
    ) -> set[str]:
        """List document paths under a parent resource.

        Args:
            parent_id: The parent resource's ID.
            active_only: If True, only return active documents.

        Returns:
            Set of document paths.
        """
        stmt = select(Document.path).where(Document.parent_id == parent_id)
        if active_only:
            stmt = stmt.where(Document.active == True)  # noqa: E712
        return set(self._session.execute(stmt).scalars().all())

    def update(
        self,
        doc: Document,
        *,
        title: str | None = None,
        description: str | None = None,
        content_hash: str | None = None,
        body: str | None = None,
        etag: str | None = None,
        last_modified: datetime | None = None,
        metadata_json: dict[str, Any] | None = None,
        active: bool | None = None,
    ) -> Document:
        """Update a document.

        Args:
            doc: The document to update.
            title: New title if changed.
            description: New description if changed.
            content_hash: New content hash if changed.
            body: New text content if changed.
            etag: New etag if changed.
            last_modified: New modification time if changed.
            metadata_json: New metadata payload if changed.
            active: New active status if changed.

        Returns:
            The updated Document instance.
        """
        if title is not None:
            doc.title = title
        if description is not None:
            doc.description = description
        if content_hash is not None:
            doc.content_hash = content_hash
        if body is not None:
            doc.body = body
        if etag is not None:
            doc.etag = etag
        if last_modified is not None:
            doc.last_modified = last_modified
        if metadata_json is not None:
            doc.metadata_json = metadata_json
        if active is not None:
            doc.active = active
        return doc

    def soft_delete(self, doc: Document) -> Document:
        """Soft-delete a document by setting active=False.

        Args:
            doc: The document to soft-delete.

        Returns:
            The updated Document instance.
        """
        doc.active = False
        return doc

    def soft_delete_by_paths(
        self,
        parent_id: int,
        paths: set[str],
    ) -> int:
        """Soft-delete multiple documents by path.

        Args:
            parent_id: The parent resource's ID.
            paths: Set of paths to soft-delete.

        Returns:
            Number of documents soft-deleted.
        """
        if not paths:
            return 0

        stmt = select(Document).where(
            Document.parent_id == parent_id,
            Document.path.in_(paths),
            Document.active == True,  # noqa: E712
        )
        docs = self._session.execute(stmt).scalars().all()
        for doc in docs:
            doc.active = False
        return len(docs)

    def deactivate_missing(
        self,
        parent_id: int,
        active_paths: set[str],
    ) -> int:
        """Deactivate documents whose paths are not in the given set.

        Used for deletion sync: after ingestion, any document not present
        in the current batch is marked inactive.

        Args:
            parent_id: The parent resource's ID.
            active_paths: Set of paths that should remain active.

        Returns:
            Number of documents deactivated.
        """
        if not active_paths:
            # No active paths means deactivate everything
            stmt = (
                select(Document)
                .where(
                    Document.parent_id == parent_id,
                    Document.active == True,  # noqa: E712
                )
            )
        else:
            stmt = (
                select(Document)
                .where(
                    Document.parent_id == parent_id,
                    Document.active == True,  # noqa: E712
                    Document.path.notin_(active_paths),
                )
            )
        docs = list(self._session.execute(stmt).scalars().all())
        for doc in docs:
            doc.active = False
        return len(docs)

    def hard_delete_by_paths(
        self,
        parent_id: int,
        paths: set[str],
    ) -> int:
        """Hard-delete multiple documents by path.

        Args:
            parent_id: The parent resource's ID.
            paths: Set of paths to delete.

        Returns:
            Number of documents deleted.
        """
        if not paths:
            return 0

        stmt = select(Document).where(
            Document.parent_id == parent_id,
            Document.path.in_(paths),
        )
        docs = list(self._session.execute(stmt).scalars().all())
        for doc in docs:
            self._session.delete(doc)
        return len(docs)

    def delete(self, doc: Document) -> None:
        """Hard-delete a document.

        Args:
            doc: The document to delete.
        """
        self._session.delete(doc)

    def count_by_parent(
        self,
        parent_id: int,
        *,
        active_only: bool = False,
    ) -> int:
        """Count documents under a parent resource.

        Args:
            parent_id: The parent resource's ID.
            active_only: If True, only count active documents.

        Returns:
            Number of documents.
        """
        stmt = select(func.count()).select_from(Document).where(
            Document.parent_id == parent_id
        )
        if active_only:
            stmt = stmt.where(Document.active == True)  # noqa: E712
        count = self._session.execute(stmt).scalar()
        return count or 0


class DocumentLinkRepository(_BaseRepository):
    """Repository for DocumentLink model operations."""

    def create(
        self,
        source_id: int,
        target_id: int,
        relation: DocumentLinkKind,
    ) -> DocumentLink:
        """Create a new document link.

        Args:
            source_id: Source document ID.
            target_id: Target document ID.
            relation: The link type.

        Returns:
            The created DocumentLink instance.
        """
        link = DocumentLink(
            source_id=source_id,
            target_id=target_id,
            relation=relation,
        )
        self._session.add(link)
        return link

    def upsert(
        self,
        source_id: int,
        target_id: int,
        relation: DocumentLinkKind,
    ) -> DocumentLink:
        """Create or update a document link.

        Args:
            source_id: Source document ID.
            target_id: Target document ID.
            relation: The link type.

        Returns:
            The DocumentLink instance (existing or new).
        """
        existing = self.get(source_id, target_id)
        if existing is not None:
            existing.relation = relation
            return existing
        return self.create(source_id, target_id, relation)

    def get(self, source_id: int, target_id: int) -> DocumentLink | None:
        """Get a document link by source and target.

        Args:
            source_id: Source document ID.
            target_id: Target document ID.

        Returns:
            The DocumentLink if found, None otherwise.
        """
        return self._session.get(DocumentLink, (source_id, target_id))

    def list_outgoing(self, source_id: int) -> list[DocumentLink]:
        """List all outgoing links from a document.

        Args:
            source_id: Source document ID.

        Returns:
            List of DocumentLink instances.
        """
        stmt = select(DocumentLink).where(DocumentLink.source_id == source_id)
        return list(self._session.execute(stmt).scalars().all())

    def list_incoming(self, target_id: int) -> list[DocumentLink]:
        """List all incoming links to a document (backlinks).

        Args:
            target_id: Target document ID.

        Returns:
            List of DocumentLink instances.
        """
        stmt = select(DocumentLink).where(DocumentLink.target_id == target_id)
        return list(self._session.execute(stmt).scalars().all())

    def delete_outgoing(self, source_id: int) -> int:
        """Delete all outgoing links from a document.

        Args:
            source_id: Source document ID.

        Returns:
            Number of links deleted.
        """
        stmt = select(DocumentLink).where(DocumentLink.source_id == source_id)
        links = list(self._session.execute(stmt).scalars().all())
        for link in links:
            self._session.delete(link)
        return len(links)

    def delete_by_parent(self, parent_id: int) -> int:
        """Delete all links where source or target belongs to a parent resource.

        Args:
            parent_id: Parent resource ID (e.g. dataset ID).

        Returns:
            Number of links deleted.
        """
        # Get all document IDs under this parent
        doc_ids_stmt = select(Document.id).where(Document.parent_id == parent_id)
        doc_ids = set(self._session.execute(doc_ids_stmt).scalars().all())
        if not doc_ids:
            return 0

        stmt = select(DocumentLink).where(
            (DocumentLink.source_id.in_(doc_ids))
            | (DocumentLink.target_id.in_(doc_ids))
        )
        links = list(self._session.execute(stmt).scalars().all())
        for link in links:
            self._session.delete(link)
        return len(links)


class CatalogRepository(_BaseRepository):
    """Repository for Catalog model operations."""

    def create(
        self,
        uri: str,
        *,
        title: str | None = None,
        description: str | None = None,
        homepage: str | None = None,
    ) -> Catalog:
        """Create a new catalog.

        Args:
            uri: Unique URI for the catalog.
            title: Optional title.
            description: Optional description.
            homepage: Optional homepage URL.

        Returns:
            The created Catalog instance.
        """
        cat = Catalog(
            uri=uri,
            title=title,
            description=description,
            homepage=homepage,
        )
        self._session.add(cat)
        return cat

    def get_by_id(self, catalog_id: int) -> Catalog | None:
        """Get a catalog by ID."""
        return self._session.get(Catalog, catalog_id)

    def get_by_uri(self, uri: str) -> Catalog | None:
        """Get a catalog by URI.

        Args:
            uri: The catalog's unique URI.

        Returns:
            The Catalog if found, None otherwise.
        """
        stmt = select(Catalog).where(Catalog.uri == uri)
        return self._session.execute(stmt).scalar_one_or_none()

    def get_or_create(
        self,
        uri: str,
        *,
        title: str | None = None,
        description: str | None = None,
        homepage: str | None = None,
    ) -> tuple[Catalog, bool]:
        """Get an existing catalog or create a new one.

        Args:
            uri: Unique URI for the catalog.
            title: Optional title (used only on create).
            description: Optional description (used only on create).
            homepage: Optional homepage URL (used only on create).

        Returns:
            Tuple of (Catalog instance, created flag).
        """
        existing = self.get_by_uri(uri)
        if existing is not None:
            return existing, False
        return self.create(uri, title=title, description=description, homepage=homepage), True

    def entry_exists(self, catalog_id: int, resource_id: int) -> bool:
        """Check if a catalog entry exists.

        Args:
            catalog_id: The catalog's ID.
            resource_id: The resource's ID.

        Returns:
            True if entry exists.
        """
        stmt = select(func.count()).select_from(CatalogEntry).where(
            CatalogEntry.catalog_id == catalog_id,
            CatalogEntry.resource_id == resource_id,
        )
        count = self._session.execute(stmt).scalar()
        return count is not None and count > 0

    def list_all(self) -> list[Catalog]:
        """List all catalogs."""
        stmt = select(Catalog).order_by(Catalog.uri)
        return list(self._session.execute(stmt).scalars().all())

    def delete(self, catalog: Catalog) -> None:
        """Delete a catalog and all its entries."""
        self._session.delete(catalog)

    def add_entry(
        self,
        catalog_id: int,
        resource_id: int,
        relation: CatalogEntryRelationKind,
        *,
        created_by: str | None = None,
    ) -> CatalogEntry:
        """Add a resource entry to a catalog.

        Args:
            catalog_id: The catalog's ID.
            resource_id: The resource's ID.
            relation: The relationship type.
            created_by: Optional author.

        Returns:
            The created CatalogEntry instance.
        """
        entry = CatalogEntry(
            catalog_id=catalog_id,
            resource_id=resource_id,
            relation=relation,
            created_by=created_by,
        )
        self._session.add(entry)
        return entry

    def remove_entry(self, catalog_id: int, resource_id: int) -> bool:
        """Remove an entry from a catalog.

        Args:
            catalog_id: The catalog's ID.
            resource_id: The resource's ID.

        Returns:
            True if entry was found and removed, False otherwise.
        """
        stmt = select(CatalogEntry).where(
            CatalogEntry.catalog_id == catalog_id,
            CatalogEntry.resource_id == resource_id,
        )
        entry = self._session.execute(stmt).scalar_one_or_none()
        if entry is None:
            return False
        self._session.delete(entry)
        return True

    def list_entries(self, catalog_id: int) -> list[CatalogEntry]:
        """List all entries in a catalog.

        Args:
            catalog_id: The catalog's ID.

        Returns:
            List of CatalogEntry instances.
        """
        stmt = select(CatalogEntry).where(
            CatalogEntry.catalog_id == catalog_id
        )
        return list(self._session.execute(stmt).scalars().all())


class CollectionRepository(_BaseRepository):
    """Repository for Collection model operations."""

    def create(
        self,
        uri: str,
        *,
        title: str | None = None,
        description: str | None = None,
    ) -> Collection:
        """Create a new collection.

        Args:
            uri: Unique URI for the collection.
            title: Optional title.
            description: Optional description.

        Returns:
            The created Collection instance.
        """
        coll = Collection(uri=uri, title=title, description=description)
        self._session.add(coll)
        return coll

    def get_by_id(self, collection_id: int) -> Collection | None:
        """Get a collection by ID."""
        return self._session.get(Collection, collection_id)

    def list_all(self) -> list[Collection]:
        """List all collections."""
        stmt = select(Collection).order_by(Collection.uri)
        return list(self._session.execute(stmt).scalars().all())

    def delete(self, collection: Collection) -> None:
        """Delete a collection and all its member associations."""
        self._session.delete(collection)

    def add_member(self, collection_id: int, resource_id: int) -> CollectionMember:
        """Add a resource to a collection.

        Args:
            collection_id: The collection's ID.
            resource_id: The resource's ID.

        Returns:
            The created CollectionMember instance.
        """
        member = CollectionMember(
            collection_id=collection_id,
            resource_id=resource_id,
        )
        self._session.add(member)
        return member

    def remove_member(self, collection_id: int, resource_id: int) -> bool:
        """Remove a resource from a collection.

        Args:
            collection_id: The collection's ID.
            resource_id: The resource's ID.

        Returns:
            True if member was found and removed, False otherwise.
        """
        stmt = select(CollectionMember).where(
            CollectionMember.collection_id == collection_id,
            CollectionMember.resource_id == resource_id,
        )
        member = self._session.execute(stmt).scalar_one_or_none()
        if member is None:
            return False
        self._session.delete(member)
        return True

    def list_members(self, collection_id: int) -> list[CollectionMember]:
        """List all members in a collection.

        Args:
            collection_id: The collection's ID.

        Returns:
            List of CollectionMember instances.
        """
        stmt = select(CollectionMember).where(
            CollectionMember.collection_id == collection_id
        )
        return list(self._session.execute(stmt).scalars().all())


class BookmarkRepository(_BaseRepository):
    """Repository for Bookmark model operations."""

    def create(
        self,
        uri: str,
        url: str,
        owner: str,
        *,
        title: str | None = None,
        description: str | None = None,
        favicon_url: str | None = None,
        folder: str | None = None,
        is_archived: bool = False,
        metadata_json: dict[str, Any] | None = None,
    ) -> Bookmark:
        """Create a new bookmark.

        Args:
            uri: Unique URI for the bookmark.
            url: The bookmarked URL.
            owner: Owner of the bookmark.
            title: Optional title.
            description: Optional description.
            favicon_url: Optional favicon URL.
            folder: Optional folder/category.
            is_archived: Whether the bookmark is archived.
            metadata_json: Optional metadata payload.

        Returns:
            The created Bookmark instance.
        """
        bm = Bookmark(
            uri=uri,
            url=url,
            owner=owner,
            title=title,
            description=description,
            favicon_url=favicon_url,
            folder=folder,
            is_archived=is_archived,
            metadata_json=metadata_json,
        )
        self._session.add(bm)
        return bm

    def get_by_id(self, bookmark_id: int) -> Bookmark | None:
        """Get a bookmark by ID."""
        return self._session.get(Bookmark, bookmark_id)

    def list_all(self, *, owner: str | None = None) -> list[Bookmark]:
        """List bookmarks, optionally filtered by owner.

        Args:
            owner: Optional owner to filter by.

        Returns:
            List of Bookmark instances.
        """
        stmt = select(Bookmark)
        if owner is not None:
            stmt = stmt.where(Bookmark.owner == owner)
        stmt = stmt.order_by(Bookmark.uri)
        return list(self._session.execute(stmt).scalars().all())

    def delete(self, bookmark: Bookmark) -> None:
        """Delete a bookmark and all its links."""
        self._session.delete(bookmark)

    def add_link(
        self,
        bookmark_id: int,
        resource_id: int,
        relation: BookmarkRelationKind,
    ) -> BookmarkLink:
        """Link a bookmark to a resource.

        Args:
            bookmark_id: The bookmark's ID.
            resource_id: The resource's ID.
            relation: The relationship type.

        Returns:
            The created BookmarkLink instance.
        """
        link = BookmarkLink(
            bookmark_id=bookmark_id,
            resource_id=resource_id,
            relation=relation,
        )
        self._session.add(link)
        return link

    def remove_link(self, bookmark_id: int, resource_id: int) -> bool:
        """Remove a link between a bookmark and a resource.

        Args:
            bookmark_id: The bookmark's ID.
            resource_id: The resource's ID.

        Returns:
            True if link was found and removed, False otherwise.
        """
        stmt = select(BookmarkLink).where(
            BookmarkLink.bookmark_id == bookmark_id,
            BookmarkLink.resource_id == resource_id,
        )
        link = self._session.execute(stmt).scalar_one_or_none()
        if link is None:
            return False
        self._session.delete(link)
        return True


class RepoRepository(_BaseRepository):
    """Repository for Repository (code repo) model operations."""

    def create(
        self,
        uri: str,
        *,
        title: str | None = None,
        description: str | None = None,
        host: str | None = None,
        repo_full_name: str | None = None,
        default_branch: str | None = None,
        web_url: str | None = None,
    ) -> Repository:
        """Create a new repository.

        Args:
            uri: Unique URI for the repository.
            title: Optional title.
            description: Optional description.
            host: Hosting platform.
            repo_full_name: Full repository name (e.g. "owner/repo").
            default_branch: Default branch name.
            web_url: Web URL for the repository.

        Returns:
            The created Repository instance.
        """
        repo = Repository(
            uri=uri,
            title=title,
            description=description,
            host=host,
            repo_full_name=repo_full_name,
            default_branch=default_branch,
            web_url=web_url,
        )
        self._session.add(repo)
        return repo

    def get_by_id(self, repo_id: int) -> Repository | None:
        """Get a repository by ID."""
        return self._session.get(Repository, repo_id)

    def list_all(self) -> list[Repository]:
        """List all repositories."""
        stmt = select(Repository).order_by(Repository.uri)
        return list(self._session.execute(stmt).scalars().all())

    def delete(self, repo: Repository) -> None:
        """Delete a repository and all its links."""
        self._session.delete(repo)

    def add_link(
        self,
        repository_id: int,
        resource_id: int,
        relation: str,
    ) -> RepositoryLink:
        """Link a repository to a resource.

        Args:
            repository_id: The repository's ID.
            resource_id: The resource's ID.
            relation: The relationship type.

        Returns:
            The created RepositoryLink instance.
        """
        link = RepositoryLink(
            repository_id=repository_id,
            resource_id=resource_id,
            relation=relation,
        )
        self._session.add(link)
        return link

    def remove_link(self, repository_id: int, resource_id: int) -> bool:
        """Remove a link between a repository and a resource.

        Args:
            repository_id: The repository's ID.
            resource_id: The resource's ID.

        Returns:
            True if link was found and removed, False otherwise.
        """
        stmt = select(RepositoryLink).where(
            RepositoryLink.repository_id == repository_id,
            RepositoryLink.resource_id == resource_id,
        )
        link = self._session.execute(stmt).scalar_one_or_none()
        if link is None:
            return False
        self._session.delete(link)
        return True
