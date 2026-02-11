# Catalog Data Model

## Inheritance Strategy

The model uses **joined-table polymorphic inheritance** rooted at `Resource`. Every first-class entity (Dataset, Document, Catalog, etc.) is a Resource subtype, sharing common fields (`uri`, `title`, `description`, timestamps) in the `resources` table with type-specific columns in their own tables. The discriminator is `Resource.kind` (the `ResourceKind` enum).

```
Resource (abstract root)
├── Dataset
├── Document
├── Catalog
├── Collection
├── Bookmark
└── Repository
```

---

## Core Entities

### Resource

The base entity. Every row in `resources` has a `kind` that tells you which subtype table to join. Carries `uri` (unique identifier string), optional `title`/`description`, and `created_at`/`updated_at` timestamps. Not instantiated directly -- always one of its subtypes.

### Dataset

A **source of documents** -- represents one ingestion source (e.g., an Obsidian vault, a Heptabase export, a PDF folder). Has a unique `name`, a `source_type` (e.g. "obsidian", "heptabase"), and a `source_path` (filesystem path to the source). Owns Documents through the Resource parent relationship.

### Document

A **single piece of content** within a Dataset. Always belongs to a parent Resource (typically a Dataset) via `parent_id`. Carries:

- `path` -- original file path relative to the source
- `body` -- full text content
- `content_hash` -- SHA-256 for change detection
- `doc_type` -- enum: `VAULT_EXPORT`, `CACHED_PAGE`, `PDF`, `OTHER`
- `active` -- soft-delete flag (inactive = removed from source but kept in DB)
- `metadata_json` -- arbitrary JSON blob for source-specific metadata (frontmatter, etc.)
- `etag`/`last_modified` -- HTTP-style caching headers for remote sources

Uniquely identified within its parent by `(parent_id, path)`.

### Catalog

A **curated collection of resources** -- think of it as a named workspace or project. Has an optional `homepage` URL. Contains resources via `CatalogEntry` join records, each tagged with a relation kind (bookmark, collection, dataset, repository, other).

### Collection

A **grouping of resources** -- simpler than Catalog, no relation typing. Contains resources via `CollectionMember` join records.

### Bookmark

A **saved web URL**. Carries `url`, optional `favicon_url`, `owner` (who saved it), optional `folder` (organizational path), and `is_archived` flag. Links to other resources via `BookmarkLink` with typed relations (derived_from, relevant_to, source_for).

### Repository

A **code repository reference**. Carries `host`, `repo_full_name`, `default_branch`, `web_url`. Links to other resources via `RepositoryLink` with free-form string relation labels.

---

## Relationship Entities (Junction Tables)

### DocumentLink

Connects two Documents directionally. Composite PK of `(source_id, target_id)`. Typed by `DocumentLinkKind`: `WIKILINK` (Obsidian `[[links]]`) or `MARKDOWN_LINK` (Heptabase `[](./links)`). This forms a **directed graph** of document cross-references.

### CatalogEntry

Connects a Catalog to any Resource. Has its own auto-increment `id`, plus `catalog_id` and `resource_id` (unique together). Tagged with `CatalogEntryRelationKind` and tracks `created_at`/`created_by`.

### CollectionMember

Connects a Collection to any Resource. Same pattern as CatalogEntry but without a relation type -- just membership.

### BookmarkLink

Connects a Bookmark to any Resource. Composite PK of `(bookmark_id, resource_id)`. Typed by `BookmarkRelationKind`: `DERIVED_FROM`, `RELEVANT_TO`, `SOURCE_FOR`.

### RepositoryLink

Connects a Repository to any Resource. Composite PK of `(repository_id, resource_id)`. Uses a free-form string `relation` instead of an enum.

---

## Relationship Summary

```
Dataset --(parent_id)--< Document >--(DocumentLink)--< Document
                              ^
Catalog --(CatalogEntry)--> Resource (any subtype)
Collection --(CollectionMember)--> Resource (any subtype)
Bookmark --(BookmarkLink)--> Resource (any subtype)
Repository --(RepositoryLink)--> Resource (any subtype)
```

