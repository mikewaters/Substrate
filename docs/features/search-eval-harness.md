# Search Evaluation Harness (Golden Queries)

This document defines the recommended approach for longitudinal evaluation
of catalog search quality. It is designed to detect regressions when any of the
following change:

- Embedding model or embedding backend
- FTS implementation or configuration
- RAG v2 settings (chunking, fusion, reranking)
- Search service code or indexing pipelines

The harness is intentionally deterministic, small, and repeatable so it can
run in CI and during local development without touching developer or production
Databases.

---

## Goals

1. Provide stable, repeatable search quality metrics over time.
2. Make regressions easy to detect and diagnose.
3. Separate FTS-only, vector-only, and hybrid evaluations.
4. Record enough metadata to compare runs across models and code versions.

## Non-Goals

- This harness does not measure end-user latency at scale.
- It does not validate all UI integration paths.
- It does not attempt to reproduce production data distributions.

---

## Core Concept

We evaluate search quality using golden queries: a fixed set of queries with
expected document matches. Each run executes those queries against a fixed
corpus that is ingested into a dedicated eval database, then aggregates hit@k
metrics by retriever type and difficulty.

This is already supported by `catalog.eval.golden` and the CLI:

- Golden queries: `/Users/mike/Develop/lifeos/substrate/src/catalog/tests/rag_v2/fixtures/golden_queries.json`
- CLI command: `uv run python -m catalog eval golden`

---

## Inputs

### 1) Fixed Corpus

Use a stable, version-controlled corpus. Recommended:

- `/Users/mike/Develop/lifeos/substrate/src/catalog/tests/corpus/vault-small`

This corpus is small and deterministic, which makes results stable and fast.

### 2) Golden Queries

The current fixture is:

- `/Users/mike/Develop/lifeos/substrate/src/catalog/tests/rag_v2/fixtures/golden_queries.json`

This file already contains:

- `version` and `description`
- `queries`: each with `query`, `expected_docs`, `difficulty`, `retriever_types`

If you add or modify queries, you should treat the file as versioned:

- Bump the `version`.
- Record a short description of what changed.
- Preserve the old file if you need historical comparability.

---

## Environment Isolation

The evaluation harness must never use a developer's default database. Use
Dedicated paths set via environment variables.

Recommended variables (from `catalog.core.settings`):

- `IDX_DATABASES_CATALOG_PATH` (catalog DB)
- `IDX_DATABASES_CONTENT_PATH` (content DB)
- `IDX_VECTOR_STORE_PATH` (vector store persistence path)
- `IDX_EMBEDDING_MODEL` (embedding model id)
- `IDX_TRANSFORMERS_MODEL` (reranker model id, if used)

Example environment for local evaluation:

```bash
export IDX_DATABASES_CATALOG_PATH=/tmp/catalog-eval/catalog.db
export IDX_DATABASES_CONTENT_PATH=/tmp/catalog-eval/content.db
export IDX_VECTOR_STORE_PATH=/tmp/catalog-eval/vectors
export IDX_EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
```

---

## Execution Flow

### Step 1: Ingest the Fixed Corpus

Use the existing ingest script with a dedicated dataset name. This writes into
The isolated eval database and vector store paths.

```bash
uv run python scripts/ingest_obsidian_vault.py \
  /Users/mike/Develop/lifeos/substrate/src/catalog/tests/corpus/vault-small \
  --dataset-name eval-vault
```

### Step 2: Run Golden Query Evaluation

```bash
uv run python -m catalog eval golden \
  --queries-file /Users/mike/Develop/lifeos/substrate/src/catalog/tests/rag_v2/fixtures/golden_queries.json \
  --output json
```

Optional threshold gating:

```bash
uv run python -m catalog eval golden \
  --queries-file /Users/mike/Develop/lifeos/substrate/src/catalog/tests/rag_v2/fixtures/golden_queries.json \
  --output json \
  --check
```

Thresholds are defined in:

- `/Users/mike/Develop/lifeos/substrate/src/catalog/catalog/eval/golden.py`

---

## Metrics

The evaluator aggregates hit@k metrics by:

- `retriever_type` (bm25, vector, hybrid)
- `difficulty` (easy, medium, hard, fusion)

Hit@k means: "At least one expected document appears in the top-k results."

Current output format:

