# Heading Bias Mitigation for Hybrid Retrieval

## Context
Chunk text from `MarkdownNodeParser` includes heading lines mixed into body content. This goes to both FTS (`text` column) and embeddings, causing heading-keyword-dense chunks to dominate BM25 and compound through RRF fusion. The existing `_split_frontmatter_title()` only extracts YAML frontmatter titles into a separate column - markdown heading lines (`# Heading`) remain in the `text` column.

The feature spec is at `src/catalog/features/heading-bias-mitigation.md`.

---

## Phase 1: Ingestion and FTS Structure

### 1a. Add heading/body splitter utility
**File**: `src/catalog/catalog/store/fts_chunk.py`

Add `extract_heading_body(text: str) -> tuple[str, str]` that:
1. Calls existing `_split_frontmatter_title(text)` to get YAML title + remaining text
2. Regex-extracts markdown heading lines (`^#{1,6}\s+.+$`) from remaining text
3. Combines frontmatter title + stripped heading text into `heading_text`
4. Returns `(heading_text, body_text)` where body has heading lines removed

This replaces the current `_split_frontmatter_title` call inside `upsert()`.

### 1b. Update FTS schema
**File**: `src/catalog/catalog/store/fts_chunk.py`

Replace `create_chunks_fts_table()` schema:
- Current: `(node_id, title, text, source_doc_id)`
- New: `(node_id, heading_text, body_text, source_doc_id)`

### 1c. Update `FTSChunkManager.upsert()`
**File**: `src/catalog/catalog/store/fts_chunk.py`

New signature: `upsert(node_id, text, source_doc_id)` - keep same params but internally call `extract_heading_body(text)` and INSERT into new column names. The caller doesn't need to change.

### 1d. Update `FTSChunkManager.search_with_scores()`
**File**: `src/catalog/catalog/store/fts_chunk.py`

- Add `bm25_weights: str | None = None` parameter
- Default weights: `"0.0, 0.25, 1.0, 0.0"` for `(node_id, heading_text, body_text, source_doc_id)` - informational baseline
- SELECT `body_text` instead of `text` for result text
- Build `FTSChunkResult` from `body_text` column

### 1e. Update `ChunkPersistenceTransform._process_chunk()`
**File**: `src/catalog/catalog/transform/llama.py` (line 830)

- After getting `text = node.get_content()`, call `extract_heading_body(text)`
- Store `heading_text` and `body_text` in node metadata for downstream use
- Set `node.set_content(body_text if body_text.strip() else heading_text)` so embeddings use body-only text
- FTS upsert stays the same (still passes full `text`, splitter runs inside upsert)

### 1f. Update `FTSChunkRetriever._retrieve()`
**File**: `src/catalog/catalog/search/fts_chunk.py`

- Add `bm25_weights: str | None = None` to constructor
- Pass `bm25_weights` through to `search_with_scores()`

---

## Phase 2: Retrieval Routing and Dedupe

### 2a. Create intent classifier
**New file**: `src/catalog/catalog/search/intent.py`

`classify_intent(query: str) -> Literal["informational", "navigational"]`

Rule-based heuristics:
- Navigational if quoted strings present
- Navigational if short query (<=3 tokens) with internal capitals (CamelCase, PROJ-1234)
- Navigational if matches doc-name patterns (`[A-Z]+-\d+`, CamelCase)
- Informational otherwise

### 2b. Add intent-based settings
**File**: `src/catalog/catalog/core/settings.py` (RAGSettings class)

New fields:
```
bm25_heading_weight_informational: float = 0.25
bm25_heading_weight_navigational: float = 0.80
rrf_fts_weight_informational: float = 1.5
rrf_vector_weight_informational: float = 2.0
rrf_fts_weight_navigational: float = 2.5
rrf_vector_weight_navigational: float = 1.0
hybrid_dedupe_enabled: bool = True
```

### 2c. Update `FTSChunkRetriever` for intent
**File**: `src/catalog/catalog/search/fts_chunk.py`

- Add `query_intent` param to constructor
- In `_retrieve()`, resolve BM25 weights from settings based on intent
- Build weights string: `f"0.0, {heading_weight}, 1.0, 0.0"` where `heading_weight` comes from settings per intent

