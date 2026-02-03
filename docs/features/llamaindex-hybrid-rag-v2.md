# LlamaIndex Hybrid RAG v2 (Additive) Integration Design

## Summary
This document proposes an additive LlamaIndex-based RAG + hybrid retrieval path for the catalog codebase. The design keeps existing search and ingestion flows intact while introducing an opt-in v2 path that reuses current storage, embedding, and retrieval seams.

## Existing Seams & Contracts

### A) Storage & Vector I/O
- Vector persistence and retrieval is managed via `catalog.store.vector.VectorStoreManager`, which creates/loads a `VectorStoreIndex` and persists to the configured `IDX_VECTOR_STORE_PATH` directory.
- Vector queries are executed either directly against `SimpleVectorStore` (`catalog.search.vector.VectorSearch`) or via `VectorStoreIndex.as_retriever()` in the hybrid path (`catalog.search.hybrid.HybridSearch`).
- Dataset scoping relies on `source_doc_id = "{dataset}:{path}"` in node metadata. The hybrid retriever uses LlamaIndex `MetadataFilters` with `FilterOperator.CONTAINS` on `source_doc_id`, while direct vector search filters results in Python.

### B) Embeddings Access
- Embedding model creation is centralized in `catalog.embedding.get_embed_model()` and `catalog.store.vector.VectorStoreManager._get_embed_model()`.
- MLX and HuggingFace embeddings are supported, with batch size defined by `IDX_EMBEDDING__BATCH_SIZE`.
- No explicit embedding cache or retry middleware exists; models are lazily initialized.

### C) Document/Node Persistence
- Documents are persisted via `catalog.transform.llama.PersistenceTransform`, which writes to SQLite and updates `documents_fts`.
- Chunk nodes are persisted via `catalog.transform.llama.ChunkPersistenceTransform`, which sets stable node IDs (`{content_hash}:{chunk_seq}`) and writes to `chunks_fts` with `source_doc_id` metadata.

### D) Retrieval Pipeline Assembly
- `catalog.search.fts_chunk.FTSChunkRetriever` implements a LlamaIndex `BaseRetriever` over the `chunks_fts` FTS5 index.
- `catalog.search.hybrid.HybridSearch` assembles a `QueryFusionRetriever` (RRF mode) over FTS and vector retrievers.
- `catalog.search.rerank.Reranker` wraps LlamaIndex `LLMRerank` postprocessing.

### E) External Function API Layer
- The public `catalog.search.search()` function returns `SearchResults` and sets up sessions.
- `catalog.search.service.SearchService` is the primary orchestrator and uses `SearchCriteria` and `SearchResult` Pydantic models.

### F) Ingestion Pipeline Assembly
- `catalog.ingest.pipelines.DatasetIngestPipeline` orchestrates ingestion using a LlamaIndex `IngestionPipeline`, with persistence and chunking transforms (`PersistenceTransform`, `ChunkPersistenceTransform`, and `SentenceSplitter`).
- Dataset-level metadata normalization and source-specific transforms are attached via `catalog.ingest.sources.create_source()` and its transform hooks.
- FTS and chunk FTS tables are ensured during ingestion through `catalog.store.fts.create_fts_table()` and `catalog.store.fts_chunk.create_chunks_fts_table()`.

## Parallel Path Strategy

### Exposure Strategy
Introduce a new, explicit namespace:
- `catalog.search_v2.search()` convenience function
- `catalog.search_v2.service.SearchServiceV2` orchestrator

Default behavior stays unchanged; v2 is opt-in by using the new namespace.

### Compatibility & Migration
- Clients can adopt `catalog.search_v2` without changing existing `catalog.search` flows.
- Provide a side-by-side comparison mode in v2 (`compare_with_v1=True`) for internal evaluation.
- Rollback is achieved by reverting to `catalog.search.search()`.

## Design-to-Repo Mapping Table

