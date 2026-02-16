---
name: search-improver
description: Iterative retrieval diagnosis, corpus construction, experiment execution, and regression-gated improvement for RAG search.
---

# search-improver

Iteratively diagnoses retrieval failures, builds controlled sub-100-doc corpora, runs deterministic ingestion + retrieval experiments, proposes validated improvements, and tracks experiments locally with regression gates.

## Trigger phrases

Activate this skill when the user asks about:

- **Search debugging / retrieval failure diagnosis** -- "why isn't this query returning the right doc", "debug search for X", "diagnose retrieval failure"
- **Retrieval regression investigation** -- "search quality dropped", "recall regressed", "MRR went down after change"
- **Corpus design and selection** -- "build a test corpus", "curate fixture docs for eval", "synthetic corpus for search"
- **Hybrid search tuning** -- "tune RRF weights", "adjust reranking", "hybrid search balance", "keyword vs semantic weight"
- **Eval gating and baseline comparison** -- "compare against baseline", "run regression gate", "did this change improve search"

## Loop contract

Every engagement MUST follow this cycle. Do not skip steps.

```
Plan -> Instrument -> Experiment -> Reflect -> Queue next round (or stop)
```

1. **Plan** -- Identify the failure mode or improvement target. State the hypothesis. Define the metric that must move.
2. **Instrument** -- Build or select the corpus. Write or update the golden queries. Configure the experiment parameters.
3. **Experiment** -- Run ingestion + retrieval through the harness. Collect per-query traces and aggregate metrics.
4. **Reflect** -- Compare against baseline. Identify what improved, what regressed, what stayed flat. Record findings.
5. **Queue** -- If stopping criteria not met, define the next hypothesis and loop. Otherwise, declare the campaign complete.

## Key scripts

All scripts live in the `scripts/` directory relative to this skill.

| Script | Purpose |
|---|---|
| `build_corpus.py` | Build curated, synthetic, or fixture corpora for controlled experiments |
| `run_experiment.py` | Run ingestion + retrieval experiments end-to-end |
| `build_metrics.py` | Derive aggregate metrics (MRR, recall, precision) and per-query traces |
| `compare_baseline.py` | Compare current metrics against a baseline; enforce regression gate |
| `bootstrap_round.py` | Create or update beads round tasks for campaign tracking |

## Required reuse targets

These existing repo modules MUST be used rather than reimplemented:

- `scripts/ingest_obsidian_vault.py` -- vault ingestion pipeline
- `scripts/run_search_eval.py` -- search evaluation runner
- `src/catalog/catalog/eval/harness.py` -- evaluation harness
- `src/catalog/catalog/eval/golden.py` -- golden dataset management
- `src/catalog/catalog/search/service.py` -- search service
- `src/catalog/catalog/search/models.py` -- search models and types

## Experiment ledger

Each experiment MUST be stored in a dated, slugged directory:

```
experiments/<YYYY-MM-DD>/<slug>/
  spec.md              -- Hypothesis, parameters, and expected outcomes (write before running)
  run.json             -- Execution metadata (written by run_experiment.py)
  metrics.json         -- Aggregated metrics (written by run_experiment.py, enriched by build_metrics.py)
  results.jsonl        -- Per-query retrieval results (written by run_experiment.py)
  trace.jsonl          -- Per-result rank traces (written by run_experiment.py)
  recommendations.md   -- Evidence-backed improvement proposals (write after reflecting)
  diff.patch           -- Code changes or commit references (capture after implementing)
```

### Typical pipeline

```bash
# 1. Build corpus
uv run python scripts/build_corpus.py synthetic --output-dir /tmp/corpus --seed 42

# 2. Run experiment
uv run python scripts/run_experiment.py \
    --corpus-dir /tmp/corpus \
    --output-dir experiments/2026-02-15/heading-bias-v1 \
    --slug heading-bias-v1

# 3. Enrich metrics (adds nDCG@k, heading-dominance rate)
uv run python scripts/build_metrics.py enrich \
    --experiment-dir experiments/2026-02-15/heading-bias-v1

# 4. Compare against baseline
uv run python scripts/compare_baseline.py \
    --current experiments/2026-02-15/heading-bias-v1/metrics.json \
    --baseline reports/evals/baselines/latest.json

# 5. View summary
uv run python scripts/build_metrics.py summary \
    --experiment-dir experiments/2026-02-15/heading-bias-v1
```

## Default assumptions

- **Primary corpus**: `src/catalog/tests/corpus/vault-small`
- **Primary queries**: `src/catalog/tests/rag_v2/fixtures/golden_queries.json`
- **Experiment artifacts**: `experiments/` directory at repo root
- **Run records**: `reports/evals/` directory at repo root
- **Iteration cap**: 3 rounds per campaign unless overridden

## Stopping criteria

- **Default cap**: 3 rounds per campaign.
- **Early stop**: No key metric improves for 2 consecutive rounds.
- **Success stop**: Regression gates green AND the target failure mode is resolved.
