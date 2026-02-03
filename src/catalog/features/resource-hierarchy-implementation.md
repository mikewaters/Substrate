# Resource Hierarchy -- Implementation Plan

Refer to `resource-hierarchy-design.md` for the full model specification.

## Phase 1: Models (models.py only)

All changes in `src/catalog/catalog/store/models.py`. No downstream changes yet.

**Task 1.1: Add enums and Resource base class**
- Add `ResourceKind`, `DocumentKind`, `CatalogEntryRelationKind`, `BookmarkRelationKind` enums
- Add `Resource` base class with joined-table inheritance (`resources` table)
- Fields: `id`, `kind` (discriminator), `uri`, `title`, `description`, `created_at`, `updated_at`
- Add `documents` relationship with `cascade="all, delete-orphan"` via `Document.parent_id`

**Task 1.2: Refactor Dataset to extend Resource**
- Change `Dataset(Base)` to `Dataset(Resource)`
- Add `id` FK to `resources.id` as PK
- Keep `name`, `source_type`, `source_path` on `datasets` table
- Remove `uri`, `created_at`, `updated_at` (now on `resources`)
- Add `polymorphic_identity = ResourceKind.DATASET`
- Remove old `documents` relationship (now inherited from Resource)

**Task 1.3: Refactor Document to extend Resource**
- Change `Document(Base)` to `Document(Resource)`
- Add `id` FK to `resources.id` as PK
- Rename `dataset_id` to `parent_id` (FK to `resources.id`, `ondelete="CASCADE"`)
- Rename `kind` to `doc_type` (DocumentKind enum)
- Remove `created_at`, `updated_at` (now on `resources`)
- Add `parent_resource` relationship back to Resource
- Add `inherit_condition = id == Resource.id`
- Update indexes: `ix_documents_dataset_path` -> `ix_documents_parent_path`, etc.
- Keep `get_metadata()` / `set_metadata()` helpers

**Task 1.4: Add Catalog + CatalogEntry** (parallel with 1.5-1.7)
- `Catalog(Resource)` on `catalogs` table: `id`, `homepage`
- `CatalogEntry(Base)` on `catalog_entries` table: `id`, `catalog_id`, `resource_id`, `relation`, `created_at`, `created_by`
- Cascade: deleting Catalog deletes entries; `ondelete="CASCADE"` on both FKs

**Task 1.5: Add Collection + CollectionMember** (parallel with 1.4, 1.6, 1.7)
- `Collection(Resource)` on `collections` table: `id`
- `CollectionMember(Base)` on `collection_members` table: `id`, `collection_id`, `resource_id`, `created_at`
- Cascade: deleting Collection deletes member rows only; `ondelete="CASCADE"` on both FKs

**Task 1.6: Add Bookmark + BookmarkLink** (parallel with 1.4, 1.5, 1.7)
- `Bookmark(Resource)` on `bookmarks` table: `id`, `url`, `favicon_url`, `owner`, `folder`, `is_archived`
- `BookmarkLink(Base)` on `bookmark_links` table: composite PK (`bookmark_id`, `resource_id`), `relation`
- Cascade: deleting Bookmark deletes link rows only

**Task 1.7: Add Repository + RepositoryLink** (parallel with 1.4, 1.5, 1.6)
- `Repository(Resource)` on `repositories` table: `id`, `host`, `repo_full_name`, `default_branch`, `web_url`
- `RepositoryLink(Base)` on `repository_links` table: composite PK (`repository_id`, `resource_id`), `relation`
- Cascade: deleting Repository deletes link rows only

**Task 1.8: Update exports**
- Update `__all__` in `models.py` to include all new classes and enums
- Update `store/__init__.py` exports

## Phase 2: Tests

**Task 2.1: Update existing model tests**
- File: `catalog/tests/idx/unit/store/test_models.py`
- Update `TestDataset` fixtures: Dataset now requires `uri` (via Resource), constructor changes
- Update `TestDocument` fixtures: `dataset_id` -> `parent_id`, Document now requires `uri`
- Update `TestDatasetDocumentRelationship`: relationship is now via `parent_resource` / `documents`
- Verify cascade delete still works through Resource inheritance