| Capability | LlamaIndex abstraction | Existing seam | Proposed new code | Config knobs | Parity risks |
| --- | --- | --- | --- | --- | --- |
| Chunking defaults + overlap | `SentenceSplitter` / `TokenTextSplitter` | `catalog.ingest.pipelines.DatasetIngestPipeline` | `catalog/search_v2/ingestion.py` | `IDX_RAG_V2__CHUNK_SIZE`, `IDX_RAG_V2__CHUNK_OVERLAP` | Token vs char chunk parity |
| Embedding text formatting | `TransformComponent` | `catalog.transform.llama` pipeline | `catalog/search_v2/transforms.py` | `IDX_RAG_V2__EMBED_PREFIX_QUERY`, `IDX_RAG_V2__EMBED_PREFIX_DOC` | Prefix mismatch risk |
| Ingestion pipeline assembly | `IngestionPipeline` | `DatasetIngestPipeline` + transforms | `catalog/search_v2/ingestion.py` | `IDX_RAG_V2__INGEST__*` | Pipeline ordering parity |
| Vector retrieval | `VectorIndexRetriever` | `VectorStoreManager` | `catalog/search_v2/retrievers.py` | `IDX_RAG_V2__VECTOR_TOP_K` | Score normalization |
| Lexical retrieval | `BaseRetriever` | `FTSChunkRetriever` | reuse existing retriever | `IDX_RAG_V2__FTS_TOP_K` | FTS scoring differences |
| Hybrid fusion | `QueryFusionRetriever` | `HybridSearch` | `HybridRetrieverFactoryV2` | `IDX_RAG_V2__FUSION_TOP_K` | RRF weighting parity |
| Reranking | `LLMRerank` | `Reranker` | `catalog/search_v2/rerank.py` | `IDX_RAG_V2__RERANK_TOP_N` | Model parity |
| Snippet/citation shaping | response glue | `SearchResult` fields | `catalog/search_v2/formatting.py` | snippet length | No chunk snippet helper |
| Evaluation harness | Pytest | existing tests | `tests/rag_v2/` | thresholds | dataset variability |

## Proposed New Mid-Layer Abstractions

### EmbeddingPrefixTransform
- **Purpose:** Apply QMD-style prefixes to embeddings while reusing the existing embedding infrastructure.
- **Location:** `src/catalog/catalog/search_v2/transforms.py`
- **Interface:** `__call__(nodes: list[BaseNode]) -> list[BaseNode]`
- **Dependencies:** `catalog.embedding.get_embed_model`, existing ingestion pipeline.
- **Rationale:** LlamaIndex does not provide prefix formatting by default.

### HybridRetrieverFactoryV2
- **Purpose:** Centralize construction of a `QueryFusionRetriever` using existing FTS and vector retrievers.
- **Location:** `src/catalog/catalog/search_v2/retrievers.py`
- **Interface:** `build(query, dataset_name, k_lex, k_dense, k_fused) -> QueryFusionRetriever`
- **Dependencies:** `FTSChunkRetriever`, `VectorStoreManager`.
- **Rationale:** Keeps RRF configuration versioned and isolated from v1.

### QueryEngineBuilderV2
- **Purpose:** Assemble retriever + postprocessors + response shaping for v2.
- **Location:** `src/catalog/catalog/search_v2/engine.py`
- **Interface:** `build_query_engine(...) -> RetrieverQueryEngine`
- **Dependencies:** `Reranker` and LlamaIndex query engine components.
- **Rationale:** Encapsulates wiring and enables opt-in features (rerank, fusion).

### IngestionPipelineBuilderV2
- **Purpose:** Compose a v2 ingestion pipeline that reuses existing persistence and chunking transforms while enabling v2-specific embedding formatting.
- **Location:** `src/catalog/catalog/search_v2/ingestion.py`
- **Interface:** `build_pipeline(dataset_id, dataset_name, embed_model, chunk_size, chunk_overlap) -> IngestionPipeline`
- **Dependencies:** `PersistenceTransform`, `ChunkPersistenceTransform`, `SentenceSplitter`, `VectorStoreManager`, source transforms from `catalog.ingest.sources`.
- **Rationale:** Keeps v2 ingestion separate while honoring current storage and FTS contracts.

## Phased Implementation Plan

### Phase 1: Minimal vertical slice (parallel path)
- **Scope:** Hybrid retrieval using existing FTS + vector seams, plus a v2 ingestion builder that wires existing persistence transforms.
- **Code locations:**
  - `src/catalog/catalog/search_v2/__init__.py`
  - `src/catalog/catalog/search_v2/service.py`
  - `src/catalog/catalog/search_v2/retrievers.py`
  - `src/catalog/catalog/search_v2/ingestion.py`
