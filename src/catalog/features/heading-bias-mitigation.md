# Heading Bias Mitigation for Hybrid Retrieval

## Status
Proposed

## Date
2026-02-15

## Owner
Catalog

## Summary
Catalog search currently over-rewards markdown titles and headings in several
retrieval paths. The bias originates from field leakage: heading text is mixed
into chunk content used for both FTS and embeddings, then amplified by hybrid
fusion.

This proposal introduces a body-first retrieval design with explicit heading
handling, intent-routed scoring, and metric gates to prevent regressions.

The design keeps headings useful for navigational queries while reducing
heading-only false positives in informational queries.

## Context and Current State

## Current retrieval architecture
1. Source adapters (Obsidian and Heptabase) run `MarkdownNodeParser` with
   header metadata enabled.
2. Chunk persistence stores `node.get_content()` directly in chunk FTS.
3. Embeddings are generated from transformed chunk text (with a title-aware
   embedding prefix).
4. Hybrid search combines FTS and vector results via weighted RRF.

## Relevant implementation points
1. Markdown parsing:
   - `src/catalog/catalog/integrations/obsidian/source.py`
   - `src/catalog/catalog/integrations/heptabase/reader.py`
2. Chunk persistence:
   - `src/catalog/catalog/transform/llama.py`
3. Chunk FTS schema and query:
   - `src/catalog/catalog/store/fts_chunk.py`
   - `src/catalog/catalog/search/fts_chunk.py`
4. Hybrid fusion:
   - `src/catalog/catalog/search/hybrid.py`
5. Search orchestration:
   - `src/catalog/catalog/search/service.py`
6. Evaluation harness:
   - `src/catalog/catalog/eval/golden.py`

## Failure mode
1. Heading labels are short and keyword-dense.
2. Heading lines appear in chunk text and receive strong lexical match scores.
3. The same signal influences embeddings.
4. Hybrid RRF rewards chunks ranked by both FTS and vector, compounding bias.
5. Top-k can contain many near-duplicate chunks from one document.

## Goals
1. Reduce heading-only false positives in informational queries.
2. Preserve strong note-title lookup for navigational queries.
3. Make heading influence tunable without schema ambiguity.
4. Add objective, testable metrics for heading bias.

## Non-goals
1. Replacing hybrid retrieval with a new ranking framework.
2. Adding LLM-based intent routing for this feature.
3. Preserving backward compatibility for old chunk FTS schema.

## Architecture Options Analysis

## Option A: Split body and heading into explicit fields (recommended)
Description:
1. At ingestion, split each chunk into `body_text` and `heading_text`.
2. Store both in separate FTS columns.
3. Embed body text by default.
4. Apply intent-specific column weights during query.

Pros:
1. Makes heading influence explicit and tunable.
2. Fixes root cause instead of masking symptoms.
3. Supports navigational vs informational weighting policy cleanly.

Cons:
1. Requires schema update and reindex.
2. Touches ingest and retrieval layers.

## Option B: Keep single FTS text column and tune hybrid weights only
Description:
1. Leave schema unchanged.
2. Adjust global RRF and retriever weights.

Pros:
1. Lower implementation effort.
2. No schema update.

Cons:
1. Cannot distinguish heading vs body signal in FTS.
2. Tuning remains coarse and brittle.
3. Heading leakage remains in embeddings and lexical scores.

## Option C: Rerank-only mitigation
Description:
1. Keep current retrieval unchanged.
2. Depend on reranker to demote heading-only matches.

Pros:
1. Minimal retrieval-layer changes.

Cons:
1. Slower and higher-cost path for all affected queries.
2. Does not improve base retrieval quality.
3. Increases dependence on external model behavior.

## Decision
Adopt Option A with deterministic query intent routing and per-document dedupe.
This provides direct control over heading influence and aligns with measurable
quality gates.

## Proposed Design

## 1) Chunk content model
Each indexed chunk has three views:
1. `body_text`: body evidence used for primary retrieval and embeddings.
2. `heading_text`: heading/title evidence used as controlled lexical signal.
3. `display_text`: optional original text for debugging and snippet fallback.

Rules:
1. Remove markdown heading lines from `body_text`.
2. Extract heading lines into `heading_text`.
3. If body is empty after extraction, keep empty body and preserve heading.

## 2) Ingestion and persistence changes
Introduce a deterministic chunk text splitter used by chunk persistence:
1. Input: raw chunk text from parser.
2. Output:
   - `body_text`
   - `heading_text`
3. Persist both fields to chunk FTS.

Embedding input policy:
1. Use `body_text` for embeddings when non-empty.
2. Fallback to `heading_text` only when body is empty.
3. Preserve existing embedding identity and prefixing behavior.

## 3) Chunk FTS schema update
Update `chunks_fts` to:
1. `node_id`
2. `body_text`
3. `heading_text`
4. `source_doc_id`

Use weighted BM25 call with explicit column weights. Baseline defaults:
1. Informational:
   - `node_id = 0.0`
   - `body_text = 1.0`
   - `heading_text = 0.25`
   - `source_doc_id = 0.0`
2. Navigational:
   - `node_id = 0.0`
   - `body_text = 1.0`
   - `heading_text = 0.80`
   - `source_doc_id = 0.0`

## 4) Query intent routing
Add deterministic intent classifier with two labels:
1. `informational`
2. `navigational`

