# Feature: Delegate Change Detection to LlamaIndex Docstore

## Problem

`PersistenceTransform` uses `SHA256(body)` to decide whether to skip a document. Because
`FrontmatterTransform` strips frontmatter into `node.metadata` before persistence, metadata-only
changes (tags, title, categories, description) produce the same body hash. The document is
incorrectly skipped, and updated metadata is never re-ingested.

## Solution

Replace our custom hash-based change detection with LlamaIndex's built-in docstore mechanism.
LlamaIndex computes `SHA256(text + metadata)` on each node, meaning any frontmatter change
produces a different hash and triggers reprocessing.

The V2 pipeline already has the required infrastructure:
- `SimpleDocumentStore` with `load_pipeline`/`persist_pipeline` for cross-run persistence
- `DocstoreStrategy.UPSERTS_AND_DELETE` configured
- Vector store attached (required -- without it LlamaIndex silently downgrades to DUPLICATES_ONLY)
- Stable document IDs across all sources (`doc.id_ = relative_path`)

## Design

### Change Detection Flow (new)

```
Documents arrive at IngestionPipeline.run()
    |
    v
LlamaIndex docstore strategy (_handle_upserts):
  - New doc_id?          -> pass through to transforms
  - Known doc_id, hash differs? -> delete old from docstore+vectors, pass through
  - Known doc_id, hash same?    -> filter out (never reaches transforms)
  - doc_id in docstore but not in batch? -> delete from docstore+vectors
    |
    v
Only new/changed documents reach PersistenceTransform
    |
    v
PersistenceTransform: always create-or-update (no skip logic)
    |
    v
Post-pipeline: sync deletions to our SQLite DB
```

### Changes to PersistenceTransform

**Before**: PersistenceTransform decides whether to skip based on `content_hash == existing.content_hash`.

**After**: PersistenceTransform always persists. LlamaIndex already filtered unchanged docs upstream.

Specifically:
1. Remove the `content_hash` comparison branch that returns `False` (the skip path)
2. Simplify `_process_node()` to always create or update
3. Keep computing and storing `content_hash` in the DB for diagnostics, but include metadata
   in the hash: `SHA256(body + metadata_json)` to align with LlamaIndex's approach
4. Remove the `_force` parameter (LlamaIndex handles this via `clear_cache`)

### Deletion Sync

LlamaIndex's `UPSERTS_AND_DELETE` handles deletions in the docstore and vector store, but our
SQLite `documents` table also needs updating. After `pipeline.run()`:

```python
# Get all paths that were in the input batch
batch_paths = {doc.metadata["relative_path"] for doc in source.documents}

# Mark documents not in the batch as inactive
doc_repo.deactivate_missing(dataset_id, batch_paths)
```

This is a new method on `DocumentRepository` that sets `active=False` for all documents in
the dataset whose path is not in `batch_paths`.

### Pipeline Build Changes

In `DatasetIngestPipelineV2.build_pipeline()`:
- Remove `force` parameter from `PersistenceTransform` constructor
- The `force` path already calls `clear_cache()` which wipes the docstore, so LlamaIndex
  will treat all documents as new -- achieving the same effect

### Stats Reporting

`PersistenceTransform.stats.skipped` will always be 0 since LlamaIndex filters upstream.
To preserve the "skipped" metric for logging:

```python
# After pipeline run
total_in_batch = len(source.documents)
total_processed = persist.stats.created + persist.stats.updated
result.documents_skipped = total_in_batch - total_processed
```

## Scope

### In scope
- Simplify PersistenceTransform to always-persist (no skip logic)
- Add post-pipeline deletion sync to SQLite DB
- Add `DocumentRepository.deactivate_missing()` method
- Update content_hash computation to include metadata
- Update stats reporting
- Update tests

### Out of scope
- V1 pipeline changes (deprecated, will be deleted)
- Schema migrations (content_hash column stays, just gets a different value)
- IngestionCache (transformation-level caching -- already working, orthogonal concern)

## Risks

1. **First run after change**: The docstore has old hashes (body-only). LlamaIndex will see
   every document as "changed" on the first run because the hash formula changed. This is
   acceptable -- it's a one-time full re-index, equivalent to `--force`.

2. **Metadata ordering**: `str(self.metadata)` in LlamaIndex's hash could be sensitive to
   dict ordering. Python 3.7+ dicts are insertion-ordered, and our metadata flows through
   consistent transforms, so this should be stable. Worth a test.

3. **Silent downgrade**: If the vector store is ever removed from the pipeline, LlamaIndex
   silently falls back to DUPLICATES_ONLY, losing upsert and deletion semantics. We should
   add an assertion that the vector store is attached when using UPSERTS_AND_DELETE.

## Implementation Tasks

1. **Add `DocumentRepository.deactivate_missing()`** -- new repo method
2. **Simplify `PersistenceTransform._process_node()`** -- remove skip logic, always persist
3. **Update `_compute_content_hash()`** -- include metadata in hash (or remove entirely and use node.hash)
4. **Add post-pipeline deletion sync** in `DatasetIngestPipelineV2.ingest()`
5. **Add vector store guard** -- assert vector store is present when strategy is UPSERTS_AND_DELETE
6. **Update stats reporting** -- derive skipped count from batch size minus processed
7. **Update/add tests** -- verify metadata-only changes trigger reprocessing, deletion sync works