- **Tests:** `tests/rag_v2/test_hybrid_retrieval.py`
- **Done means:** `search_v2` returns `SearchResults` with `SearchResult` payloads matching v1 schema, and `IngestionPipelineBuilderV2` builds a pipeline that reuses existing persistence transforms.

### Phase 2: Quality parity
- **Scope:** Prefix formatting + reranking.
- **Code locations:**
  - `src/catalog/catalog/search_v2/transforms.py`
  - `src/catalog/catalog/search_v2/rerank.py`
- **Tests:** `tests/rag_v2/test_rerank.py`
- **Done means:** Reranked results align with expected ordering and v1-compatible output shape.

### Phase 3: Operationalization
- **Scope:** Config, metrics, and performance knobs.
- **Code locations:**
  - `src/catalog/catalog/core/settings.py`
  - `src/catalog/catalog/search_v2/service.py`
- **Tests:** `tests/rag_v2/test_settings.py`
- **Done means:** v2 behavior is driven by `IDX_RAG_V2__*` configuration.

### Phase 4: Evaluation & rollout
- **Scope:** Golden queries and side-by-side evaluation mode.
- **Code locations:**
  - `tests/rag_v2/test_eval.py`
  - `src/catalog/catalog/search_v2/service.py`
- **Done means:** `compare_with_v1=True` supports evaluation without replacing v1.

## Change Boundaries
- Do not change `catalog.search.service.SearchService`, `catalog.search.search()`, or existing v1 retrievers.
- All v2 additions should live under `catalog/search_v2/` and new tests under `tests/rag_v2/`.
- Only extend `catalog.core.settings.Settings` to add v2 configuration keys.

## Rollout & Evaluation Plan
- New v2 namespace is opt-in by default.
- Side-by-side comparison mode for internal regression testing.
- Golden-query evaluation ensures hit@k parity for hybrid retrieval.

## Risks & Mitigations
- **Chunking parity risk:** Provide optional token-based splitter config and keep defaults aligned with existing usage.
- **Embedding prefix mismatch:** Encode prefixes in a minimal `TransformComponent`.
- **Score comparability:** Focus on ranking parity rather than score parity.