**Task 2.2: Add tests for new models** (parallel with 2.1 once fixtures are shared)
- Test Resource base: create, unique URI constraint, repr
- Test Catalog + CatalogEntry: create, relationship, cascade delete entries
- Test Collection + CollectionMember: create, membership, cascade deletes members but not resources
- Test Bookmark + BookmarkLink: create, link to resource, cascade deletes links
- Test Repository + RepositoryLink: create, link to resource, cascade deletes links
- Test polymorphic querying: `session.query(Resource)` returns mixed types

## Phase 3: Repository layer

**Task 3.1: Update DatasetRepository**
- `create()`: now needs `uri` parameter (or generates it)
- All PK-based lookups unchanged (still `int`)
- `get_by_uri()` moves to a base ResourceRepository or stays

**Task 3.2: Update DocumentRepository**
- `create()`: `dataset_id` -> `parent_id`, add `uri` and `doc_type` params
- `get_by_path()`: `dataset_id` -> `parent_id`
- `list_by_dataset()` -> `list_by_parent()` (or keep name for convenience)
- All path-based queries: `dataset_id` -> `parent_id`

**Task 3.3: Add new repositories** (parallel)
- `CatalogRepository`: CRUD for Catalog, manage entries
- `CollectionRepository`: CRUD for Collection, manage members
- `BookmarkRepository`: CRUD for Bookmark, manage links
- `RepositoryRepository` (or `RepoRepository`): CRUD for Repository, manage links
- Consider a base `ResourceRepository` with shared logic

## Phase 4: Schemas + Services

**Task 4.1: Update Pydantic schemas**
- `DatasetCreate`: add optional `title`, `description`; URI generation stays in service
- `DocumentCreate`: `dataset_id` -> `parent_id`, add optional `doc_type`
- `DatasetInfo` / `DocumentInfo`: reflect new field names
- Add schemas for Catalog, Collection, Bookmark, Repository

**Task 4.2: Update DatasetService**
- URI generation unchanged (already generates from name)
- Document creation passes `parent_id` instead of `dataset_id`

**Task 4.3: Add services for new resource types** (parallel)

## Phase 5: FTS / Search / Transform

**Task 5.1: Update FTS managers**
- `store/fts.py`, `store/fts_chunk.py`: `dataset_id` -> `parent_id` in all queries

**Task 5.2: Update docstore and transform**
- `store/docstore.py`: Document construction uses `parent_id`
- `transform/llama.py`: `PersistenceTransform` / `ChunkPersistenceTransform` use `parent_id`

## Execution order

```
Phase 1 (models.py):
  1.1 (enums + Resource) --> 1.2 (Dataset) --> 1.3 (Document)
                          \-> 1.4 (Catalog)     -\
                          \-> 1.5 (Collection)   -|--> 1.8 (exports)
                          \-> 1.6 (Bookmark)     -|
                          \-> 1.7 (Repository)   -/

Phase 2 (tests):
  2.1 (update existing) -\
  2.2 (new model tests) -/--> verify all pass

Phase 3 (repositories):
  3.1 (DatasetRepo) -\
  3.2 (DocumentRepo) -|--> integration tests
  3.3 (new repos)     -/

Phase 4 (schemas + services):
  4.1 (schemas) --> 4.2 (DatasetService) --> 4.3 (new services)

Phase 5 (FTS / search / transform):
  5.1 (FTS) -\
  5.2 (docstore + transform) -/--> end-to-end tests
```

## Verification

After each phase, run `make agent-test` to confirm no regressions. After Phase 2, all model-level tests should pass. After Phase 5, the full ingestion pipeline (`scripts/ingest_obsidian_vault.py`) should work end-to-end.

## Key files modified

| Phase | Files |
|-------|-------|
| 1 | `src/catalog/catalog/store/models.py`, `src/catalog/catalog/store/__init__.py` |
| 2 | `src/catalog/catalog/tests/idx/unit/store/test_models.py` (+ new test files) |
| 3 | `src/catalog/catalog/store/repositories.py` |
| 4 | `src/catalog/catalog/store/schemas.py`, `src/catalog/catalog/store/dataset.py` |
| 5 | `src/catalog/catalog/store/fts.py`, `src/catalog/catalog/store/fts_chunk.py`, `src/catalog/catalog/store/docstore.py`, `src/catalog/catalog/transform/llama.py` |
