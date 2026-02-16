# Metrics and Trace Schemas

## Required Retrieval Metrics

All experiments must report these metrics at k=1, 3, 5, and 10:

- **Recall@k (hit@k)**: Binary -- 1 if any expected document appears in the top k
  results, 0 otherwise. Averaged across queries to produce hit rate.
- **MRR@k**: Mean Reciprocal Rank. For each query, 1/rank of the first relevant
  result (0 if none in top k). Averaged across queries.
- **nDCG@k**: Normalized Discounted Cumulative Gain. Used when graded relevance
  judgments exist (not just binary). Falls back to binary relevance otherwise.
- **Heading-dominance rate**: Fraction of queries where the top-1 result is a
  heading-only match (no body content overlap). Tracks a known failure mode where
  short heading nodes outrank substantive content.

## Optional Answer-Level Metrics

These require LLM evaluation and are not part of the regression gate by default:

- **Context relevancy**: Whether retrieved passages actually help answer the query.
- **Faithfulness**: Whether the generated answer is grounded in the retrieved context.

## Per-Query Trace (trace.jsonl)

One line per (query, mode, result) triple. Each line is a JSON object:

| Field | Type | Description |
|-------|------|-------------|
| query | string | The query text |
| mode | string | One of `"fts"`, `"vector"`, `"hybrid"`, `"hybrid_rerank"` |
| rank | int | 1-based rank in the result list |
| doc_id | string | Document identifier (matches corpus doc_id) |
| node_id | string | Node-level identifier when available (nullable) |
| score_final | float | Final score used for ranking |
| score_components | object | Breakdown: `{"fts": float, "vector": float, "rrf": float, "rerank": float}`. Omit keys that do not apply to this mode. |
| source_channel_ranks | object | For hybrid modes only: `{"bm25_rank": int, "vector_rank": int, "fused_rank": int}` |

## Aggregated Metrics (metrics.json)

Structure:

```json
{
  "by_retriever": {
    "<retriever_type>": {
      "by_difficulty": {
        "<difficulty>": {
          "hit_at_1": 0.75,
          "hit_at_3": 0.90,
          "hit_at_5": 0.95,
          "hit_at_10": 1.0,
          "mrr_at_10": 0.82,
          "count": 12
        }
      },
      "overall": {
        "hit_at_1": 0.70,
        "hit_at_3": 0.85,
        "hit_at_5": 0.92,
        "hit_at_10": 0.97,
        "mrr_at_10": 0.78,
        "count": 40
      }
    }
  }
}
```

Keys under `by_retriever`: `"bm25"`, `"vector"`, `"hybrid"`.
Keys under `by_difficulty`: `"easy"`, `"medium"`, `"hard"`, `"fusion"`.

## Regression Gate

Configuration lives in the experiment spec or a shared config file.

**Default threshold**: No metric may drop more than 0.05 from the stored baseline.

Behavior:
- Compare each metric in `metrics.json` against corresponding value in baseline.
- If any metric regresses beyond the threshold, exit with non-zero code.
- Baseline files are stored in `reports/evals/baselines/` as `metrics.json` snapshots.
- To update a baseline, copy the current `metrics.json` into the baselines directory
  after confirming the results are acceptable.

Thresholds are configurable per-metric. Example override:

```json
{
  "hit_at_1": 0.03,
  "mrr_at_10": 0.05,
  "heading_dominance_rate": 0.10
}
```
