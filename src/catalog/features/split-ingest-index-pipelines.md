# Split Ingest/Index Pipelines

## Status
In Progress

## Date
2026-02-26

## Owner
Catalog

## Summary
`DatasetIngestPipeline` conflates two distinct concerns: document ingestion
(source acquisition, ontology mapping, DB persistence) and indexing (FTS,
chunking, embedding, vector storage). This makes the pipeline hard to reason
about, test independently, and extend (e.g., re-index without re-ingesting).

This PRD splits the monolithic pipeline into two composable stages sharing a
common base class, and extracts FTS persistence into a standalone transform
owned by the index stage.

## Goals
1. Separate ingestion (source -> documents) from indexing (documents -> searchable chunks + vectors)
2. Enable re-indexing without re-ingesting
3. Extract document-level FTS into its own TransformComponent in the index pipeline
4. Create a shared base class for pipeline commonalities

## Non-Goals
1. Changing the source adapter interface
2. Modifying the embedding model or chunking strategy
3. Altering the database schema
4. Adding new integrations

## Architecture

```
catalog.core.pipeline.BasePipeline (new)
    |-- catalog.ingest.pipelines.DatasetIngestPipeline
    |-- catalog.index.pipelines.DatasetIndexPipeline
```

### BasePipeline (`catalog/core/pipeline.py`)

Shared Pydantic base class providing:
- `dataset_id`, `dataset_name` fields
- `embed_model`, `resilient_embedding` fields
- `_get_embed_model()`, `_cache_key()`, settings access via `_settings`
- LlamaIndex pipeline construction helpers (docstore creation, cache load/persist)
- `model_config = {"arbitrary_types_allowed": True}`

### Stage 1: DatasetIngestPipeline (slimmed)

Responsibility: Source acquisition, dataset creation, ontology mapping,
document DB persistence.

Transforms:
1. `OntologyMapper`
2. `PersistenceTransform` -- DB-only, FTS calls removed
3. `source.transforms()` (source-specific post-persist hooks)

Output: Persisted `Document` records with `doc_id` in node metadata. Returns
nodes for the index stage.

The orchestration logic (dataset creation, incremental resolution, deletion
sync, cache management) stays here.

### Stage 2: DatasetIndexPipeline (new)

Responsibility: FTS indexing, chunking, chunk FTS, embedding, vector insertion.

Transforms:
1. `DocumentFTSTransform` (new) -- document-level FTS, extracted from PersistenceTransform
2. `ResilientSplitter`
3. `ChunkPersistenceTransform` (chunk-level FTS + metadata assignment)
4. `EmbeddingPrefixTransform`
5. Vector identity transforms + `embed_model`

Input: Nodes with `doc_id` in metadata (output of ingest stage).

### New Transform: DocumentFTSTransform

Replaces the existing `FTSIndexerTransform` stub (which currently raises
`NotImplementedError`). Simple passthrough transform that calls
`FTSManager.upsert(doc_id, path, body)` for each node. Lives in
`catalog/transform/llama.py`.

## Execution Flow

```
config -> DatasetIngestPipeline.ingest()
            |
            v
       [persisted nodes with doc_id]
            |
            v
       DatasetIndexPipeline.index(nodes)
            |
            v
       [FTS-indexed docs, chunked, embedded, vectorized]
```

The ingest pipeline orchestrator calls ingest then index sequentially.
Deletion sync remains in the ingest pipeline (document lifecycle concern).

## Files Changed

| File | Action |
|---|---|
| `catalog/core/pipeline.py` | New -- `BasePipeline` base class |
| `catalog/ingest/pipelines.py` | Slim down -- remove chunking/embedding/FTS stages, inherit from BasePipeline |
| `catalog/index/pipelines.py` | Rewrite -- `DatasetIndexPipeline` with FTS/chunking/embedding |
| `catalog/transform/llama.py` | Fix `FTSIndexerTransform` -> `DocumentFTSTransform`, remove FTS from `PersistenceTransform` |
| `catalog/ingest/schemas.py` | Add `IndexResult` alongside existing `IngestResult` |
| Tests | Update existing pipeline tests, add unit tests for index pipeline |

## Open Questions
- Should the result schema be split into `IngestResult` + `IndexResult`, or kept unified?
  Decision: Split. IngestResult drops `chunks_created` and `vectors_inserted`;
  IndexResult owns those plus `fts_documents_indexed`.
