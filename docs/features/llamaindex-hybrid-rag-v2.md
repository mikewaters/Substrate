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
| Query expansion | `QueryTransform` + `QueryFusionRetriever` | None | `catalog/search_v2/query_expansion.py` | `IDX_RAG_V2__EXPANSION_*` | Expansion quality |
| RRF weighting | Custom `NodePostprocessor` | `QueryFusionRetriever` | `catalog/search_v2/postprocessors.py` | `IDX_RAG_V2__RRF_*` | Weight tuning |
| LLM caching | Custom cache adapter | `catalog.ingest.cache` | `catalog/search_v2/cache.py` | `IDX_RAG_V2__CACHE_*` | Cache invalidation |
| MCP tools | LlamaIndex `FunctionTool` | None | `catalog/search_v2/tools.py` | tool schemas | API surface |

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

### QueryExpansionTransform
- **Purpose:** Generate structured query expansions (lex/vec/hyde) for multi-query retrieval.
- **Location:** `src/catalog/catalog/search_v2/query_expansion.py`
- **Interface:** `expand(query: str) -> QueryExpansionResult` returning tagged expansions.
- **Dependencies:** LLM provider, cache adapter.
- **Rationale:** TS uses grammar-constrained expansion; v2 uses LlamaIndex query transforms with structured output parsing.

### LLMCacheAdapter
- **Purpose:** Provide hash-keyed caching for LLM operations (query expansion, reranking).
- **Location:** `src/catalog/catalog/search_v2/cache.py`
- **Interface:** `get(key: str) -> T | None`, `set(key: str, value: T) -> None`
- **Dependencies:** SQLite via existing session utilities.
- **Rationale:** TS caches expansion and rerank results; v2 needs equivalent for latency parity.

### RRFScoreAdjustmentPostprocessor
- **Purpose:** Apply original-query weighting and top-rank bonuses after RRF fusion.
- **Location:** `src/catalog/catalog/search_v2/postprocessors.py`
- **Interface:** `postprocess_nodes(nodes, query_bundle) -> list[NodeWithScore]`
- **Dependencies:** LlamaIndex `BaseNodePostprocessor`.
- **Rationale:** LlamaIndex `QueryFusionRetriever` doesn't support per-retriever weights or rank bonuses natively.

### KeywordChunkSelector
- **Purpose:** Select best chunk per document based on keyword hits before reranking.
- **Location:** `src/catalog/catalog/search_v2/postprocessors.py`
- **Interface:** `postprocess_nodes(nodes, query_bundle) -> list[NodeWithScore]`
- **Dependencies:** LlamaIndex `BaseNodePostprocessor`.
- **Rationale:** TS picks chunk with best keyword overlap; reduces rerank cost by sending one chunk per doc.

### PerDocDedupePostprocessor
- **Purpose:** Collapse multiple chunks per document to best-scoring chunk.
- **Location:** `src/catalog/catalog/search_v2/postprocessors.py`
- **Interface:** `postprocess_nodes(nodes, query_bundle) -> list[NodeWithScore]`
- **Dependencies:** LlamaIndex `BaseNodePostprocessor`, node metadata `source_doc_id`.
- **Rationale:** Vector retrieval returns multiple chunks per doc; need one representative per doc for final ranking.

### ScoreNormalizer
- **Purpose:** Normalize BM25 and vector scores to comparable ranges before blending.
- **Location:** `src/catalog/catalog/search_v2/postprocessors.py`
- **Interface:** `normalize(nodes, retriever_type) -> list[NodeWithScore]`
- **Dependencies:** Score metadata on nodes.
- **Rationale:** BM25 scores (0-25+) and vector scores (0-1) need normalization for fair RRF.

### SnippetExtractor
- **Purpose:** Extract line-anchored snippets with diff-style headers from chunk text.
- **Location:** `src/catalog/catalog/search_v2/formatting.py`
- **Interface:** `extract_snippet(chunk_text, chunk_pos, doc_path, max_lines) -> str`
- **Dependencies:** None (pure utility).
- **Rationale:** TS returns snippets with line numbers; v2 needs equivalent for citation parity.