```json
{
  "bm25": {
    "easy": {
      "hit_at_1": 0.5,
      "hit_at_3": 0.75,
      "hit_at_5": 0.8,
      "hit_at_10": 0.9,
      "count": 10
    }
  }
}
```

---

## Run Record Format (Recommended)

To compare runs over time, wrap the CLI output in a run record that adds
metadata about the environment and inputs. This can be done in a thin wrapper
script (no code changes to core evaluation logic required).

Recommended JSON envelope:

```json
{
  "run_id": "2026-02-08T20:15:00Z",
  "git": {
    "commit": "abcd1234",
    "branch": "main",
    "dirty": false
  },
  "corpus": {
    "path": "/Users/mike/Develop/lifeos/substrate/src/catalog/tests/corpus/vault-small",
    "hash": "sha256:..."
  },
  "queries": {
    "path": "/Users/mike/Develop/lifeos/substrate/src/catalog/tests/rag_v2/fixtures/golden_queries.json",
    "version": "v1"
  },
  "settings": {
    "embedding_model": "BAAI/bge-small-en-v1.5",
    "fts_impl": "sqlite_fts5",
    "rag_v2": {
      "chunk_size": 800,
      "chunk_overlap": 120
    }
  },
  "metrics": {
    "bm25": {
      "easy": {
        "hit_at_1": 0.50,
        "hit_at_3": 0.75,
        "hit_at_5": 0.80,
        "hit_at_10": 0.90,
        "count": 10
      }
    },
    "vector": { "...": "..." },
    "hybrid": { "...": "..." }
  }
}
```

Notes:

- `corpus.hash` should be computed from file contents to ensure the dataset
  is unchanged.
- `queries.version` is read from the golden queries JSON.
- `fts_impl` should be a short identifier (for example `sqlite_fts5`).

---

## Baselines and Regression Gating

### Baseline Selection

Each baseline is keyed by:

- Corpus hash
- Golden query version
- Embedding model id
- FTS implementation identifier
- RAG v2 settings that affect retrieval (chunking, fusion, rerank, etc.)

### Threshold Strategy

Suggested thresholds:

- FTS-only (bm25): tighter thresholds, results should be stable.
- Vector or hybrid: allow small drift due to model updates.

Use `--check` to enforce thresholds from `catalog.eval.golden`.

### Drift Categories

We recommend categorizing changes as:

1. Expected improvement (metrics increase)
2. Allowed drift (metrics decrease within tolerance)
3. Regression (metrics decrease past thresholds)

---

## Comparing Runs

When a run fails thresholds, compare against the most recent baseline:

1. Compare `metrics` (aggregated hit@k).
2. If desired, run `compare` or `compare-batch` for diagnostic overlap
   metrics across v1 and v2.

CLI support exists for v1 and v2 comparison:

```bash
uv run python -m catalog eval compare "your query here"
```

---

## CI Integration (Recommended)

Minimal CI:

1. Ingest fixed corpus into isolated paths.
2. Run golden eval with `--check`.
3. Persist run record artifacts.

Artifact Locations

Recommended path for outputs:

- `reports/evals/YYYY-MM-DD/<run-id>.json`

Do not store these under `src/catalog/tests/` to avoid test discovery.

---

## Updating the Harness

### When to Update Golden Queries

- You changed search ranking or query intent semantics.
- You added a new retriever mode or important filter behavior.

Always update `version` and document the change in `description`.

### When to Update the Corpus

Only update the corpus when:

- The current dataset no longer represents the desired domain.
- You can tolerate a baseline reset.

If you update the corpus, it must be treated as a new baseline.

---

## Troubleshooting

No results returned:

- Confirm the corpus ingest step succeeded.
- Verify `IDX_DATABASES_CATALOG_PATH` points to the eval database used during ingestion.

Flaky results:

- Confirm the embedding model is pinned.
- Ensure the vector store path is isolated and clean between runs.

Large metric shifts:

- Run a side-by-side `compare` on representative queries.
- Confirm golden query expectations still match the corpus.

---

## Summary

The golden query harness provides a repeatable evaluation loop that is
stable enough for CI gating while still sensitive to meaningful regressions.
It should be treated as the primary signal for search quality stability
over time.

## Feature Completion

Once this feature is completed, ensure the corresponding ADR is marked as accepted.
