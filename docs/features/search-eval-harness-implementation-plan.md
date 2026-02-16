# Search Eval Harness Implementation Plan

This plan operationalizes the golden query evaluation harness described in
`/Users/mike/Develop/lifeos/substrate/docs/features/search-eval-harness.md`.
It focuses on a repeatable, versioned evaluation workflow that can run in CI
and locally without touching developer or production data.

---

## Scope

Implement a reproducible evaluation workflow that:

- Ingests a fixed corpus into an isolated eval database.
- Runs golden query evaluation across retriever modes.
- Emits a run record artifact with metadata and metrics.
- Compares results against baselines and enforces thresholds.
- Integrates into CI with clear gating behavior.

Out of scope:

- Production load testing.
- UI-level validation.
- Full benchmark suite against large corpora.

---

## Inputs and Artifacts

### Fixed Inputs

- Corpus: `/Users/mike/Develop/lifeos/substrate/src/catalog/tests/corpus/vault-small`
- Golden queries: `/Users/mike/Develop/lifeos/substrate/src/catalog/tests/rag_v2/fixtures/golden_queries.json`
- Eval CLI: `uv run python -m catalog eval golden`

### Generated Artifacts

- Run record JSON files (one per run)
- Optional baseline JSON files per configuration

Recommended output location:

- `reports/evals/YYYY-MM-DD/<run-id>.json`

Do not store run records under `src/catalog/tests/` to avoid test discovery.

---

## Design Overview

The eval harness is a thin orchestration layer that wraps existing ingestion
and evaluation components. It should:

1. Create isolated paths for catalog DB, content DB, and vector store.
2. Ingest the fixed corpus into those paths using the existing ingest script.
3. Run `catalog eval golden` against the ingested dataset.
4. Capture CLI JSON output and wrap it in a run record envelope.
5. Compare current run to a baseline using thresholds or direct diffing.

The existing `catalog.eval.golden` logic remains authoritative for metrics.

---

## Implementation Steps

### Phase 1: Baseline Harness Script

Create a small, self-contained script in `scripts/` that:

1. Accepts arguments:
   - corpus path
   - queries file path
   - output directory
   - dataset name (default `eval-vault`)
   - embedding model id
   - vector store path
   - catalog/content db paths
   - optional flag to compare against baseline
2. Sets env vars:
   - `SUBSTRATE_DATABASES_CATALOG_PATH`
   - `SUBSTRATE_DATABASES_CONTENT_PATH`
   - `SUBSTRATE_VECTOR_STORE_PATH`
   - `SUBSTRATE_EMBEDDING_MODEL`
3. Calls ingest:
   - `uv run python scripts/ingest_obsidian_vault.py <corpus> --dataset-name <name>`
4. Calls eval:
   - `uv run python -m catalog eval golden --queries-file <file> --output json`
5. Creates a run record envelope and writes JSON to output directory.

Deliverable:

- `scripts/run_search_eval.py` (name can be finalized in implementation).

### Phase 2: Run Record Envelope

Define a canonical run record schema (JSON) with:

- `run_id` (ISO8601 timestamp)
- `git.commit`, `git.branch`, `git.dirty`
- `corpus.path`, `corpus.hash`
- `queries.path`, `queries.version`
- `settings.embedding_model`, `settings.fts_impl`, `settings.rag_v2`
- `metrics` (the existing golden evaluation output)

### Phase 3: Baseline Management

Provide a baseline selection strategy:

- Key by `corpus.hash + queries.version + embedding_model + fts_impl + rag_v2 settings`.
- Store baseline in `reports/evals/baselines/<key>.json`.

Provide a comparison mode that:

- Loads the baseline.
- Compares metrics (hit@k per retriever/difficulty).
- Enforces thresholds (use the existing `EVAL_THRESHOLDS` as default).

### Phase 4: CI Integration

Add a CI job that:

1. Runs the eval harness script with pinned paths.
2. Stores the run record as a build artifact.
3. Fails the job if thresholds are not met.

CI should set environment variables explicitly to avoid coupling to local
machine defaults.

---

## Detailed Behavior

### Corpus Hashing

Compute a corpus hash using a stable file-walk with sorted paths and content
hashing (sha256). Store the corpus hash in the run record.

### Golden Query Version

Read `version` from the golden queries JSON. Include it in the run record
and baseline key. This ensures changes to queries force new baselines.

### RAG v2 Settings Capture

Record the RAG v2 settings that affect retrieval:

- chunk_size
- chunk_overlap
- rrf_k
- rerank_enabled
- expansion_enabled

Source values from `catalog.core.settings.Settings` at runtime.

---

## Outputs and Reports

### Run Record

Example file name:

- `reports/evals/2026-02-08/2026-02-08T20-15-00Z.json`

### Human Summary (Optional)

Generate a small summary table alongside the JSON:

- `reports/evals/2026-02-08/summary.txt`

Include:

- counts of queries per difficulty
- hit@1/3/5/10 per retriever type
- baseline comparison results

---

## Threshold Strategy

Default thresholds should come from `catalog.eval.golden.EVAL_THRESHOLDS`.

Guidance:

- FTS-only should be stable; tighten thresholds.
- Vector and hybrid allow drift; use slightly lower thresholds.

If thresholds are violated, the harness should exit non-zero in CI.

---

## Migration and Rollout

1. Land the harness script and doc changes.
2. Run a first baseline locally for current embedding/FTS settings.
3. Store baseline artifacts in a controlled location.
4. Enable CI gating with explicit thresholds.
5. Establish a process for baseline updates when intentional changes land.

---

## Testing Strategy

- Unit test corpus hashing and run record serialization.
- Unit test baseline comparison logic and threshold enforcement.
- Integration test can be skipped by default to avoid runtime cost.

---

## Risks and Mitigations

- Risk: embedding drift causes false regressions.
  - Mitigation: baseline by model id and allow drift thresholds.

- Risk: corpus changes invalidate historical comparison.
  - Mitigation: hash the corpus and treat updates as new baselines.

- Risk: harness impacts developer local DBs.
  - Mitigation: enforce explicit isolated paths in script.

---

## Open Questions

- Should we support multiple corpora (domain-specific eval packs)?
- Should we store baselines in repo or in external storage?
- Do we want per-query outputs for deeper diagnostics?

---

## Success Criteria

- A developer can run the harness locally with one command.
- CI gates pull requests on threshold regressions.
- Run records are comparable across time, models, and code changes.
