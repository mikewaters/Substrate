# Resource Hierarchy Design

DCAT-aligned domain model introducing a `Resource` base class with joined-table polymorphic inheritance. All models use SQLAlchemy 2.0 declarative style, integer primary keys, and plural table names.

## Decisions

| Question | Decision |
|----------|----------|
| PK type | Integer (autoincrement), matching existing models |
| SQLAlchemy style | 2.0 declarative (`Mapped` / `mapped_column`) |
| Table names | Plural (`resources`, `datasets`, `documents`, ...) |
| Timestamp column | `updated_at` (existing convention, not `modified_at`) |
| Resource.title/description | Nullable -- caller determines how they are set |
| Document type column | `doc_type` (avoids collision with Resource `kind` discriminator) |
| Document parent FK | `parent_id` (renamed from `resource_id` for clarity) |
| Link table FKs | Point to `resources.id`, not `datasets.id` |

## Cascade behavior

| Resource subclass | Cascade rule |
|-------------------|-------------|
| **Catalog** | Deletes all children: CatalogEntry rows AND child documents (via `parent_id`) |
| **Dataset** | Deletes all direct children: Documents (via `parent_id`) |
| **Document** | Does not cascade-delete any referenced resources |
| **Collection** | Referential only: deletes CollectionMember rows, NOT referenced resources |
| **Bookmark** | Deletes BookmarkLink rows, NOT linked resources |
| **Repository** | Deletes RepositoryLink rows, NOT linked resources |

Link/member tables use `ondelete="CASCADE"` on both FKs so rows are cleaned up when either side is deleted.

## Enums

```python
class ResourceKind(str, enum.Enum):
    """Polymorphic discriminator for the Resource hierarchy."""
    BOOKMARK = "bookmark"
    CATALOG = "catalog"
    COLLECTION = "collection"
    DATASET = "dataset"
    DOCUMENT = "document"
    REPOSITORY = "repository"


class DocumentKind(str, enum.Enum):
    """Classifies the origin/format of a Document."""
    CACHED_PAGE = "cached_page"
    VAULT_EXPORT = "vault_export"
    PDF = "pdf"
    OTHER = "other"


class CatalogEntryRelationKind(str, enum.Enum):
    """Describes how a resource relates to its catalog."""
    BOOKMARK = "bookmark"
    COLLECTION = "collection"
    DATASET = "dataset"
    OTHER = "other"
    REPOSITORY = "repository"


class BookmarkRelationKind(str, enum.Enum):
    """Describes how a bookmark relates to a resource."""
    DERIVED_FROM = "derived_from"
    RELEVANT_TO = "relevant_to"
    SOURCE_FOR = "source_for"
```

## Resource (base class)

Table `resources` -- joined-table inheritance root.

```python
class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[ResourceKind] = mapped_column(Enum(ResourceKind), nullable=False)
    uri: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    documents: Mapped[list["Document"]] = relationship(
        "Document",
        foreign_keys="[Document.parent_id]",
        back_populates="parent_resource",
        cascade="all, delete-orphan",
    )

    __mapper_args__ = {
        "polymorphic_on": "kind",
    }
```

## Dataset

Table `datasets` -- joined to `resources`.

Retains `name` as a dataset-specific slug identifier (separate from `Resource.title`). `uri` and timestamps move to `resources`.

```python
class Dataset(Resource):
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(ForeignKey("resources.id"), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_path: Mapped[str] = mapped_column(String(1024), nullable=False)

    __mapper_args__ = {
        "polymorphic_identity": ResourceKind.DATASET,
    }
```

## Document

Table `documents` -- joined to `resources`.

`parent_id` replaces the old `dataset_id`. Points to any owning Resource (typically a Dataset or Catalog). `doc_type` replaces the proposed `kind` column to avoid collision with the polymorphic discriminator.

Requires explicit `inherit_condition` because both `id` and `parent_id` are FKs to `resources.id`.

```python
class Document(Resource):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(ForeignKey("resources.id"), primary_key=True)
    parent_id: Mapped[int] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    doc_type: Mapped[DocumentKind] = mapped_column(
        Enum(DocumentKind), nullable=False, default=DocumentKind.OTHER
    )
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_modified: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    parent_resource: Mapped["Resource"] = relationship(
        "Resource",
        foreign_keys=[parent_id],
        back_populates="documents",
    )

    __table_args__ = (
        Index("ix_documents_parent_path", "parent_id", "path", unique=True),
        Index("ix_documents_parent_active", "parent_id", "active"),
        Index("ix_documents_content_hash", "content_hash"),
    )

    __mapper_args__ = {
        "polymorphic_identity": ResourceKind.DOCUMENT,
        "inherit_condition": id == Resource.id,
    }
```

Retains `get_metadata()` and `set_metadata()` helper methods from the current model.

## Catalog

Table `catalogs` -- joined to `resources`. DCAT Catalog: a curated collection of resource descriptions.

