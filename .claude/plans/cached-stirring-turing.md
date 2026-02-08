# Plan: E2E test module for Catalog

## Context

We need to refactor 6 integration tests into a new `src/catalog/tests/e2e/` module that runs against real, persistent infrastructure (SQLite + Qdrant) provisioned uniquely per test. Test databases must survive after the run for manual inspection.

## Pushback: Embedding model and LLM reranker

**Embedding model must remain mocked.** Loading a real model (~500MB download, seconds to initialize) would make tests impractical. `MockEmbedding` produces deterministic 384-dim vectors that exercise every infrastructure path identically to real embeddings -- the difference is only in vector similarity quality, not infrastructure coverage.

**LLM reranker must remain mocked** for `test_full_pipeline_ingest_search_rerank`. It requires an OpenAI API key and costs money per call.

Everything else is real: SQLite, FTS5, Qdrant (file-based), LlamaIndex IngestionPipeline, docstore, all transforms.

## Approach: Environment-driven settings override

Instead of patching `get_session` and `VectorStoreManager` (the current integration test pattern), override settings via environment variables and clear singleton caches. This lets the entire stack initialize naturally through the same code paths as production.

**How it works:**
1. `monkeypatch.setenv` sets `IDX_DATABASES__CATALOG_PATH`, `IDX_DATABASES__CONTENT_PATH`, `IDX_VECTOR_STORE_PATH`, `IDX_CACHE_PATH` to test-specific output dirs
2. Clear `get_settings`, `get_registry`, `get_session_factory` lru_caches
3. Call `get_registry()` -- this triggers `DatabaseRegistry.__init__` which creates engine, tables, FTS virtual tables, content DB ATTACH
4. Pipeline calls `get_session()` naturally (no patching!)
5. Pipeline creates `VectorStoreManager()` naturally -- reads test `vector_store_path` from settings
6. Only mock: `catalog.embedding.get_embed_model` returns `MockEmbedding`

**For search (HybridSearch):** Create `VectorStoreManager()` (reads test paths from settings), inject `vm._embed_model = embed_model` to bypass real model loading in `load_or_create()`, then pass to `HybridSearch(vector_manager=vm)`.

## Output directory

```
src/catalog/tests/e2e/.output/          <-- .gitignored
  test_ingest_and_fts_search/
    catalog.db                           <-- inspectable
    content.db
    qdrant/                              <-- inspectable
    cache/pipeline_storage/...           <-- docstore cache
  test_fts_keyword_search/
    ...
```

Cleaned at the START of each test (not after), so results always reflect the last run.

## Files to create

### `src/catalog/tests/e2e/__init__.py`
Empty.

### `src/catalog/tests/e2e/.gitignore`
```
.output/
```

### `src/catalog/tests/e2e/conftest.py`

Core fixture: `e2e` (function-scoped).

```python
@dataclass
class E2EInfra:
    output_dir: Path
    embed_model: MockEmbedding

    @contextmanager
    def session(self):
        """Convenience session from get_session() -- same code path as prod."""
        with get_session() as session:
            yield session

    def vector_manager(self) -> VectorStoreManager:
        """Real VectorStoreManager with mock embedding for search."""
        vm = VectorStoreManager()    # reads test paths from settings
        vm._embed_model = self.embed_model
        return vm

@pytest.fixture
def e2e(request, monkeypatch):
    test_name = request.node.name
    output_dir = E2E_OUTPUT / test_name

    # Clean before (not after) -- results persist for inspection
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    # Clear singleton caches
    get_settings.cache_clear()
    get_registry.cache_clear()
    get_session_factory.cache_clear()

    # Override settings via env
    monkeypatch.setenv("IDX_DATABASES__CATALOG_PATH", str(output_dir / "catalog.db"))
    monkeypatch.setenv("IDX_DATABASES__CONTENT_PATH", str(output_dir / "content.db"))
    monkeypatch.setenv("IDX_VECTOR_STORE_PATH", str(output_dir / "qdrant"))
    monkeypatch.setenv("IDX_CACHE_PATH", str(output_dir / "cache"))

    embed_model = MockEmbedding(embed_dim=384)

    with patch("catalog.embedding.get_embed_model", return_value=embed_model):
        get_registry()  # triggers full DB init (tables, FTS, content ATTACH)
        yield E2EInfra(output_dir=output_dir, embed_model=embed_model)

    # Teardown: clear caches so non-e2e tests get fresh singletons
    get_settings.cache_clear()
    get_registry.cache_clear()
    get_session_factory.cache_clear()
```

Vault fixtures (`sample_vault`, `linked_vault`, `ontology_vault`, `sample_docs`) also defined here, same content as the existing integration test fixtures.

### `src/catalog/tests/e2e/test_catalog_e2e.py`

