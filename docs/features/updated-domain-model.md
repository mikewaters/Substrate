# add more elements to the orm models

1. New model class Resource added
2. Dataset and Document are subclasses of Resource
3. New related classes


## Resource Model
- Has the same `id` attribute as Document and Dataset, as well as created_at and modified_at. Has an URI attribute for linked data mapping.
- Has title and description attributes
- Has a ResourceKind enum to distinguish between different resource types (Dataset, Document, etc.) and thisa is used as a discriminator column in the ORM model (named `kind`).
- new table named `resource`

Resource kind enum:
```python
class ResourceKind(str, enum.Enum):
    CATALOG = "catalog"
    DATASET = "dataset"
    COLLECTION = "collection"
    BOOKMARK = "bookmark"
    REPOSITORY = "repository"
```

## Dataset and Document Models
- Modify them to be subclasses of the Resource base class, and cleanup duplicatred properties. Document is no longer directly related to a Dataset, but instead to a Resource (which can be a Dataset or other resource types).
- Add new attributes:
```python
class DocumentKind(str, enum.Enum):
    CACHED_PAGE = "cached_page"
    VAULT_EXPORT = "vault_export"
    PDF = "pdf"
    OTHER = "other"
class Document(Resource):
    kind = Column(Enum(DocumentKind), nullable=False, default=DocumentKind.OTHER)
    resource_id = Column(UUID(as_uuid=True), ForeignKey("resource.id"), nullable=False)
    resource = relationship("Resource", backref="documents")
```

### Catalog models
Example orm structure (adapt this to our codebase):
```python
class CatalogEntryRelationKind(str, enum.Enum):
    DATASET = "dataset"
    BOOKMARK = "bookmark"
    COLLECTION = "collection"
    REPOSITORY = "repository"
    OTHER = "other"

class Catalog(Resource):
    """
    DCAT Catalog (collection of resource descriptions).
    """

    __tablename__ = "catalog"

    id = Column(UUID(as_uuid=True), ForeignKey("resource.id"), primary_key=True)

    homepage = Column(String)                     # foaf:homepage

    __mapper_args__ = {
        "polymorphic_identity": ResourceKind.CATALOG,
    }


class CatalogEntry(Base):
    """
    Generic catalog membership (covers datasets, services, bookmarks, etc.).
    """

    __tablename__ = "catalog_entry"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    catalog_id = Column(UUID(as_uuid=True), ForeignKey("catalog.id"), nullable=False)
    resource_id = Column(UUID(as_uuid=True), ForeignKey("resource.id"), nullable=False)

    relation = Column(Enum(CatalogEntryRelationKind), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String)

    catalog = relationship("Catalog", backref="entries")
    resource = relationship("Resource", backref="catalog_entries")
```

### Bookmark models

```python
class BookmarkRelationKind(str, enum.Enum):
    RELEVANT_TO = "relevant_to"
    SOURCE_FOR = "source_for"
    DERIVED_FROM = "derived_from"

class Bookmark(Resource):
    """
    Bookmark for an external URL, catalogued as a resource.
    """

    __tablename__ = "bookmark"

    id = Column(UUID(as_uuid=True), ForeignKey("resource.id"), primary_key=True)

    url = Column(String, nullable=False)          # original URL
    favicon_url = Column(String)

    owner = Column(String, nullable=False)        # user id / principal

    folder = Column(String)                       # optional logical folder/path
    is_archived = Column(Boolean, default=False)

    __mapper_args__ = {
        "polymorphic_identity": ResourceKind.BOOKMARK,
    }


class BookmarkLink(Base):
    """
    Association between bookmarks and datasets/collections (relevance, source, etc.).
    """

    __tablename__ = "bookmark_link"

    bookmark_id = Column(UUID(as_uuid=True), ForeignKey("bookmark.id"), primary_key=True)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("dataset.id"), primary_key=True)

    relation = Column(Enum(BookmarkRelationKind), nullable=False)

    bookmark = relationship("Bookmark", backref="dataset_links")
    dataset = relationship("Dataset", backref="bookmark_links")

```

### Repository models

```python
class Repository(Resource):
    """
    Code/content repository (e.g., GitHub, GitLab, local).
    """

    __tablename__ = "repository"

    id = Column(UUID(as_uuid=True), ForeignKey("resource.id"), primary_key=True)

    host = Column(String)                         # "github", "gitlab", "local"
    repo_full_name = Column(String)               # e.g., "owner/name"
    default_branch = Column(String)
    web_url = Column(String)

    __mapper_args__ = {
        "polymorphic_identity": ResourceKind.REPOSITORY,
    }


class RepositoryLink(Base):
    """
    Relation between repositories and datasets/collections derived from or related to them.
    """

    __tablename__ = "repository_link"

    repository_id = Column(UUID(as_uuid=True), ForeignKey("repository.id"), primary_key=True)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("dataset.id"), primary_key=True)

    relation = Column(String, nullable=False)     # "source_of", "mirrors", etc.

    repository = relationship("Repository", backref="dataset_links")
    dataset = relationship("Dataset", backref="repository_links")

```
