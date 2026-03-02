# Plan: Sprint 2 - Create `index` package from catalog

## Context

Sprint 1 moved shared infrastructure to agentlayer (919 tests passing). The catalog
package still contains both ingestion and indexing/search concerns in a single package.
Sprint 2 physically separates them: everything related to search, retrieval, FTS, vectors,
chunking, eval, and the search API/CLI moves to a new `index` top-level package at
`src/catalog/index/`. Both packages ship in the same wheel via hatch multi-package config.

**Dependency direction:** `index` imports from `catalog.store.*` and `catalog.core.settings`.
`catalog.sync` imports from `index.*` to orchestrate both sides.

---

## Package Structure

```
src/catalog/index/
  __init__.py
  status.py                   (check_vector_store, check_fts_table from catalog.core.status)
  pipelines/
    __init__.py               (re-exports DatasetIndexPipeline, IndexResult)
    pipelines.py              (from catalog/index/pipelines.py)
    schemas.py                (from catalog/index/schemas.py)
  search/
    __init__.py + 11 modules  (from catalog/search/)
  eval/
    __init__.py + 3 modules   (from catalog/eval/)
  api/
    __init__.py
    mcp/__init__.py, server.py, tools.py, resources.py  (from catalog/api/)
  cli/
    __init__.py, search.py, eval.py  (from catalog/cli/)
  store/
    __init__.py               (re-exports + setup_index_tables helper)
    fts.py                    (from catalog/store/fts.py)
    fts_chunk.py              (from catalog/store/fts_chunk.py)
    vector.py                 (from catalog/store/vector.py)
    cleanup.py                (from catalog/store/cleanup.py)
  transform/
    __init__.py               (lazy-import proxy)
    llama.py                  (DocumentFTSTransform, ChunkPersistenceTransform - extracted)
    embedding.py              (from catalog/transform/embedding.py)
    chunker.py                (from catalog/transform/chunker.py)
    splitter.py               (from catalog/transform/splitter.py)
```

---

## Critical Complications & Solutions

### 1. `catalog.store.database` imports FTS table creators

`DatabaseRegistry.__init__` calls `create_fts_table()` and `create_chunks_fts_table()`.
After the move these live in `index.store`.

**Solution:** Keep the FTS table creation in `DatabaseRegistry` but change the imports to
`index.store.fts` and `index.store.fts_chunk`. Since `catalog` already depends on `index`
being in the same wheel, this is fine. The alternative (lazy injection) adds complexity
for no benefit since these are always co-deployed.

### 2. `catalog.ingest.pipelines` uses `FTSManager` for deactivation cleanup

Lines 298-311 delete FTS entries for deactivated documents.

**Solution:** Replace inline `FTSManager` usage with a callback. Add
`on_document_deactivated: Callable[[int], None] | None = None` to the pipeline.
`catalog.sync` wires the callback: `on_document_deactivated=FTSManager().delete`.
Remove `from catalog.store.fts import FTSManager` from ingest/pipelines.py.

### 3. `transform/llama.py` has both ingest and index classes

**Solution:** Split it. Keep `TextNormalizerTransform`, `PersistenceTransform`,
`PersistenceStats` in `catalog/transform/llama.py`. Move `DocumentFTSTransform`,
`ChunkPersistenceTransform`, `ChunkPersistenceStats` to `index/transform/llama.py`.
Duplicate the 4-line `_compute_content_hash()` utility in both.

---

## Agent Task Plan (3 agents + leader)

### Agent A: Move search, eval, API, CLI, index pipeline modules

1. Create `src/catalog/index/` package skeleton (all `__init__.py` files)
2. Move `catalog/search/` -> `index/search/` (11 files)
   - Internal imports: `catalog.search.*` -> `index.search.*`
   - Store imports: `catalog.store.fts` -> `index.store.fts`, `catalog.store.fts_chunk` -> `index.store.fts_chunk`, `catalog.store.vector` -> `index.store.vector`
   - Keep: `catalog.core.settings`, `catalog.store.database`, `catalog.store.dataset`
3. Move `catalog/eval/` -> `index/eval/` (4 files)
   - `catalog.eval.*` -> `index.eval.*`, `catalog.search.*` -> `index.search.*`
4. Move `catalog/api/` -> `index/api/` (5 files)
   - `catalog.api.mcp.*` -> `index.api.mcp.*`, `catalog.search.*` -> `index.search.*`
5. Move `catalog/cli/search.py` + `catalog/cli/eval.py` -> `index/cli/` (2 files + new __init__)
6. Move `catalog/index/pipelines.py` + `schemas.py` -> `index/pipelines/` (2 files + new __init__)
   - `catalog.index.schemas` -> `index.pipelines.schemas`
   - `catalog.transform.llama.{DocumentFTSTransform,ChunkPersistenceTransform}` -> `index.transform.llama`
   - `catalog.transform.{embedding,splitter}` -> `index.transform.*`
   - `catalog.store.vector` -> `index.store.vector`
7. Delete old directories: `catalog/search/`, `catalog/eval/`, `catalog/api/`, `catalog/index/`, `catalog/cli/search.py`, `catalog/cli/eval.py`

### Agent B: Move store + transform modules, split llama.py

