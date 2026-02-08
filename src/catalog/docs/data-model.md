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