### MCPToolProvider
- **Purpose:** Expose v2 search capabilities as MCP tools for agent integration.
- **Location:** `src/catalog/catalog/search_v2/tools.py`
- **Interface:** LlamaIndex `FunctionTool` definitions for search, vsearch, query, get, multi_get, status.
- **Dependencies:** `SearchServiceV2`, `VectorStoreManager`.
- **Rationale:** TS exposes MCP tools; v2 needs equivalent for Claude Code/Desktop integration.

---

## Query Expansion System

### Overview
The query expansion system generates multiple query variants to improve recall. TS uses grammar-constrained LLM generation to emit tagged lines; v2 uses LlamaIndex query transforms with structured output parsing.

### QueryExpansionTransform
- **Purpose:** Generate lex/vec/hyde expansions from a single query.
- **Location:** `src/catalog/catalog/search_v2/query_expansion.py`
- **LlamaIndex abstraction:** Custom `QueryTransform` subclass.
- **Interface:**
  ```python
  class QueryExpansionTransform(QueryTransform):
      def _run(self, query_bundle: QueryBundle, metadata: dict) -> QueryBundle:
          # Returns QueryBundle with expanded query_str list

  @dataclass
  class QueryExpansionResult:
      original: str
      lex_expansions: list[str]  # 1-3 BM25 keyword variants
      vec_expansions: list[str]  # 1-3 semantic reformulations
      hyde_passage: str | None   # 0-1 hypothetical document
  ```
- **Config knobs:**
  - `IDX_RAG_V2__EXPANSION_ENABLED: bool` (default: True)
  - `IDX_RAG_V2__EXPANSION_MAX_LEX: int` (default: 3)
  - `IDX_RAG_V2__EXPANSION_MAX_VEC: int` (default: 3)
  - `IDX_RAG_V2__EXPANSION_INCLUDE_HYDE: bool` (default: True)
- **Implementation:**
  1. Call LLM with structured output prompt requesting tagged lines.
  2. Parse response into `QueryExpansionResult`.
  3. Apply quality filtering: discard expansions lacking original query terms.
  4. On failure, return fallback: original query duplicated as lex and vec.
  5. Cache result keyed by `hash(query + model_name)`.

### Query Expansion Caching
- **Purpose:** Cache expansion results to avoid redundant LLM calls.
- **Location:** `src/catalog/catalog/search_v2/cache.py`
- **LlamaIndex abstraction:** None (custom utility wrapping SQLite).
- **Interface:**
  ```python
  class LLMCacheAdapter:
      def __init__(self, session_factory, table_name: str = "llm_cache_v2"):
          ...
      def get_expansion(self, query: str, model: str) -> QueryExpansionResult | None:
          ...
      def set_expansion(self, query: str, model: str, result: QueryExpansionResult) -> None:
          ...
      def get_rerank(self, query: str, doc_hash: str, model: str) -> float | None:
          ...
      def set_rerank(self, query: str, doc_hash: str, model: str, score: float) -> None:
          ...
  ```
- **Schema:**
  ```sql
  CREATE TABLE IF NOT EXISTS llm_cache_v2 (
      cache_key TEXT PRIMARY KEY,
      cache_type TEXT NOT NULL,  -- 'expansion' | 'rerank'
      result_json TEXT NOT NULL,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
  );
  ```
- **Cache key:** SHA-256 of `f"{cache_type}:{query}:{model}:{extra}"` where extra is doc_hash for rerank.

### Query Expansion Filtering
- **Purpose:** Ensure expansions maintain query intent by requiring original terms.
- **Location:** `src/catalog/catalog/search_v2/query_expansion.py`
- **Implementation:**
  ```python
  def filter_expansions(original: str, expansions: list[str]) -> list[str]:
      original_terms = set(t.lower() for t in original.split() if len(t) > 2)
      return [
          exp for exp in expansions
          if any(term in exp.lower() for term in original_terms)
      ]
  ```
- **Fallback:** If all expansions filtered out, return `[original]`.