## Additional Gaps vs Original Artifact
- **Query expansion + HyDE:** The current retrieval path uses `QueryFusionRetriever` with `num_queries=1` and no query expansion, and there is no query pipeline or transform wired into search yet. For v2, implement a LlamaIndex-based `QueryExpansionRetrieverV2` in `catalog/search_v2/retrievers.py` that composes: (1) a `QueryTransform` (e.g., LlamaIndex `HyDEQueryTransform` for HyDE) plus a lightweight custom `LexVecQueryTransform` that emits separate query lists for lexical vs vector retrieval, and (2) a `QueryFusionRetriever` configured with `num_queries` equal to the total expansion count. The retriever should: build expanded query bundles per retriever, preserve the original query with higher weight (by duplicating the original query in the expansion list or using LlamaIndex retriever weights), and pass dataset filters through unchanged. This keeps expansion logic within LlamaIndex abstractions (query transforms + fusion retriever) while aligning to current `HybridSearch`-style assembly and avoiding custom RRF logic. 
- **Rerank caching:** `catalog.search.rerank.Reranker` wraps `LLMRerank` directly with no caching layer. If parity requires caching, the v2 design should introduce a cache adapter around rerank calls, but the current codebase has no cache seam dedicated to rerank results. This implies the v2 plan needs to specify a cache store or reuse an existing cache utility if one exists. 
- **Snippet extraction / citation formatting:** Current search results return `chunk_text`, `chunk_seq`, and `chunk_pos` in `SearchResult`, but there is no snippet extraction helper in the Python catalog path; only FTS snippet utilities exist at the document level. The v2 design should decide whether to reuse `chunks_fts` text directly, add a snippet helper that uses chunk offsets, or extend the response shaping layer to mirror TS-style line-anchored snippets. 
- **Vector store join behavior / per-doc dedupe:** `VectorSearch` returns chunk-level results by querying `SimpleVectorStore` and then looking up chunk text in SQLite, with dataset filtering done in Python and no per-document dedupe logic beyond `top_k` truncation. If parity requires per-document best-chunk dedupe, add a postprocessing step in the v2 pipeline or use a LlamaIndex postprocessor to collapse nodes per `source_doc_id`. 
- **Docstore strategy + cache use:** The ingestion pipeline currently uses `SimpleDocumentStore` and persists pipeline state via `catalog.ingest.cache.load_pipeline` and `persist_pipeline`, but the v2 plan does not specify how docstore caching integrates with new v2 ingestion or how pipeline cache is reused across runs. V2 ingestion should explicitly reuse these cache helpers or define a replacement strategy consistent with existing ingestion semantics. 
- **Evaluation parity:** Existing tests exercise hybrid behavior with LlamaIndex fusion and reranking, but there is no golden-query Hit@K suite configured for BM25/vector/hybrid parity. A v2 evaluation plan should define datasets, metric thresholds, and test locations that align with `catalog/tests/idx` integration tests and any new `tests/rag_v2` suite.
- **Query expansion caching:** The TS system caches query expansion results in `llm_cache` keyed by hash(query+model). V2 should include a cache adapter for expansion results alongside the rerank cache, using the same cache store utility. This is distinct from rerank caching and must be addressed separately.
- **Query expansion structured output:** TS uses grammar-constrained generation to emit tagged lines (`hyde:` for hypothetical passages, `lex:` for BM25 keywords, `vec:` for semantic reformulations). V2's `LexVecQueryTransform` should produce structured output that routes expansions to the appropriate retriever (lexical vs vector), with 1-3 `lex:` lines, 1-3 `vec:` lines, and 0-1 `hyde:` lines per expansion.
- **Query expansion filtering + fallback:** TS filters expansions lacking original query terms and falls back to original query (duplicated as both lex and vec) on generation failure. V2 should implement quality filtering and graceful degradation to maintain retrieval quality when expansion fails or produces poor results.
- **RRF original query weighting:** TS weights original query results 2x in RRF fusion (first two result lists from FTS and vector get weight 2.0, expanded query results get 1.0). V2 should configure `QueryFusionRetriever` weights accordingly or implement post-fusion score adjustment to preserve this behavior.
- **RRF top-rank bonus:** After RRF fusion, TS adds bonus scores: +0.05 for rank #1, +0.02 for ranks #2-3. This protects high-confidence matches from being displaced by noisy expansions. V2 should implement an equivalent post-fusion score adjustment, either in a custom retriever or as a node postprocessor.
- **Best-chunk keyword selection:** Before reranking, TS selects the chunk with best keyword hits for each candidate document (splits query into terms > 2 chars, counts term occurrences per chunk, selects chunk with highest count). V2 should implement a node postprocessor that performs keyword-based chunk selection per `source_doc_id` before passing to the reranker.
- **MCP tools exposure:** TS exposes `qmd_search` (BM25), `qmd_vsearch` (vector), `qmd_query` (hybrid+rerank), `qmd_get` (document by path/docid), `qmd_multi_get` (batch retrieval), and `qmd_status` (index health) via MCP. V2 should define equivalent tool handlers that call the v2 search service. This may be Phase 3 scope or a separate workstream.
- **Batch embedding fallback:** TS batches 32 items for embedding and falls back to single-item embedding on batch errors for robustness. V2 embedding infrastructure should handle batch failures gracefully, retrying failed items individually rather than failing the entire batch.
- **Chunking fallback:** TS provides char-based chunking fallback (4 chars/token approximation) if token-based chunking fails. V2 should specify fallback behavior for chunking errors to ensure ingestion resilience.
- **Evaluation difficulty stratification:** TS evaluation uses difficulty categories: Easy (exact keyword matches, BM25 ≥80% Hit@3), Medium (semantic/conceptual, BM25 ≥15% Hit@3, Vector ≥40% Hit@3), Hard (vague/partial memory), and Fusion (requires both lexical AND semantic signals). V2 golden query set should include difficulty labels and stratified Hit@K thresholds per category.
- **Score normalization algorithms:** TS normalizes BM25 as `Math.abs(score)` (0 to ~25+ range) and vector as `1 - cosine_distance` (0 to 1.0 range), then blends using position-aware weights. V2 should document specific score normalization algorithms to ensure consistent ranking behavior across retrieval modes.
