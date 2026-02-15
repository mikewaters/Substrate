# Search Methods

The catalog provides multiple search methods that can be used independently or combined for optimal retrieval quality. All search is performed at the **chunk level**, returning specific passages rather than whole documents.

## Overview

| Method | Type | Best For | Speed | Recall |
|--------|------|----------|-------|--------|
| FTS | Keyword (BM25) | Exact matches, known terms | Fast | Moderate |
| Vector | Semantic | Conceptual similarity | Moderate | High |
| Hybrid | Combined (RRF) | General purpose | Moderate | High |
| Hybrid + Rerank | Combined + LLM | Highest quality | Slow | Highest |

## Search Modes

### Full-Text Search (FTS)

**Mode:** `fts`

Uses SQLite FTS5 with BM25 scoring for lexical/keyword search. Best when users know specific terms they're looking for.

```python
from catalog.search import search

results = search("python asyncio tutorial", mode="fts")
```

**How it works:**
1. Query is passed to FTS5 with standard query syntax
2. BM25 scoring ranks results by term frequency and document length
3. Results are normalized to 0-1 range

**Strengths:**
- Fast execution (pure SQL)
- Exact term matching
- Supports FTS5 query operators (`AND`, `OR`, `NOT`, `*`, `"phrase"`)

**Weaknesses:**
- No semantic understanding
- Misses synonyms and paraphrases
- Vocabulary mismatch problems

### Vector Search

**Mode:** `vector`

Uses dense embeddings for semantic similarity search. Best for conceptual queries where exact terms may not appear in documents.

```python
results = search("how to handle concurrent operations", mode="vector")
```

**How it works:**
1. Query is embedded using the configured embedding model (default: `all-MiniLM-L6-v2`)
2. Cosine similarity computed against all chunk embeddings
3. Top-k most similar chunks returned

**Strengths:**
- Semantic understanding
- Handles paraphrases and synonyms
- Works across vocabulary gaps

**Weaknesses:**
- Slower than FTS (embedding computation)
- May miss exact keyword matches
- Embedding quality affects results

### Hybrid Search

**Mode:** `hybrid` (default)

Combines FTS and vector search using Reciprocal Rank Fusion (RRF). This is the recommended default for most use cases.

```python
results = search("python async error handling", mode="hybrid")
```

**How it works:**
1. Executes both FTS and vector search in parallel
2. Applies RRF fusion: `score = sum(1 / (k + rank))` across retrievers
3. Deduplicates by chunk ID
4. Returns fused results ordered by RRF score

**RRF Formula:**
```
RRF(d) = Σ 1 / (k + rank_r(d))
```
Where `k` is typically 60 and `rank_r(d)` is the rank of document `d` in retriever `r`.

**Strengths:**
- Best of both worlds
- Robust to individual retriever failures
- No tuning of score weights required

**Weaknesses:**
- Slower than single-mode search
- May surface irrelevant results if one retriever returns noise

### LLM Reranking

**Option:** `rerank=True`

Applies LLM-as-judge reranking to hybrid search results. Use when quality matters more than latency.

```python
results = search(
    "best practices for async python",
    mode="hybrid",
    rerank=True,
    rerank_candidates=20,  # Candidates to send to LLM
    limit=5,               # Final results after reranking
)
```

**How it works:**
1. Hybrid search retrieves `rerank_candidates` results (default: 20)
2. LLM evaluates relevance of each candidate to the query
3. Results reordered by LLM relevance scores
4. Top `limit` results returned

**Strengths:**
- Highest quality relevance ranking
- Understands nuanced query intent
- Can filter out false positives

**Weaknesses:**
- Slowest option (LLM API calls)
- Costs money (API usage)
- Latency ~1-3 seconds

## Usage

### Simple API