### Query Expansion Fallback
- **Purpose:** Graceful degradation when expansion fails.
- **Location:** `src/catalog/catalog/search_v2/query_expansion.py`
- **Implementation:**
  ```python
  def expand_with_fallback(query: str, llm, cache) -> QueryExpansionResult:
      try:
          result = expand_query(query, llm)
          if not result.lex_expansions and not result.vec_expansions:
              raise ValueError("Empty expansion")
          return result
      except Exception:
          return QueryExpansionResult(
              original=query,
              lex_expansions=[query],
              vec_expansions=[query],
              hyde_passage=None
          )
  ```

---

## RRF Fusion Enhancements

### RRF Original Query Weighting
- **Purpose:** Weight original query results 2x over expanded query results in RRF.
- **Location:** `src/catalog/catalog/search_v2/retrievers.py`
- **LlamaIndex abstraction:** Custom retriever wrapping `QueryFusionRetriever`.
- **Implementation:**
  The standard `QueryFusionRetriever` doesn't support per-query weights. Two options:

  **Option A: Duplicate original query in expansion list**
  ```python
  def build_weighted_queries(expansion: QueryExpansionResult) -> list[str]:
      queries = []
      # Original query appears twice (2x weight in RRF)
      queries.append(expansion.original)
      queries.append(expansion.original)
      # Expanded queries appear once
      queries.extend(expansion.lex_expansions)
      queries.extend(expansion.vec_expansions)
      if expansion.hyde_passage:
          queries.append(expansion.hyde_passage)
      return queries
  ```

  **Option B: Custom weighted RRF implementation**
  ```python
  class WeightedRRFRetriever(BaseRetriever):
      def __init__(self, retrievers: list[BaseRetriever], weights: list[float], k: int = 60):
          self.retrievers = retrievers
          self.weights = weights
          self.k = k

      def _retrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
          all_results = [r.retrieve(query_bundle) for r in self.retrievers]
          return self._weighted_rrf(all_results, self.weights)

      def _weighted_rrf(self, result_lists, weights) -> list[NodeWithScore]:
          scores = {}
          for results, weight in zip(result_lists, weights):
              for rank, node in enumerate(results):
                  node_id = node.node.node_id
                  rrf_score = weight / (self.k + rank + 1)
                  scores[node_id] = scores.get(node_id, 0) + rrf_score
          # Sort by score, return top results
          ...
  ```
- **Config knobs:**
  - `IDX_RAG_V2__RRF_K: int` (default: 60)
  - `IDX_RAG_V2__RRF_ORIGINAL_WEIGHT: float` (default: 2.0)
  - `IDX_RAG_V2__RRF_EXPANSION_WEIGHT: float` (default: 1.0)

### RRF Top-Rank Bonus
- **Purpose:** Protect high-confidence matches from being displaced by noisy expansions.
- **Location:** `src/catalog/catalog/search_v2/postprocessors.py`
- **LlamaIndex abstraction:** `BaseNodePostprocessor` subclass.
- **Interface:**
  ```python
  class TopRankBonusPostprocessor(BaseNodePostprocessor):
      rank_1_bonus: float = 0.05
      rank_2_3_bonus: float = 0.02

      def _postprocess_nodes(
          self, nodes: list[NodeWithScore], query_bundle: QueryBundle
      ) -> list[NodeWithScore]:
          for i, node in enumerate(nodes):
              if i == 0:
                  node.score += self.rank_1_bonus
              elif i <= 2:
                  node.score += self.rank_2_3_bonus
          return sorted(nodes, key=lambda n: n.score, reverse=True)
  ```
- **Config knobs:**
  - `IDX_RAG_V2__RRF_RANK1_BONUS: float` (default: 0.05)
  - `IDX_RAG_V2__RRF_RANK23_BONUS: float` (default: 0.02)

---

## Reranking & Chunk Selection