1. Move `catalog/store/fts.py` -> `index/store/fts.py` (no catalog imports to change)
2. Move `catalog/store/fts_chunk.py` -> `index/store/fts_chunk.py` (no catalog imports)
3. Move `catalog/store/vector.py` -> `index/store/vector.py` (keep `catalog.core.settings`)
4. Move `catalog/store/cleanup.py` -> `index/store/cleanup.py`
   - `catalog.store.fts.FTSManager` -> `index.store.fts.FTSManager`
   - Keep: `catalog.ingest.directory.DirectorySource`, `catalog.store.repositories`
5. Split `catalog/transform/llama.py`:
   - Keep in catalog: `TextNormalizerTransform`, `PersistenceTransform`, `PersistenceStats`
   - Move to `index/transform/llama.py`: `DocumentFTSTransform`, `ChunkPersistenceTransform`, `ChunkPersistenceStats`
   - Duplicate `_compute_content_hash()` in both
   - Remove FTS imports from catalog's llama.py
6. Move `catalog/transform/embedding.py` -> `index/transform/embedding.py`
7. Move `catalog/transform/chunker.py` -> `index/transform/chunker.py`
8. Move `catalog/transform/splitter.py` -> `index/transform/splitter.py`
9. Delete old files from catalog/store/ and catalog/transform/
10. Create `index/store/__init__.py` and `index/transform/__init__.py`

### Agent C: Fix catalog leftovers + move tests

1. Update `catalog/store/__init__.py` - remove re-exports of fts, fts_chunk, vector, cleanup
2. Update `catalog/store/database.py` - change FTS imports to `index.store.fts` / `index.store.fts_chunk`
3. Fix `catalog/ingest/pipelines.py` - replace `FTSManager` with callback pattern
4. Update `catalog/transform/__init__.py` - remove moved symbols
5. Update `catalog/cli/__init__.py` - remove search/eval sub-apps
6. Split `catalog/core/status.py` - move `check_vector_store`, `check_fts_table` to `index/status.py`
7. Update `catalog/sync.py` - `catalog.index.*` -> `index.*`, wire FTS cleanup callback
8. Update `pyproject.toml` - add `index` to `[tool.hatch.build.targets.wheel] packages`
9. Move test files:
   - **To `tests/index/`:** unit/search/*, unit/transform/{test_chunker,test_embedding_prefix,test_resilient_splitter}, unit/api/*, unit/cli/*, unit/pipelines/test_index.py, unit/store/{test_fts,test_heading_split,test_vector,test_cleanup}, integration/{test_heading_bias,test_hybrid_search,test_vector_hybrid_rerank}, rag_v2/*
   - **Stay in `tests/idx/`:** everything else (ingest, integrations, ontology, store/database+models+service, transform/persistence+frontmatter, core/status, all integration tests touching ingest)
10. Update test imports: `catalog.search.*` -> `index.search.*`, etc.
11. Create `tests/index/conftest.py` - patches `index.pipelines.pipelines.VectorStoreManager`
12. Update `tests/idx/conftest.py` - remove index pipeline patch (now in tests/index/conftest.py)

### Leader: Final sweep + verification

1. Global grep for stale `catalog.search`, `catalog.eval`, `catalog.store.fts`, `catalog.store.vector` imports
2. Verify: `uv run python -c "import index; from index.search import SearchService; from index.pipelines import DatasetIndexPipeline"`
3. Run: `uv run pytest src/agentlayer/tests/ src/catalog/tests/ -x -q`

---

## Import Change Summary

| Old import | New import |
|---|---|
| `catalog.search.*` | `index.search.*` |
| `catalog.eval.*` | `index.eval.*` |
| `catalog.api.*` | `index.api.*` |
| `catalog.index.pipelines` | `index.pipelines` |
| `catalog.index.schemas` | `index.pipelines.schemas` |
| `catalog.store.fts` | `index.store.fts` |
| `catalog.store.fts_chunk` | `index.store.fts_chunk` |
| `catalog.store.vector` | `index.store.vector` |
| `catalog.store.cleanup` | `index.store.cleanup` |
| `catalog.transform.embedding` | `index.transform.embedding` |
| `catalog.transform.chunker` | `index.transform.chunker` |
| `catalog.transform.splitter` | `index.transform.splitter` |
| `catalog.transform.llama.DocumentFTSTransform` | `index.transform.llama.DocumentFTSTransform` |
| `catalog.transform.llama.ChunkPersistenceTransform` | `index.transform.llama.ChunkPersistenceTransform` |

Unchanged (stay in catalog): `catalog.core.settings`, `catalog.store.database`,
`catalog.store.models`, `catalog.store.repositories`, `catalog.store.dataset`,
`catalog.store.schemas`, `catalog.store.docstore`, `catalog.ingest.*`,
`catalog.integrations.*`, `catalog.transform.ontology`, `catalog.transform.links`,
`catalog.transform.llama.PersistenceTransform`, `catalog.sync`

---

## Verification

```bash
uv sync
uv run python -c "import catalog; import index"
uv run pytest src/agentlayer/tests/ -x -q
uv run pytest src/catalog/tests/idx/ -x -q
uv run pytest src/catalog/tests/index/ -x -q
```