Routing heuristics (rule-based):
1. Navigational if query contains path-like markers (`/`, `.md`, extension-like).
2. Navigational if query resembles note IDs or strong exact labels.
3. Navigational if short quoted exact-title query.
4. Informational otherwise.

Routing policy:
1. Informational:
   - lower heading BM25 weight
   - slightly vector-favoring hybrid weights
2. Navigational:
   - higher heading BM25 weight
   - slightly FTS-favoring hybrid weights

## 5) Hybrid retrieval and duplicate control
Apply per-document dedupe in hybrid flow:
1. Group by `source_doc_id`.
2. Keep best scoring chunk per document.
3. Continue existing top-rank bonus and optional reranking.

## 6) Snippet behavior
Snippet source order:
1. Prefer `body_text` when present.
2. Fallback to `heading_text` for heading-only chunks.

This favors evidence-bearing snippets for informational results.

## Public Interface Changes

## FTSChunkManager
1. `upsert(node_id, body_text, heading_text, source_doc_id)`
2. `search_with_scores(..., bm25_weights=(...))`

## FTSChunkRetriever
1. Accept configurable `bm25_weights`.
2. Forward weights to `FTSChunkManager.search_with_scores`.

## HybridRetriever
1. Accept per-query RRF weights and FTS BM25 profile.
2. Build retrievers with intent-routed weighting.

## SearchService
1. Add deterministic intent classifier.
2. Route retrieval profile by intent.
3. Enable per-doc dedupe in hybrid results.

## Settings additions (RAG)
Suggested settings keys:
1. `intent_routing_enabled` (bool, default true)
2. `rrf_fts_weight_informational` (float)
3. `rrf_vector_weight_informational` (float)
4. `rrf_fts_weight_navigational` (float)
5. `rrf_vector_weight_navigational` (float)
6. `fts_heading_weight_informational` (float)
7. `fts_heading_weight_navigational` (float)

## Evaluation and Regression Gates

## Existing metrics retained
1. Hit@1, Hit@3, Hit@5, Hit@10

## New metrics
1. `heading_only_hit_rate@k`
   - proportion of top-k results where matched evidence is heading-only.
2. `duplicate_doc_rate@k`
   - proportion of top-k occupied by repeated `source_doc_id`.
3. `heading_dominance_rate@k`
   - proportion where heading match is present but body evidence is absent.

## Acceptance gates
1. Heading bias metrics improve against baseline.
2. Hit@k does not regress beyond agreed threshold.
3. Navigational query behavior remains acceptable.

## Data and Migration Strategy
This is pre-alpha and may break existing local indexes.

Strategy:
1. Replace chunk FTS schema directly.
2. Re-ingest/rebuild chunk index after deployment.
3. No legacy fallback path.

## Risks and Mitigations
1. Risk: Over-downweighting headings harms navigational lookups.
   - Mitigation: Intent routing with navigational profile.
2. Risk: Heuristics misclassify some queries.
   - Mitigation: conservative defaults + config tuning + tests.
3. Risk: Schema update causes temporary local inconsistency.
   - Mitigation: explicit rebuild path and integration tests.

## Implementation Plan

## Phase 1: Ingestion and FTS structure
1. Add chunk heading/body splitter utility.
2. Update chunk FTS schema and manager API.
3. Update chunk persistence to write split fields.

## Phase 2: Retrieval routing and dedupe
1. Add query intent classifier.
2. Route BM25 and RRF weights by intent.
3. Activate per-document dedupe in hybrid flow.

## Phase 3: Evaluation hardening
1. Add heading-bias metrics to eval modules.
2. Add dedicated golden queries for heading-bias checks.
3. Add threshold gates for CI/local eval runs.

## Test Plan

## Unit tests
1. Chunk text splitter:
   - plain body chunks
   - heading-only chunks
   - mixed heading + body chunks
   - nested markdown heading sequences
2. FTS weighting:
   - weighted query generation
   - score ordering shifts with heading weight changes
3. Intent classifier:
   - navigational positive cases
   - informational positive cases
   - edge-case short queries
4. Hybrid dedupe:
   - keeps one result per `source_doc_id`

## Integration tests
1. Ingestion writes expected `body_text` and `heading_text`.
2. Informational queries favor body-evidence chunks.
3. Navigational queries retain heading/title retrieval strength.
4. Hybrid top-k duplicate pressure decreases.

## Eval tests
1. New heading-bias metrics produce deterministic output.
2. Baseline comparison enforces configured gates.

## Acceptance Criteria
1. Proposal approved by maintainers.
2. Implementation lands with passing unit and integration tests.
3. Heading-bias metrics improve versus baseline on eval corpus.
4. No unacceptable regression in existing Hit@k thresholds.

## Out of Scope Follow-ups
1. Learned intent classifier based on historical queries.
2. Cross-encoder reranker for additional quality lift.
3. Richer section-level diversity constraints.

## References
1. `src/catalog/catalog/integrations/obsidian/source.py`
2. `src/catalog/catalog/integrations/heptabase/reader.py`
3. `src/catalog/catalog/transform/llama.py`
4. `src/catalog/catalog/store/fts_chunk.py`
5. `src/catalog/catalog/search/fts_chunk.py`
6. `src/catalog/catalog/search/hybrid.py`
7. `src/catalog/catalog/search/service.py`
8. `src/catalog/catalog/eval/golden.py`

