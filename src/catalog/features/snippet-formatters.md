Feb 15, 2026 (America/New_York)
Nancy — GPT-5.2 Thinking

Below is a software-architect-ready output artifact: **result schema + per-mode snippet pipelines**, tuned for **performance-first defaults** while preserving **accuracy** and a **future sanitization hook**.

---

## Artifact: Snippet Handling Requirements & Design (High-Level)

### Goals

* **Performance-first default**: avoid extra datastore round-trips per hit; prefer returning snippet text already available from the retrieval system.
* **Accuracy**: snippet should reflect *what was retrieved/scored* (especially for vector + rerank).
* **Spans-based highlighting**: supported as an option (`include_spans`), not mandatory for the fast path.
* **Future sanitization**: design must allow a redaction/sanitization step without forcing it now.
* **English-only** (search/tokenization assumptions).

References: SQLite FTS5 snippet/highlight functions  and Qdrant payload concept .

---

## 1) Public Result Schema (API-level)

### `SearchResponse`

```json
{
  "query": "string",
  "mode": "fts | vector | hybrid | hybrid_rerank",
  "took_ms": 12,
  "results": [ /* SearchResult[] */ ],
  "debug": { /* optional */ }
}
```

### `SearchResult`

```json
{
  "result_id": "string",              // stable per retrieval unit (chunk/passage strongly recommended)
  "doc_id": "string",
  "score": 0.0,
  "rank": 1,

  "snippet": {
    "text": "string",
    "spans": [ { "start": 10, "end": 22, "type": "match" } ],  // optional
    "source": "stored_chunk | fts_window | preview | python_excerpt",
    "sanitized": false,
    "truncated": true,
    "meta": {
      "chunk_id": "string",
      "chunk_start_char": 12345,      // optional but recommended for traceability
      "chunk_end_char": 12567
    }
  },

  "metadata": {
    "title": "string",
    "uri": "string",
    "created_at": "2026-02-01T00:00:00Z"
  }
}
```

### Notes (architectural)

* **Retrieval unit**: strongly recommend `result_id == chunk_id` (passage-based). This makes vector, hybrid, and rerank snippets “free” (the passage text itself).
* `snippet.source` is critical: it lets clients and future ADRs reason about provenance and consistency across modes.
* `snippet.spans` are **relative to `snippet.text`**. (No HTML markup.)

---

## 2) Request Controls (API-level)

### `SearchRequest` snippet options

```json
{
  "query": "string",
  "mode": "fts | vector | hybrid | hybrid_rerank",

  "top_k": 10,

  "snippet": {
    "strategy": "default | stored_chunk | fts_window | preview",
    "max_chars": 320,
    "include_spans": false,
    "span_max": 20,
    "sanitize": "off | hook"          // "hook" calls a sanitizer interface; may be no-op now
  },

  "hybrid": {
    "candidate_k_fts": 50,
    "candidate_k_vec": 50,
    "fusion": "rrf"
  },

  "rerank": {
    "enabled": false,
    "candidate_k": 100
  }
}
```

### Defaults (perf + accuracy oriented)

* `snippet.strategy = "default"`
* `default` resolves to:

  * **FTS**: `fts_window` *or* `stored_chunk` (see “FTS choice” below)
  * **Vector/Hybrid/Hybrid_rerank**: `stored_chunk`
* `include_spans = false` (fast path)
* `sanitize = off` (but sanitizer hook exists)

---

## 3) Internal Interfaces (for architect)

### `SnippetSanitizer` (future-proof hook)

```text
sanitize(text: string, context: {doc_id, chunk_id, mode, query}): { text: string, sanitized: bool }
```

### `SpanExtractor` (optional, fast/cheap)

```text
extract_spans(text: string, query: string, max_spans: int): Span[]
```

Notes:

* Keep span extraction cheap and bounded (max spans, max chars).
* English-only allows a simple tokenizer-based span finder; don’t try to match FTS semantics perfectly.

---

## 4) Mode-specific Pipelines (pseudocode)

### Shared helper

```text
post_process_snippet(snippet_text, req, context):
    if req.snippet.max_chars: snippet_text = truncate(snippet_text, req.snippet.max_chars)
    spans = []
    if req.snippet.include_spans:
        spans = SpanExtractor.extract_spans(snippet_text, req.query, req.snippet.span_max)
    sanitized = false
    if req.snippet.sanitize == "hook":
        out = SnippetSanitizer.sanitize(snippet_text, context)
        snippet_text = out.text
        sanitized = out.sanitized
        if req.snippet.include_spans:
            spans = SpanExtractor.extract_spans(snippet_text, req.query, req.snippet.span_max)  // recompute after sanitize
    return {text: snippet_text, spans, sanitized}
```

---

### A) FTS mode (SQLite FTS5)

SQLite FTS5 supports generating query-aware snippets via `snippet()` and highlighting via `highlight()`.

**FTS strategy choice (performance vs consistency)**

* **Option FTS-1 (best lexical UX):** use FTS5 `snippet()` for `fts_window`
* **Option FTS-2 (best cross-mode consistency):** return `stored_chunk` text (if your FTS index is over chunks)

#### FTS pipeline (FTS-1)

