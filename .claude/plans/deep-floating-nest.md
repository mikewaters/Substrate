# Fix: Pipeline Cache Not Skipping Unchanged Documents

## Context

On a second ingestion run with the exact same dataset, all 773 documents are reported as `updated=773` instead of being skipped. The LlamaIndex docstore-based dedup is supposed to filter unchanged documents upstream so they never reach PersistenceTransform, but it's failing to do so.

## Root Cause

**Hash drift caused by in-place metadata mutation during transforms.**

LlamaIndex's `IngestionPipeline.run()` executes in this order:
1. `_handle_upserts()` — computes `node.hash` from **original** source metadata, compares against docstore
2. `run_transformations()` — transforms modify `node.metadata` **in-place**
3. `_update_docstore(nodes_to_run)` — saves `n.hash`, which is a `@property` that **recomputes** from the now-modified metadata

Since `TextNode.hash` is a dynamic property (`SHA256(str(self.text) + str(self.metadata))`), step 3 stores a **post-transform hash** that includes keys added by our transforms:

- **OntologyMapper** adds: `title`, `description`, `_subject`, `tags`, `categories`, `_ontology_meta`; removes `frontmatter`
- **PersistenceTransform** adds: `doc_id`

On the next run, the source creates documents with the **original** metadata (no `doc_id`, no `_ontology_meta`, etc.), producing hash H1. The docstore has hash H2 (post-transform). H1 != H2, so every document is treated as "changed".

## Fix

Snapshot each document's hash **before** `pipeline.run()`, then overwrite the docstore's hashes with the original (pre-transform) values **after** the pipeline completes but **before** persisting.

### File: `src/catalog/catalog/ingest/pipelines.py`

In the `ingest()` method, around lines 314-318:

```python
source_docs = self.source.documents

# Snapshot pre-transform hashes so we can fix the docstore after
# pipeline.run(). LlamaIndex's _update_docstore saves post-transform
# hashes (because transforms mutate metadata in-place and hash is a
# computed property), causing every document to appear "changed" on
# the next run.
original_hashes = {doc.id_: doc.hash for doc in source_docs}

nodes = pipeline.run(documents=source_docs)
```

Then after `pipeline.run()` returns but before `persist_pipeline()` (around line 400):

```python
# Restore pre-transform hashes so the next run's comparison
# matches the source-produced metadata, not the transform-modified
# metadata.
pipeline.docstore.set_document_hashes(original_hashes)

persist_pipeline(dataset.name, pipeline)
```

### That's it — single file, ~6 lines added.

## Verification

1. Run ingestion on a dataset: `uv run python -m catalog.ingest.pipelines <source_path>`
2. Run again with the same dataset (no file changes)
3. Confirm logs show `updated=0, skipped=773` (or whatever the doc count is)
4. Modify one file, run again — confirm only that file shows as updated
5. Run existing tests: `uv run pytest src/catalog/tests/ -v -k "ingest or persist or cache"`