### Rerank Caching
- **Purpose:** Cache rerank scores to avoid redundant LLM calls for repeated query-doc pairs.
- **Location:** `src/catalog/catalog/search_v2/cache.py` (shared with expansion cache)
- **LlamaIndex abstraction:** Wrapper around `LLMRerank`.
- **Interface:**
  ```python
  class CachedReranker:
      def __init__(self, reranker: LLMRerank, cache: LLMCacheAdapter, model_name: str):
          self.reranker = reranker
          self.cache = cache
          self.model_name = model_name

      def rerank(self, query: str, nodes: list[NodeWithScore], top_n: int) -> list[NodeWithScore]:
          results = []
          uncached_nodes = []

          for node in nodes:
              doc_hash = node.node.metadata.get("content_hash", node.node.node_id)
              cached_score = self.cache.get_rerank(query, doc_hash, self.model_name)
              if cached_score is not None:
                  results.append(NodeWithScore(node=node.node, score=cached_score))
              else:
                  uncached_nodes.append(node)

          if uncached_nodes:
              reranked = self.reranker.postprocess_nodes(uncached_nodes, QueryBundle(query_str=query))
              for node in reranked:
                  doc_hash = node.node.metadata.get("content_hash", node.node.node_id)
                  self.cache.set_rerank(query, doc_hash, self.model_name, node.score)
                  results.append(node)

          return sorted(results, key=lambda n: n.score, reverse=True)[:top_n]
  ```
- **Config knobs:**
  - `IDX_RAG_V2__RERANK_CACHE_ENABLED: bool` (default: True)
  - `IDX_RAG_V2__RERANK_CACHE_TTL_HOURS: int` (default: 168, one week)

### Best-Chunk Keyword Selection
- **Purpose:** Select one representative chunk per document based on keyword overlap before reranking.
- **Location:** `src/catalog/catalog/search_v2/postprocessors.py`
- **LlamaIndex abstraction:** `BaseNodePostprocessor` subclass.
- **Interface:**
  ```python
  class KeywordChunkSelector(BaseNodePostprocessor):
      min_term_length: int = 3

      def _postprocess_nodes(
          self, nodes: list[NodeWithScore], query_bundle: QueryBundle
      ) -> list[NodeWithScore]:
          query_terms = set(
              t.lower() for t in query_bundle.query_str.split()
              if len(t) >= self.min_term_length
          )

          # Group nodes by source_doc_id
          doc_chunks: dict[str, list[NodeWithScore]] = {}
          for node in nodes:
              doc_id = node.node.metadata.get("source_doc_id", node.node.node_id)
              doc_chunks.setdefault(doc_id, []).append(node)

          # Select best chunk per doc by keyword hits
          selected = []
          for doc_id, chunks in doc_chunks.items():
              best_chunk = max(chunks, key=lambda n: self._keyword_score(n, query_terms))
              selected.append(best_chunk)

          return selected

      def _keyword_score(self, node: NodeWithScore, terms: set[str]) -> int:
          text_lower = node.node.get_content().lower()
          return sum(1 for term in terms if term in text_lower)
  ```
- **Config knobs:**
  - `IDX_RAG_V2__CHUNK_SELECT_MIN_TERM_LEN: int` (default: 3)

---

## Result Processing

### Per-Document Deduplication
- **Purpose:** Collapse multiple chunks per document to single best-scoring representative.
- **Location:** `src/catalog/catalog/search_v2/postprocessors.py`
- **LlamaIndex abstraction:** `BaseNodePostprocessor` subclass.
- **Interface:**
  ```python
  class PerDocDedupePostprocessor(BaseNodePostprocessor):
      def _postprocess_nodes(
          self, nodes: list[NodeWithScore], query_bundle: QueryBundle
      ) -> list[NodeWithScore]:
          best_per_doc: dict[str, NodeWithScore] = {}
          for node in nodes:
              doc_id = node.node.metadata.get("source_doc_id", node.node.node_id)
              if doc_id not in best_per_doc or node.score > best_per_doc[doc_id].score:
                  best_per_doc[doc_id] = node
          return list(best_per_doc.values())
  ```