### 2d. Update `WeightedRRFRetriever` for per-doc dedupe
**File**: `src/catalog/catalog/search/hybrid.py`

- Add `enable_dedupe: bool = False` to constructor
- At end of `_retrieve()`, if enabled, apply existing `PerDocDedupePostprocessor` from `catalog/search/postprocessors.py`

### 2e. Update `HybridRetriever.build()` for intent routing
**File**: `src/catalog/catalog/search/hybrid.py`

- Add `query_intent` param
- Route RRF weights (`fts_weight`, `vector_weight`) from settings based on intent
- Pass `query_intent` to `FTSChunkRetriever` constructor
- Pass `enable_dedupe=settings.hybrid_dedupe_enabled` to `WeightedRRFRetriever`

### 2f. Update `SearchService.search()` for intent
**File**: `src/catalog/catalog/search/service.py`

- Classify intent at top of `search()` for hybrid/fts modes
- Pass `query_intent` to `search_hybrid()` -> `hybrid_factory.build()`

---

## Phase 3: Evaluation Hardening

### 3a. Create heading bias metrics
**New file**: `src/catalog/catalog/eval/heading_bias.py`

Metrics computed from search results:
- `heading_only_hit_rate@k` - fraction of top-k where body_text is empty
- `duplicate_doc_rate@k` - fraction of top-k with repeated source_doc_id
- `heading_dominance_rate@k` - fraction where heading chunk outranks body chunk from same doc

### 3b. Integrate metrics into eval harness
**File**: `src/catalog/catalog/eval/golden.py`

- Add `heading_bias: HeadingBiasMetrics | None` to `EvalResult`
- Compute heading bias metrics during `evaluate_golden_queries()`
- Add `HEADING_BIAS_THRESHOLDS` dict

### 3c. Add heading-bias golden queries
**New file**: `src/catalog/tests/rag_v2/fixtures/heading_bias_queries.json`

Queries targeting heading-bias edge cases (informational queries that currently false-positive on headings, navigational queries that should still work).

---

## Test Plan

### Unit tests
| Test file | What it covers |
|-----------|---------------|
| `tests/idx/unit/store/test_heading_split.py` | `extract_heading_body()`: plain body, heading-only, mixed, nested headings, frontmatter+headings, non-heading `#` symbols |
| `tests/idx/unit/search/test_intent.py` | `classify_intent()`: quoted, CamelCase, JIRA-style, short caps, long lowercase, edge cases |
| `tests/idx/unit/search/test_fts_weights.py` | BM25 weight routing by intent, score ordering with different weights |
| `tests/idx/unit/search/test_hybrid_dedupe.py` | Per-doc dedupe keeps one result per `source_doc_id` |

### Integration tests
| Test file | What it covers |
|-----------|---------------|
| `tests/idx/integration/test_heading_bias.py` | End-to-end: ingest markdown with headings, verify `heading_text`/`body_text` split in FTS, verify informational queries prefer body matches, verify navigational queries retain heading strength, verify dedupe reduces duplicates |

### Verification
1. `make agent-test` - run differential tests
2. `make agent-test TESTPATH=tests/idx/unit/store` - heading splitter tests
3. `make agent-test TESTPATH=tests/idx/unit/search` - intent + FTS weight tests
4. `make agent-test TESTPATH=tests/idx/integration` - integration tests

---

## Key files to modify
- `src/catalog/catalog/store/fts_chunk.py` - schema, splitter, upsert, search
- `src/catalog/catalog/transform/llama.py` - embedding text = body only
- `src/catalog/catalog/search/fts_chunk.py` - BM25 weight routing
- `src/catalog/catalog/search/hybrid.py` - intent RRF weights + dedupe
- `src/catalog/catalog/search/service.py` - intent classification entry point
- `src/catalog/catalog/core/settings.py` - new RAG settings

## New files to create
- `src/catalog/catalog/search/intent.py` - intent classifier
- `src/catalog/catalog/eval/heading_bias.py` - bias metrics
- Test files listed above

## Existing utilities to reuse
- `_split_frontmatter_title()` in `store/fts_chunk.py` - called by new `extract_heading_body()`
- `PerDocDedupePostprocessor` in `search/postprocessors.py` - used in RRF dedupe step
- `_sanitize_fts5_query()` in `store/fts_chunk.py` - unchanged, still used in search