Key patterns:

- **Dataset -> Document** is a strong ownership (1:many via `parent_id`, cascade delete)
- **Document <-> Document** is a directed graph via DocumentLink (many:many, self-referential)
- **Catalog/Collection -> Resource** are organizational groupings (many:many to any resource type)
- **Bookmark/Repository -> Resource** are cross-reference links (many:many to any resource type)

---

## Enums

| Enum | Values | Used By |
|------|--------|---------|
| `ResourceKind` | bookmark, catalog, collection, dataset, document, repository | Resource.kind (discriminator) |
| `DocumentKind` | cached_page, vault_export, pdf, other | Document.doc_type |
| `DocumentLinkKind` | wikilink, markdown_link | DocumentLink.relation |
| `CatalogEntryRelationKind` | bookmark, collection, dataset, other, repository | CatalogEntry.relation |
| `BookmarkRelationKind` | derived_from, relevant_to, source_for | BookmarkLink.relation |

---

## Secondary Database

There is a `ContentBase` declared for a separate content database (designed to be ATTACHed to the main catalog DB). It is currently empty -- planned for future use to separate large content blobs from the relational metadata.

---

## Store Abstractions (Data Catalog vs Index)

The `catalog.store` module currently mixes two distinct abstractions:

- **Data Catalog**: structured representation of content and metadata.
- **Index**: search and retrieval infrastructure (FTS, vector search, LLM cache, LlamaIndex glue).

Below is a file-by-file classification to guide a future split.

| File | Classification | Notes / split guidance |
| --- | --- | --- |
| `catalog.store.__init__` | Mixed | Re-exports both catalog and index APIs. If splitting, keep catalog exports (models, repositories, schemas, DatasetService, database/session helpers) in Data Catalog and move index exports (FTS managers, vector store, LLM cache, docstore, cleanup) to Index. |
| `catalog.store.cleanup` | Mixed | `IndexCleanup` and `cleanup_fts_*` are Index; `cleanup_stale_documents` and the DirectorySource-based stale document discovery are Data Catalog maintenance. Split into an Index cleanup module and a Data Catalog stale-content cleanup module. |
| `catalog.store.database` | Mixed / Shared infra | Core DB registry/session management is shared. Index-specific pieces are `create_fts_table` and `create_chunks_fts_table` calls during initialization. Move those to Index bootstrap or an Index DB-initialization hook. |
| `catalog.store.dataset` | Data Catalog | Dataset and document CRUD service for catalog data. |
| `catalog.store.docstore` | Index | `SQLiteDocumentStore` is LlamaIndex integration for retrieval; depends on catalog documents but conceptually Index. |
| `catalog.store.fts` | Index | Document-level FTS indexing/search. |
| `catalog.store.fts_chunk` | Index | Chunk-level FTS indexing/search. |
| `catalog.store.llm_cache` | Index | RAG cache (`LLMCache`, `LLMCacheEntry`) is index-related. If splitting, move model/table into Index schema or Index DB. |
| `catalog.store.models` | Data Catalog (legacy/duplicate) | Catalog ORM models; overlaps with `catalog.store.models.catalog`. Keep in Data Catalog or remove in favor of the package version when splitting. |
| `catalog.store.repositories` | Data Catalog | Repositories for catalog resources. |
| `catalog.store.schemas` | Data Catalog | Pydantic I/O schemas for catalog resources. |
| `catalog.store.session_context` | Shared infra | Ambient session plumbing used by both. Place in shared persistence infrastructure or keep as cross-cutting utility. |
| `catalog.store.vector` | Index | Vector store management and retrieval. |
| `catalog.store.models.__init__` | Data Catalog | Re-exports catalog/content models and base. |
| `catalog.store.models.catalog` | Data Catalog | Primary catalog ORM models. |
| `catalog.store.models.content` | Data Catalog | Content DB base for catalog storage. |