```text
fts_search(req):
    rows = sqlite_fts_query(
        query=req.query,
        limit=req.top_k,
        select=[
          doc_id, chunk_id, score,
          snippet_text = fts5_snippet(table, ... params ...)   // from FTS5
        ]
    )

    for each row:
        snippet = post_process_snippet(row.snippet_text, req, context={doc_id, chunk_id, mode:"fts"})
        emit SearchResult(result_id=chunk_id, doc_id=doc_id, score=row.score, snippet.source="fts_window", snippet.text=snippet.text, snippet.spans=snippet.spans, snippet.sanitized=snippet.sanitized)
```

#### FTS pipeline (FTS-2)

```text
fts_search(req):
    rows = sqlite_fts_query(query=req.query, limit=req.top_k, select=[doc_id, chunk_id, score, chunk_text])
    for each row:
        snippet = post_process_snippet(row.chunk_text, req, context={doc_id, chunk_id, mode:"fts"})
        emit ... snippet.source="stored_chunk"
```

**Recommendation for perf+accuracy overall:**

* If your system is chunk-based, default FTS to **FTS-2** (`stored_chunk`) for maximum uniformity and minimal complexity; keep **FTS-1** as an opt-in strategy.

---

### B) Vector mode (Qdrant)

Qdrant points can store payload fields like `chunk_text` alongside the vector.

```text
vector_search(req):
    points = qdrant_search(
        query_vector=embed(req.query),
        limit=req.top_k,
        with_payload=["doc_id", "chunk_id", "chunk_text", "chunk_start_char", "chunk_end_char"]
    )

    for each point:
        snippet = post_process_snippet(point.payload.chunk_text, req, context={doc_id, chunk_id, mode:"vector"})
        emit SearchResult(result_id=chunk_id, doc_id=doc_id, score=point.score,
            snippet.source="stored_chunk",
            snippet.meta={chunk_id, chunk_start_char, chunk_end_char},
            snippet.text=snippet.text, snippet.spans=snippet.spans, snippet.sanitized=snippet.sanitized)
```

---

### C) Hybrid mode (FTS + vector, no rerank)

Use rank fusion (e.g., Reciprocal Rank Fusion) to combine rankings without score normalization assumptions; it’s a common hybrid approach.

```text
hybrid_search(req):
    fts_candidates = fts_search_internal(req.query, k=req.hybrid.candidate_k_fts)       // returns chunk_id + score + optional chunk_text/snippet
    vec_candidates = vector_search_internal(req.query, k=req.hybrid.candidate_k_vec)   // returns chunk_id + score + chunk_text

    fused = fuse_rrf(fts_candidates, vec_candidates)  // produces ordered chunk_ids

    top = take(fused, req.top_k)

    for each item in top:
        // prefer stored chunk_text if available (accuracy: passage that ranked)
        chunk_text = item.chunk_text if present else fetch_chunk_text(item.chunk_id)   // goal: avoid this fetch by ensuring availability
        snippet = post_process_snippet(chunk_text, req, context={doc_id, chunk_id, mode:"hybrid"})
        emit ... snippet.source="stored_chunk"
```

**Perf requirement for architect:**

* Ensure both internal candidate retrievals return **chunk_text in-band**, so hybrid does **zero extra fetches**.

---

### D) Hybrid + rerank (retrieve → fuse → rerank)

This is the standard retrieve-then-rerank architecture used widely with cross-encoders.

```text
hybrid_rerank_search(req):
    fts_candidates = fts_search_internal(req.query, k=req.rerank.candidate_k/2)
    vec_candidates = vector_search_internal(req.query, k=req.rerank.candidate_k/2)

    fused_candidates = fuse_rrf(fts_candidates, vec_candidates)
    candidates = take(fused_candidates, req.rerank.candidate_k)

    // reranker scores query + chunk_text pairs
    reranked = cross_encoder_rerank(query=req.query, passages=[c.chunk_text for c in candidates])

    top = take(reranked, req.top_k)

    for each c in top:
        snippet = post_process_snippet(c.chunk_text, req, context={doc_id, chunk_id, mode:"hybrid_rerank"})
        emit ... snippet.source="stored_chunk"
```

**Accuracy note:** snippet is the exact passage reranked, which is the most faithful explanation of “why this result”.

---

## 5) Non-functional Requirements (to hand to architect)

1. **No extra reads on default path**

   * Vector/hybrid/rerank must return `chunk_text` in-band (payload or joined select).
2. **Bounded work per result**

   * `max_chars`, `span_max`, and optional sanitization ensure predictable latency.
3. **Deterministic snippet**

   * Same inputs → same snippet output, to enable caching.
4. **Observability hooks**

   * record `snippet.source`, whether spans/sanitization ran, and truncate counts (for perf tuning).

---

## 6) Open Questions (explicitly for ADR follow-up)

* Multiple fields (title/body) snippet selection policy (kept open as requested).
* Whether FTS default should be `stored_chunk` (consistency) or `fts_window` (best lexical UX) — both supported via `snippet.strategy`.

---

### Citations

* SQLite FTS5 auxiliary functions (`snippet`, `highlight`) for query-aware excerpts.
* Qdrant payload concept for storing `chunk_text` alongside vectors.
* Hybrid rank fusion (RRF) as a common approach for hybrid retrieval.
* Retrieve-then-rerank / cross-encoder reranking pattern.