### Score Normalization
- **Purpose:** Normalize BM25 and vector scores to comparable ranges for fair fusion.
- **Location:** `src/catalog/catalog/search_v2/postprocessors.py`
- **LlamaIndex abstraction:** `BaseNodePostprocessor` subclass or inline in retriever.
- **Interface:**
  ```python
  class ScoreNormalizerPostprocessor(BaseNodePostprocessor):
      retriever_type: Literal["bm25", "vector"]

      def _postprocess_nodes(
          self, nodes: list[NodeWithScore], query_bundle: QueryBundle
      ) -> list[NodeWithScore]:
          if not nodes:
              return nodes

          if self.retriever_type == "bm25":
              # BM25: scores typically 0-25+, normalize to 0-1
              max_score = max(n.score for n in nodes) or 1.0
              for node in nodes:
                  node.score = node.score / max_score
          elif self.retriever_type == "vector":
              # Vector: already 0-1 (cosine similarity), ensure consistency
              for node in nodes:
                  node.score = max(0.0, min(1.0, node.score))

          return nodes
  ```
- **Config knobs:**
  - `IDX_RAG_V2__SCORE_NORMALIZE_BM25: bool` (default: True)
  - `IDX_RAG_V2__SCORE_NORMALIZE_VECTOR: bool` (default: True)

### Snippet Extraction
- **Purpose:** Extract line-anchored snippets with diff-style headers for citations.
- **Location:** `src/catalog/catalog/search_v2/formatting.py`
- **LlamaIndex abstraction:** None (pure utility function).
- **Interface:**
  ```python
  @dataclass
  class Snippet:
      text: str
      start_line: int
      end_line: int
      header: str  # e.g., "@@ -15,10 +15,10 @@ path/to/file.md"

  def extract_snippet(
      chunk_text: str,
      chunk_pos: int,  # character offset in original doc
      doc_content: str,
      doc_path: str,
      max_lines: int = 10,
      context_lines: int = 2
  ) -> Snippet:
      # Calculate line number from character position
      lines_before = doc_content[:chunk_pos].count('\n')
      start_line = lines_before + 1

      # Extract chunk lines
      chunk_lines = chunk_text.split('\n')[:max_lines]
      end_line = start_line + len(chunk_lines) - 1

      # Build diff-style header
      header = f"@@ -{start_line},{len(chunk_lines)} +{start_line},{len(chunk_lines)} @@ {doc_path}"

      return Snippet(
          text='\n'.join(chunk_lines),
          start_line=start_line,
          end_line=end_line,
          header=header
      )
  ```
- **Config knobs:**
  - `IDX_RAG_V2__SNIPPET_MAX_LINES: int` (default: 10)
  - `IDX_RAG_V2__SNIPPET_CONTEXT_LINES: int` (default: 2)

---

## Ingestion & Caching

### Docstore Strategy
- **Purpose:** Maintain document-level deduplication across ingestion runs.
- **Location:** `src/catalog/catalog/search_v2/ingestion.py`
- **LlamaIndex abstraction:** `SimpleDocumentStore` with `DocstoreStrategy.UPSERTS_AND_DELETE`.
- **Implementation:**
  ```python
  class IngestionPipelineBuilderV2:
      def build_pipeline(self, dataset_name: str, ...) -> IngestionPipeline:
          # Load existing docstore for deduplication
          docstore = load_pipeline(dataset_name) or SimpleDocumentStore()

          pipeline = IngestionPipeline(
              transformations=[
                  PersistenceTransform(...),
                  SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap),
                  ChunkPersistenceTransform(...),
                  EmbeddingPrefixTransform(...),
              ],
              docstore=docstore,
              docstore_strategy=DocstoreStrategy.UPSERTS_AND_DELETE,
          )
          return pipeline

      def persist_pipeline_state(self, dataset_name: str, pipeline: IngestionPipeline):
          persist_pipeline(dataset_name, pipeline)
  ```
- **Reuse:** Existing `catalog.ingest.cache.load_pipeline` and `persist_pipeline` functions.

