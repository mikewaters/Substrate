# Search Eval Harness Implementation

This feature adds a concrete harness command for longitudinal search-quality
tracking using the existing golden-query evaluation CLI.

## What was implemented

- `scripts/run_search_eval.py`
  - Orchestrates isolated ingestion + golden-query evaluation.
  - Captures a run record JSON with git metadata, corpus hash, query version,
    selected retrieval settings, and evaluation metrics.
  - Supports baseline-key generation and optional baseline presence checks.
- `catalog.eval.harness`
  - Reusable utilities for run record generation and metadata normalization.
  - Stable corpus hashing for baseline partitioning.
  - Parsing helper for eval CLI output.
- `tests/rag_v2/test_eval_harness.py`
  - Unit coverage for corpus hashing, version extraction, metrics parsing,
    run record structure, and baseline-key determinism.

## Usage

From repository root:

```bash
uv run python scripts/run_search_eval.py \
  --corpus src/catalog/tests/corpus/vault-small \
  --queries-file src/catalog/tests/rag_v2/fixtures/golden_queries.json \
  --output-dir reports/evals \
  --dataset-name eval-vault \
  --embedding-model mlx-community/all-MiniLM-L6-v2-bf16
```

### Optional baseline gate

```bash
uv run python scripts/run_search_eval.py \
  --corpus src/catalog/tests/corpus/vault-small \
  --queries-file src/catalog/tests/rag_v2/fixtures/golden_queries.json \
  --compare-baseline
```

When `--compare-baseline` is enabled, the command fails if the baseline file
for the current baseline key is not present under `reports/evals/baselines/`.

## Notes

- Harness execution is intentionally isolated from developer-local databases via
  explicit IDX path overrides.
- This implementation performs baseline existence checks only; score-threshold
  diffing can be added in a follow-up increment.
