# Search Improver Skill Requirements (Handoff Artifact)

Use this document as the single handoff artifact for the skill-creator agent.
It defines the target behavior, required resources, and acceptance criteria for
a reusable skill that iteratively improves search quality in this repository.

## 1) Objective

Create a skill named `search-improver` that can repeatedly:

1. Diagnose retrieval failures in the local search stack.
2. Build or select controlled sub-100-document corpora.
3. Run deterministic ingestion + retrieval experiments using real code paths.
4. Propose and validate search improvements with measurable evidence.
5. Track each experiment locally and gate regressions.

The skill must treat LlamaIndex concepts as first-class in analysis and
recommendations: loading, transformations/node parsing, retrieval, fusion, and
evaluation.

## 2) Non-Goals

1. Do not build UI dashboards.
2. Do not use external eval SaaS tools.
3. Do not rely on LLM-only judging without retrieval-only metrics.
4. Do not create migration or compatibility fallbacks.

## 3) Repository Grounding (Must Reuse Existing Components)

The skill must prefer existing repository abstractions over reimplementation.

Required reuse targets:

1. Ingestion script:
   - `scripts/ingest_obsidian_vault.py`
2. Eval harness entrypoint:
   - `scripts/run_search_eval.py`
3. Eval internals:
   - `src/catalog/catalog/eval/harness.py`
   - `src/catalog/catalog/eval/golden.py`
4. Search orchestration:
   - `src/catalog/catalog/search/service.py`
   - `src/catalog/catalog/search/models.py`

If a required metric or trace is missing, extend these paths instead of creating
a parallel implementation.

## 4) Skill Package Deliverables

The skill-creator agent must output a valid skill folder with:

1. `SKILL.md`:
   - Tight `name` and `description` frontmatter.
   - Description must include trigger phrases for search debugging, retrieval
     regressions, corpus design, hybrid tuning, and eval gating.
2. `agents/openai.yaml`:
   - Generated from the skill using the skill-creator workflow.
3. `scripts/`:
   - Multiple deterministic scripts (required; see Section 7).
4. `references/`:
   - Focused reference files for corpus formats, metric schema, and Beads loop.

Do not add auxiliary docs such as README or changelog files inside the skill.

## 5) Loop Contract (Mandatory Behavior)

The skill must enforce a strict loop:

1. Plan
2. Instrument
3. Experiment
4. Reflect
5. Queue next round (optional) or stop

The skill must not propose a change without a harness run artifact that supports
the claim.

## 6) Beads Task Management Contract

The skill must use `bd` for coding-task tracking per `AGENTS_TASKS.md`.

Required behavior:

1. Create a parent Beads task for each improvement campaign.
2. Create round tasks for each iteration (at least plan, implement, evaluate).
3. Update task status as work progresses.
4. Close tasks with explicit evidence references (experiment folder path).
5. Repeat for multiple rounds until stopping criteria are met.

Stopping criteria defaults:

1. Stop after 3 rounds by default.
2. Stop early if no key metric improves for 2 consecutive rounds.
3. Stop when regression gates are green and target failure mode is resolved.

## 7) Script-First Requirements (Deterministic Tasks to Encapsulate)

The skill must be heavily biased to scripts for repeatable operations.
At minimum, include scripts equivalent to the following responsibilities:

1. Corpus builder script:
   - Build curated, synthetic, or fixture corpora.
   - Emit deterministic corpus artifacts.
2. Retrieval experiment runner script:
   - Execute ingestion and retrieval runs across modes.
   - Call existing app code paths.
3. Metrics and trace builder script:
   - Derive aggregate metrics and per-query traces.
4. Baseline comparator script:
   - Compare current metrics with baseline and return non-zero on regression.
5. Beads round bootstrap script:
   - Create/update round tasks for the improvement loop.

Script requirements:

1. Deterministic outputs for same inputs and seed.
2. Clear CLI interface (`--help`, explicit required args).
3. Offline-friendly execution (except local model inference already used in-app).
4. Store outputs only in repository-local artifacts.