Six tests, each using the `e2e` fixture. All use `DatasetIngestPipelineV2` for ingestion (real pipeline, not custom mini-pipelines) and `get_session()` for DB queries (no patching).

#### 1. `test_ingest_and_fts_search` (from test_ingest_fts.py::TestIngestAndSearch::test_ingest_directory_then_search)
- Ingest `sample_vault` with `SourceDirectoryConfig`
- Search with `FTSSearch` for "python" using `get_session()` + `use_session()`
- Assert >= 2 results, verify expected paths

#### 2. `test_fts_keyword_search` (from test_hybrid_search.py::TestSearchServiceModes::test_fts_mode_returns_keyword_matches)
- Ingest `sample_vault` with `SourceObsidianConfig`
- Search with `FTSSearch` for "OAuth2"
- Assert auth.md found

#### 3. `test_hybrid_search` (from test_hybrid_search.py::TestHybridSearchRRF::test_hybrid_search_returns_results)
- Ingest `sample_vault` with `SourceObsidianConfig`
- Create `vm = e2e.vector_manager()` and use real `HybridSearch(vector_manager=vm)`
- Search for "authentication" with ambient session
- Assert non-empty results with `"rrf"` in scores

**Key difference from integration test:** No mocked `QueryFusionRetriever`. Real FTS + real Qdrant vector search (with mock embeddings). FTS finds keyword matches; vector returns structurally valid results. RRF fuses both.

#### 4. `test_full_pipeline_ingest_search_rerank` (from test_vector_hybrid_rerank.py::TestEndToEndFlow)
- Ingest `sample_docs` with `SourceDirectoryConfig`
- Real hybrid search via `e2e.vector_manager()` (same as test 3)
- Mock LLM reranker: `Reranker(provider=mock_provider)` with `AsyncMock`
- Assert reranked results have `"rerank"` and `"blend_weight"` in scores

#### 5. `test_backlinks_queryable` (from test_obsidian_links.py::TestObsidianLinkIntegration)
- Ingest `linked_vault` with `SourceObsidianConfig` via `DatasetIngestPipelineV2`
- ObsidianVaultSource.transforms() includes `LinkResolutionTransform` as post-persist transform
- Query `document_links` table for incoming links to note A
- Assert B and D link to A (2 incoming)

**Key difference from integration test:** Uses `DatasetIngestPipelineV2` instead of custom `IngestionPipeline([frontmatter, persist, link_resolve])` mini-pipeline.

#### 6. `test_frontmatter_ontology_metadata` (from test_frontmatter_ontology.py::TestFrontmatterOntologyWithSchema)
- Define `SampleVaultSchema` (same as existing test)
- Ingest `ontology_vault` with `SourceObsidianConfig(vault_schema=SampleVaultSchema)`
- Query `documents` + `resources` tables
- Assert ontology-shaped metadata: title, tags, categories, author, extra

**Key difference from integration test:** Uses `DatasetIngestPipelineV2` instead of custom mini-pipeline.

## Key files referenced

| File | Role |
|------|------|
| `catalog/core/settings.py` | `get_settings()` -- lru_cached singleton, reads `IDX_*` env vars |
| `catalog/store/database.py` | `get_registry()`, `get_session_factory()`, `get_session()` -- all lru_cached |
| `catalog/store/vector.py` | `VectorStoreManager` -- reads `settings.vector_store_path`, lazy `_get_embed_model()` |
| `catalog/embedding/__init__.py` | `get_embed_model()` -- patched to return `MockEmbedding` |
| `catalog/ingest/pipelines_v2.py` | `DatasetIngestPipelineV2.ingest()` -- calls `get_session()`, creates `VectorStoreManager()` |
| `catalog/integrations/obsidian/source.py` | `ObsidianVaultSource.transforms()` -- returns `[FrontmatterTransform]`, `[LinkResolutionTransform, ...]` |
| `catalog/search/fts.py` | `FTSSearch` -- FTS5 search with dataset filtering |
| `catalog/search/hybrid.py` | `HybridSearch` -- RRF fusion of FTS + vector |
| `catalog/llm/reranker.py` | `Reranker` -- LLM-as-judge reranking (mocked) |
| `tests/idx/conftest.py` | `MockEmbedding` class -- reused in e2e conftest |

## Verification

```bash
# Run e2e tests
uv run pytest src/catalog/tests/e2e/ -v

# Inspect test databases after run
sqlite3 src/catalog/tests/e2e/.output/test_ingest_and_fts_search/catalog.db ".tables"
sqlite3 src/catalog/tests/e2e/.output/test_ingest_and_fts_search/catalog.db "SELECT * FROM documents"
ls src/catalog/tests/e2e/.output/test_ingest_and_fts_search/qdrant/

# Verify existing integration tests still pass
uv run pytest src/catalog/tests/idx/integration/ -v
```
