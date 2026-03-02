# ADR-0004: Catalog-Driven Index Reconciliation

**Status:** Accepted
**Date:** 2026-02-27

## Context

The ingest pipeline previously triggered index-artifact deletion via an `on_deactivated` callback: when documents were marked inactive in the catalog, ingest called back into the index layer (e.g. `FTSManager().delete(doc_id)`) to remove document FTS rows. That coupled ingest to index concerns and made FTS/vector lifecycle depend on ingest execution order and callbacks.

An alternative would be to derive deletion from a file-backed LlamaIndex docstore. If cache files are missing or deleted, correctness could diverge.

## Decision

**Catalog `documents.active` is the sole source of truth for deletion lifecycle.** The index pipeline owns reconciliation of all derived index artifacts (document FTS, chunk FTS, vector store) from that catalog state.

- Ingest continues to mark missing documents inactive via `deactivate_missing()` and does not perform any index-artifact deletion.
- At the start of every `DatasetIndexPipeline.index()` run, a reconciliation pass removes document FTS rows, chunk FTS rows (by `source_doc_id`), and vector entries for all documents in the target dataset where `documents.active = 0`.
- Reconciliation uses the same database session as the rest of the index run and is idempotent.

## Rejected alternative

**Index correctness depending on file-backed docstore state.** Relying on a LlamaIndex docstore (e.g. persisted to disk) to decide what to delete would tie correctness to cache files. If the cache is missing or cleared, deleted documents could reappear in search until the next full run. Catalog state is the single durable source of truth.

## Consequences

- Ingest and index are decoupled: ingest owns source-to-catalog state; index owns catalog-to-search-artifact state.
- Deleting or losing pipeline cache/docstore files does not prevent removed documents from being removed from search artifacts.
- Reconciliation runs at the start of each index run, so if indexing fails later, deleted docs are still absent from search.
- The index pipeline must run with an ambient session so reconciliation can query inactive documents and update FTS/chunk FTS; vector deletion is best-effort per backend.