### Batch Embedding Fallback
- **Purpose:** Handle batch embedding failures gracefully by retrying individual items.
- **Location:** `src/catalog/catalog/search_v2/transforms.py`
- **LlamaIndex abstraction:** Custom `TransformComponent` wrapping embedding.
- **Interface:**
  ```python
  class ResilientEmbeddingTransform(TransformComponent):
      def __init__(self, embed_model: BaseEmbedding, batch_size: int = 32):
          self.embed_model = embed_model
          self.batch_size = batch_size

      def __call__(self, nodes: list[BaseNode], **kwargs) -> list[BaseNode]:
          # Try batch embedding
          try:
              return self._batch_embed(nodes)
          except Exception as e:
              logger.warning(f"Batch embedding failed: {e}, falling back to individual")
              return self._individual_embed(nodes)

      def _batch_embed(self, nodes: list[BaseNode]) -> list[BaseNode]:
          for i in range(0, len(nodes), self.batch_size):
              batch = nodes[i:i + self.batch_size]
              texts = [n.get_content() for n in batch]
              embeddings = self.embed_model.get_text_embedding_batch(texts)
              for node, emb in zip(batch, embeddings):
                  node.embedding = emb
          return nodes

      def _individual_embed(self, nodes: list[BaseNode]) -> list[BaseNode]:
          for node in nodes:
              try:
                  node.embedding = self.embed_model.get_text_embedding(node.get_content())
              except Exception as e:
                  logger.error(f"Failed to embed node {node.node_id}: {e}")
                  node.embedding = None  # Mark as failed
          return [n for n in nodes if n.embedding is not None]
  ```
- **Config knobs:**
  - `IDX_RAG_V2__EMBED_BATCH_SIZE: int` (default: 32)
  - `IDX_RAG_V2__EMBED_FALLBACK_ENABLED: bool` (default: True)

### Chunking Fallback
- **Purpose:** Fall back to character-based chunking if token-based fails.
- **Location:** `src/catalog/catalog/search_v2/ingestion.py`
- **LlamaIndex abstraction:** Custom splitter wrapper.
- **Interface:**
  ```python
  class ResilientSplitter(TransformComponent):
      def __init__(
          self,
          chunk_size_tokens: int = 800,
          chunk_overlap_tokens: int = 120,
          chars_per_token: int = 4
      ):
          self.token_splitter = TokenTextSplitter(
              chunk_size=chunk_size_tokens,
              chunk_overlap=chunk_overlap_tokens
          )
          self.char_splitter = SentenceSplitter(
              chunk_size=chunk_size_tokens * chars_per_token,
              chunk_overlap=chunk_overlap_tokens * chars_per_token
          )

      def __call__(self, nodes: list[BaseNode], **kwargs) -> list[BaseNode]:
          try:
              return self.token_splitter(nodes, **kwargs)
          except Exception as e:
              logger.warning(f"Token splitting failed: {e}, falling back to char-based")
              return self.char_splitter(nodes, **kwargs)
  ```
- **Config knobs:**
  - `IDX_RAG_V2__CHUNK_FALLBACK_ENABLED: bool` (default: True)
  - `IDX_RAG_V2__CHUNK_CHARS_PER_TOKEN: int` (default: 4)

---

## MCP Tools

### MCPToolProvider
- **Purpose:** Expose v2 search as MCP tools for Claude Code/Desktop integration.
- **Location:** `src/catalog/catalog/search_v2/tools.py`
- **LlamaIndex abstraction:** `FunctionTool` from `llama_index.core.tools`.
- **Interface:**
  ```python
  from llama_index.core.tools import FunctionTool

  def create_mcp_tools(search_service: SearchServiceV2) -> list[FunctionTool]:
      return [
          FunctionTool.from_defaults(
              fn=lambda query, dataset=None, limit=20: search_service.search_fts(query, dataset, limit),
              name="catalog_search",
              description="BM25 keyword search over indexed documents"
          ),
          FunctionTool.from_defaults(
              fn=lambda query, dataset=None, limit=20: search_service.search_vector(query, dataset, limit),
              name="catalog_vsearch",
              description="Semantic vector search over indexed documents"
          ),
          FunctionTool.from_defaults(
              fn=lambda query, dataset=None, limit=20, rerank=True: search_service.search_hybrid(query, dataset, limit, rerank),
              name="catalog_query",
              description="Hybrid search with RRF fusion and optional reranking (best quality)"
          ),
          FunctionTool.from_defaults(
              fn=lambda path_or_docid: search_service.get_document(path_or_docid),
              name="catalog_get",
              description="Retrieve document by path or docid"
          ),
          FunctionTool.from_defaults(
              fn=lambda pattern: search_service.get_documents(pattern),
              name="catalog_multi_get",
              description="Retrieve multiple documents by glob pattern"
          ),
          FunctionTool.from_defaults(
              fn=lambda: search_service.get_status(),
              name="catalog_status",
              description="Get index health and collection info"
          ),
      ]
  ```