```python
class Catalog(Resource):
    __tablename__ = "catalogs"

    id: Mapped[int] = mapped_column(ForeignKey("resources.id"), primary_key=True)
    homepage: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    entries: Mapped[list["CatalogEntry"]] = relationship(
        "CatalogEntry",
        back_populates="catalog",
        cascade="all, delete-orphan",
    )

    __mapper_args__ = {
        "polymorphic_identity": ResourceKind.CATALOG,
    }
```

### CatalogEntry

Table `catalog_entries` -- associates a Catalog with a Resource.

```python
class CatalogEntry(Base):
    __tablename__ = "catalog_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    catalog_id: Mapped[int] = mapped_column(
        ForeignKey("catalogs.id", ondelete="CASCADE"), nullable=False
    )
    resource_id: Mapped[int] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"), nullable=False
    )
    relation: Mapped[CatalogEntryRelationKind] = mapped_column(
        Enum(CatalogEntryRelationKind), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    catalog: Mapped["Catalog"] = relationship("Catalog", back_populates="entries")
    resource: Mapped["Resource"] = relationship("Resource")

    __table_args__ = (
        Index("ix_catalog_entries_catalog_resource", "catalog_id", "resource_id", unique=True),
    )
```

## Collection

Table `collections` -- joined to `resources`. A referential grouping; does not own its members.

```python
class Collection(Resource):
    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(ForeignKey("resources.id"), primary_key=True)

    members: Mapped[list["CollectionMember"]] = relationship(
        "CollectionMember",
        back_populates="collection",
        cascade="all, delete-orphan",
    )

    __mapper_args__ = {
        "polymorphic_identity": ResourceKind.COLLECTION,
    }
```

### CollectionMember

Table `collection_members` -- associates a Collection with a Resource.

```python
class CollectionMember(Base):
    __tablename__ = "collection_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    collection_id: Mapped[int] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), nullable=False
    )
    resource_id: Mapped[int] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    collection: Mapped["Collection"] = relationship("Collection", back_populates="members")
    resource: Mapped["Resource"] = relationship("Resource")

    __table_args__ = (
        Index("ix_collection_members_coll_resource", "collection_id", "resource_id", unique=True),
    )
```

## Bookmark

Table `bookmarks` -- joined to `resources`. Catalogued external URL.

```python
class Bookmark(Resource):
    __tablename__ = "bookmarks"

    id: Mapped[int] = mapped_column(ForeignKey("resources.id"), primary_key=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    favicon_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    folder: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    resource_links: Mapped[list["BookmarkLink"]] = relationship(
        "BookmarkLink",
        back_populates="bookmark",
        cascade="all, delete-orphan",
    )

    __mapper_args__ = {
        "polymorphic_identity": ResourceKind.BOOKMARK,
    }
```

### BookmarkLink

Table `bookmark_links` -- relates a Bookmark to any Resource.

```python
class BookmarkLink(Base):
    __tablename__ = "bookmark_links"

    bookmark_id: Mapped[int] = mapped_column(
        ForeignKey("bookmarks.id", ondelete="CASCADE"), primary_key=True
    )
    resource_id: Mapped[int] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True
    )
    relation: Mapped[BookmarkRelationKind] = mapped_column(
        Enum(BookmarkRelationKind), nullable=False
    )

    bookmark: Mapped["Bookmark"] = relationship("Bookmark", back_populates="resource_links")
    resource: Mapped["Resource"] = relationship("Resource")
```

## Repository

Table `repositories` -- joined to `resources`. Code or content repository.

```python
class Repository(Resource):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(ForeignKey("resources.id"), primary_key=True)
    host: Mapped[str | None] = mapped_column(String(100), nullable=True)
    repo_full_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    default_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    web_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    resource_links: Mapped[list["RepositoryLink"]] = relationship(
        "RepositoryLink",
        back_populates="repository",
        cascade="all, delete-orphan",
    )

    __mapper_args__ = {
        "polymorphic_identity": ResourceKind.REPOSITORY,
    }
```

### RepositoryLink

Table `repository_links` -- relates a Repository to any Resource.

```python
class RepositoryLink(Base):
    __tablename__ = "repository_links"

    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), primary_key=True
    )
    resource_id: Mapped[int] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True
    )
    relation: Mapped[str] = mapped_column(String(100), nullable=False)

    repository: Mapped["Repository"] = relationship("Repository", back_populates="resource_links")
    resource: Mapped["Resource"] = relationship("Resource")
```

## Exports

```python
__all__ = [
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
    "Repository",
    "RepositoryLink",
    "Resource",
    "ResourceKind",
]
```

## Implementation notes

- `Document.inherit_condition` is required because `id` and `parent_id` are both FKs to `resources.id`. SQLAlchemy needs explicit disambiguation for the inheritance join. Verify this works in tests; if SQLAlchemy resolves it from the PK FK automatically, the explicit condition can be removed.
- `Resource.documents` relationship with `cascade="all, delete-orphan"` applies uniformly. Subclasses that don't parent Documents (Bookmark, Repository, Collection) are unaffected since no Documents will reference them via `parent_id`. The service layer should validate that `parent_id` points to a valid parent type.
- All link/member tables use composite or unique indexes to prevent duplicate associations.
- The `get_metadata()` and `set_metadata()` helpers stay on Document.