```python
from catalog.search import search

# Default hybrid search
results = search("machine learning concepts", limit=10)

# FTS only
results = search("asyncio", mode="fts", limit=20)

# Vector only with dataset filter
results = search("meeting notes", mode="vector", dataset_name="obsidian")

# Hybrid with reranking
results = search(
    "python error handling patterns",
    mode="hybrid",
    rerank=True,
    limit=5,
)
```

### SearchService API

For more control, use `SearchService` directly:

```python
from catalog.search import SearchService, SearchCriteria
from catalog.store.database import get_session
from catalog.store.session_context import use_session

with get_session() as session:
    with use_session(session):
        service = SearchService(debug=True)

        results = service.search(SearchCriteria(
            query="python tutorials",
            mode="hybrid",
            dataset_name="obsidian",
            limit=10,
            rerank=True,
            rerank_candidates=30,
        ))

        for r in results.results:
            print(f"{r.path}: {r.score:.3f}")
            print(f"  Chunk: {r.chunk_text[:100]}...")
```

## Result Structure

Each `SearchResult` contains:

| Field | Type | Description |
|-------|------|-------------|
| `path` | str | Document path within dataset |
| `dataset_name` | str | Source dataset name |
| `score` | float | Final relevance score (0-1) |
| `chunk_text` | str | Matched chunk content |
| `chunk_seq` | int | Chunk sequence within document |
| `chunk_pos` | int | Byte offset in original document |
| `metadata` | dict | Document metadata (frontmatter, etc.) |
| `scores` | dict | Component scores: `fts`, `vector`, `rrf`, `rerank` |

## Index Architecture

### Document-Level FTS (`documents_fts`)

Full-text index on complete document content. Used by `FTSSearch` for document-level queries.

### Chunk-Level FTS (`chunks_fts`)

Full-text index on chunked content. Used by `FTSChunkRetriever` for hybrid search.

### Vector Store (`default__vector_store.json`)

Embeddings for all chunks. Used by `VectorSearch` and hybrid search.

## Configuration

### Embedding Model

Configured via environment or settings:

```python
# Default: all-MiniLM-L6-v2 (384 dimensions)
# Backend: mlx (Apple Silicon) or huggingface
```

### Vector Backend Selection

Qdrant remains the default vector backend.

To run an experimental production trial with Zvec, set:

```bash
IDX_VECTOR_DB__BACKEND=zvec
IDX_VECTOR_DB__ENABLE_EXPERIMENTAL_ZVEC=true
IDX_ZVEC__ENDPOINT=http://<zvec-host>:8000
IDX_ZVEC__COLLECTION_NAME=catalog_vectors
IDX_ZVEC__TIMEOUT_SECONDS=5
```

Notes:
- If `IDX_VECTOR_DB__ENABLE_EXPERIMENTAL_ZVEC` is not `true`, startup fails when
  backend is set to `zvec`.
- Keep Qdrant settings unchanged for rollback by restoring
  `IDX_VECTOR_DB__BACKEND=qdrant`.

### Chunking

Documents are split using `SentenceSplitter`:
- Default chunk size: 768 tokens
- Default overlap: 96 tokens

### Reranking LLM

Default: `gpt-4o-mini` with temperature=0.0

## Performance Considerations

1. **First query latency**: Vector store and embedding model are lazy-loaded. First query will be slower.

2. **Dataset filtering**: When filtering by dataset, vector search fetches 3x candidates to account for filtering.

3. **Reranking cost**: Each rerank call makes LLM API requests. Batch size of 5 nodes per call.

4. **Index size**: Vector store grows with document count. Consider cleanup for large datasets.

## Troubleshooting

### No results returned

1. Check dataset exists: `bd list` or query `datasets` table
2. Verify documents were indexed: check `documents_created` in ingest result
3. Try FTS mode to rule out embedding issues

### Poor relevance

1. Try hybrid mode instead of single-mode search
2. Enable reranking for highest quality
3. Check chunk size - too small may lose context

### Slow search

1. Ensure vector store is persisted (avoid reload on each query)
2. Reduce `rerank_candidates` if using reranking
3. Consider FTS-only for latency-critical paths