## 8) Corpus Requirements (Sub-100 Docs)

Support three corpus modes:

1. Curated snippets:
   - Extract 20-80 markdown docs or sections from local vault/test inputs.
   - Preserve headings and metadata.
2. Synthetic unit corpora:
   - Include templates for heading trap, exact-match trap, near-duplicate, and
     metadata-only relevance.
3. Fixture corpora:
   - Stable, version-controlled corpora under a deterministic fixture path.

Canonical corpus artifact format:

1. `corpus.jsonl`:
   - One document per line with `doc_id`, `title`, `body`, optional frontmatter.
2. `queries.json`:
   - Query list with expected doc IDs and target retriever modes.
3. `README.md`:
   - Corpus intent, generation method, and known failure modes covered.

## 9) Harness and Experiment Requirements

Each run must execute retrieval modes:

1. BM25/FTS
2. Vector
3. Hybrid (RRF)
4. Hybrid + rerank

Each run must output:

1. `run.json`:
   - Timestamp, git metadata, corpus/queries pointers, relevant settings.
2. `results.jsonl`:
   - Per-query retrieval results.
3. `metrics.json`:
   - Aggregated metrics.
4. `trace.jsonl`:
   - Per-query rank trace with channel-level contributions.

Per-query trace minimum fields:

1. `query`
2. `mode`
3. `rank`
4. `doc_id` or path
5. `node_id` when available
6. `score_final`
7. `score_components` (for example: fts/vector/rrf/rerank)
8. `source_channel_ranks` for hybrid fusion (bm25 rank, vector rank, fused rank)

## 10) Scenario Coverage Requirements

Minimum scenario set (must be runnable repeatedly):

1. Heading bias regression.
2. Exact-match identifiers (numbers/SKU/IDs).
3. Semantic paraphrase retrieval.
4. Near-duplicate ranking/diversity behavior.

For each scenario, define:

1. Failure hypothesis.
2. Query set.
3. Expected retrieval behavior.
4. Metric targets.

## 11) Metrics and Regression Gates

Required retrieval metrics:

1. Recall@k (or hit@k where appropriate).
2. MRR@k.
3. nDCG@k when graded relevance exists.
4. Heading-dominance rate.

Optional answer-level metrics:

1. Context relevancy.
2. Faithfulness.

Regression gate requirements:

1. Local command to compare latest run vs baseline.
2. Configurable thresholds per metric.
3. Non-zero exit code on threshold failure.

## 12) Local Experiment Ledger

Store each experiment in:

`experiments/<YYYY-MM-DD>/<slug>/`

Required files:

1. `spec.md`
2. `run.json`
3. `metrics.json`
4. `results.jsonl`
5. `trace.jsonl`
6. `recommendations.md`
7. `diff.patch` or commit references

## 13) Recommendation Output Contract

For every proposed change, output:

1. Why:
   - Which metric/scenario failed and by how much.
2. What:
   - Exact code/config change location.
3. Risk/Tradeoff:
   - Possible regressions or cost implications.
4. Validation:
   - Which scenarios and expected deltas must pass.

Recommendations must be prioritized and linked to experiment evidence paths.

## 14) Definition of Done

The skill is complete when it can run end-to-end and demonstrate all of:

1. Build/select a valid sub-100-document corpus and query set.
2. Run ingestion and retrieval through real repo abstractions.
3. Emit deterministic metrics and trace artifacts.
4. Generate at least one evidence-backed improvement recommendation.
5. Track round-based progress in Beads tasks.
6. Compare against baseline and enforce regression gates locally.

## 15) Default Assumptions for Implementation

Use these defaults unless the user overrides them:

1. Primary corpus:
   - `src/catalog/tests/corpus/vault-small`
2. Primary queries:
   - `src/catalog/tests/rag_v2/fixtures/golden_queries.json`
3. Eval wrapper:
   - `scripts/run_search_eval.py`
4. Output roots:
   - `experiments/` for loop artifacts
   - `reports/evals/` for run records and baselines
5. Iteration cap:
   - 3 rounds per campaign