### MCP Server Integration
- **Purpose:** Run catalog as MCP server process.
- **Location:** `src/catalog/catalog/search_v2/mcp_server.py`
- **Implementation:** Use `mcp` Python package or custom stdio protocol handler.
- **Config:** Claude Desktop config snippet:
  ```json
  {
    "mcpServers": {
      "catalog": {
        "command": "uv",
        "args": ["run", "python", "-m", "catalog.search_v2.mcp_server"]
      }
    }
  }
  ```

---

## Evaluation System

### Golden Query Evaluation
- **Purpose:** Measure Hit@K parity with TS system using predefined query-document pairs.
- **Location:** `tests/rag_v2/test_eval.py`
- **LlamaIndex abstraction:** None (custom test harness).
- **Interface:**
  ```python
  @dataclass
  class GoldenQuery:
      query: str
      expected_docs: list[str]  # paths or docids
      difficulty: Literal["easy", "medium", "hard", "fusion"]
      retriever_types: list[Literal["bm25", "vector", "hybrid"]]

  @dataclass
  class EvalResult:
      query: str
      difficulty: str
      retriever_type: str
      hit_at_1: bool
      hit_at_3: bool
      hit_at_5: bool
      hit_at_10: bool
      retrieved_docs: list[str]

  def evaluate_golden_queries(
      search_service: SearchServiceV2,
      golden_queries: list[GoldenQuery],
      k_values: list[int] = [1, 3, 5, 10]
  ) -> dict[str, dict[str, float]]:
      # Returns metrics grouped by difficulty and retriever_type
      ...
  ```

### Difficulty-Stratified Thresholds
- **Purpose:** Set per-difficulty Hit@K thresholds matching TS evaluation.
- **Location:** `tests/rag_v2/conftest.py`
- **Thresholds:**
  ```python
  EVAL_THRESHOLDS = {
      "bm25": {
          "easy": {"hit_at_3": 0.80},
          "medium": {"hit_at_3": 0.15},
          "hard": {"hit_at_5": 0.15},
      },
      "vector": {
          "easy": {"hit_at_3": 0.60},
          "medium": {"hit_at_3": 0.40},
          "hard": {"hit_at_5": 0.30},
      },
      "hybrid": {
          "easy": {"hit_at_3": 0.85},
          "medium": {"hit_at_3": 0.50},
          "hard": {"hit_at_5": 0.40},
          "fusion": {"hit_at_3": 0.60},
      },
  }
  ```

### Golden Query Dataset
- **Purpose:** Curated query-document pairs for evaluation.
- **Location:** `tests/rag_v2/fixtures/golden_queries.json`
- **Structure:**
  ```json
  {
    "queries": [
      {
        "query": "authentication configuration",
        "expected_docs": ["docs/auth-config.md"],
        "difficulty": "easy",
        "retriever_types": ["bm25", "vector", "hybrid"]
      },
      {
        "query": "how to set up user login",
        "expected_docs": ["docs/auth-config.md"],
        "difficulty": "medium",
        "retriever_types": ["vector", "hybrid"]
      }
    ]
  }
  ```

---

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
- **Scope:** Query expansion, RRF enhancements, reranking with caching, chunk selection.
- **Code locations:**
  - `src/catalog/catalog/search_v2/query_expansion.py`
  - `src/catalog/catalog/search_v2/postprocessors.py`
  - `src/catalog/catalog/search_v2/cache.py`
  - `src/catalog/catalog/search_v2/rerank.py`
  - `src/catalog/catalog/search_v2/transforms.py`
- **Tests:** `tests/rag_v2/test_query_expansion.py`, `tests/rag_v2/test_rerank.py`
- **Done means:** Query expansion generates lex/vec/hyde variants, RRF uses 2x weighting + top-rank bonus, reranking is cached, best-chunk selection reduces rerank candidates.

### Phase 3: Operationalization
- **Scope:** Config, MCP tools, snippet formatting, resilient ingestion.
- **Code locations:**
  - `src/catalog/catalog/core/settings.py`
  - `src/catalog/catalog/search_v2/tools.py`
  - `src/catalog/catalog/search_v2/mcp_server.py`
  - `src/catalog/catalog/search_v2/formatting.py`
- **Tests:** `tests/rag_v2/test_settings.py`, `tests/rag_v2/test_mcp_tools.py`
- **Done means:** v2 behavior is driven by `IDX_RAG_V2__*` configuration, MCP tools are exposed, snippets include line numbers.

### Phase 4: Evaluation & rollout
- **Scope:** Golden queries, side-by-side evaluation mode, difficulty stratification.
- **Code locations:**
  - `tests/rag_v2/test_eval.py`
  - `tests/rag_v2/fixtures/golden_queries.json`
  - `src/catalog/catalog/search_v2/service.py`
- **Done means:** `compare_with_v1=True` supports evaluation, golden queries pass difficulty-stratified thresholds.

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
- **Query expansion quality:** Use caching and fallback to mitigate LLM variability.
- **RRF weight tuning:** Start with TS defaults (2x original, k=60) and tune based on evaluation.

## Configuration Summary

| Config Key | Type | Default | Description |
|------------|------|---------|-------------|
| `IDX_RAG_V2__CHUNK_SIZE` | int | 800 | Tokens per chunk |
| `IDX_RAG_V2__CHUNK_OVERLAP` | int | 120 | Overlap tokens |
| `IDX_RAG_V2__CHUNK_FALLBACK_ENABLED` | bool | True | Fall back to char-based chunking |
| `IDX_RAG_V2__CHUNK_CHARS_PER_TOKEN` | int | 4 | Char/token ratio for fallback |
| `IDX_RAG_V2__EMBED_BATCH_SIZE` | int | 32 | Embedding batch size |
| `IDX_RAG_V2__EMBED_FALLBACK_ENABLED` | bool | True | Fall back to single-item embedding |
| `IDX_RAG_V2__EMBED_PREFIX_QUERY` | str | "task: search result \| query: " | Query embedding prefix |
| `IDX_RAG_V2__EMBED_PREFIX_DOC` | str | "title: {title} \| text: " | Document embedding prefix |
| `IDX_RAG_V2__EXPANSION_ENABLED` | bool | True | Enable query expansion |
| `IDX_RAG_V2__EXPANSION_MAX_LEX` | int | 3 | Max lexical expansions |
| `IDX_RAG_V2__EXPANSION_MAX_VEC` | int | 3 | Max vector expansions |
| `IDX_RAG_V2__EXPANSION_INCLUDE_HYDE` | bool | True | Include HyDE passage |
| `IDX_RAG_V2__RRF_K` | int | 60 | RRF constant |
| `IDX_RAG_V2__RRF_ORIGINAL_WEIGHT` | float | 2.0 | Original query weight |
| `IDX_RAG_V2__RRF_EXPANSION_WEIGHT` | float | 1.0 | Expanded query weight |
| `IDX_RAG_V2__RRF_RANK1_BONUS` | float | 0.05 | Rank #1 score bonus |
| `IDX_RAG_V2__RRF_RANK23_BONUS` | float | 0.02 | Rank #2-3 score bonus |
| `IDX_RAG_V2__RERANK_TOP_N` | int | 10 | Final results after rerank |
| `IDX_RAG_V2__RERANK_CANDIDATES` | int | 40 | Candidates to rerank |
| `IDX_RAG_V2__RERANK_CACHE_ENABLED` | bool | True | Enable rerank caching |
| `IDX_RAG_V2__CACHE_TTL_HOURS` | int | 168 | Cache TTL (one week) |
| `IDX_RAG_V2__SNIPPET_MAX_LINES` | int | 10 | Max lines in snippet |
| `IDX_RAG_V2__VECTOR_TOP_K` | int | 20 | Vector retrieval top-k |
| `IDX_RAG_V2__FTS_TOP_K` | int | 20 | FTS retrieval top-k |
| `IDX_RAG_V2__FUSION_TOP_K` | int | 30 | Fusion result top-k |
