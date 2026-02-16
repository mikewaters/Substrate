# Improvement Loop Contract

## The Five Phases

Every improvement round follows these phases in strict order.

### 1. Plan

- Identify the failure mode from prior metrics or user report.
- Form a hypothesis: what retrieval behavior causes the failure, and why.
- Design the experiment: which corpus mode, which queries, which retrievers.
- Write the spec before touching any code.

### 2. Instrument

- Add trace points or metrics collection if the current harness does not capture
  the data needed to validate or reject the hypothesis.
- Extend the evaluation harness, not the production code path, unless the
  production code path is itself the subject of change.

### 3. Experiment

- Run the retrieval experiment deterministically (fixed corpus, fixed queries,
  no stochastic variation beyond embedding model behavior).
- Emit all required artifacts (see artifact structure below).
- Never skip trace emission -- partial data invalidates the round.

### 4. Reflect

- Compare metrics against the baseline.
- Diagnose root cause from trace data: which channel contributed or failed,
  which score components dominated.
- Draft recommendations with evidence.

### 5. Queue

- If stopping criteria are met, close the campaign.
- Otherwise, create the next round plan based on reflect-phase findings.

## Experiment Artifact Structure

Each experiment is stored at: `experiments/YYYY-MM-DD/slug/`

Required files:

| File | Purpose |
|------|---------|
| spec.md | Hypothesis, approach, expected outcome. Written during Plan phase. |
| run.json | Execution metadata: timestamp, git SHA, corpus pointer, query set pointer, retriever settings. |
| metrics.json | Aggregated metrics following the schema in metrics-schema.md. |
| results.jsonl | Per-query retrieval results (query, ranked doc list, scores). |
| trace.jsonl | Per-query rank trace with channel contributions (see metrics-schema.md). |
| recommendations.md | Evidence-backed change proposals produced during Reflect phase. |
| diff.patch or commit ref | The code/config change tested in this round, if any. |

## Recommendation Output Contract

Every proposed change in recommendations.md must include all four sections:

1. **Why**: Which metric or scenario failed, by how much, and in which queries.
   Cite specific trace data (query text, expected doc_id, actual rank, score breakdown).

2. **What**: Exact code or config change location. File path, function name, or
   config key. Include a sketch of the change or reference the diff.

3. **Risk/Tradeoff**: What might regress. Which query difficulties or retriever
   types could be negatively affected. Any latency or cost implications.

4. **Validation**: Which queries and scenarios must pass after the change.
   State expected metric deltas (e.g., "hit_at_3 for hard queries should increase
   from 0.40 to at least 0.55").

## Stopping Criteria

- **Default round limit**: 3 rounds per campaign.
- **Early stop**: No key metric (hit_at_5, mrr_at_10) improves for 2 consecutive rounds.
- **Success stop**: All regression gates pass green AND the target failure mode
  (as stated in the campaign plan) is resolved.

A campaign that hits the round limit without resolving the failure mode should
produce a final summary with remaining gaps and suggested next campaign scope.

## Beads Task Tracking

- Create a parent task per campaign with the campaign goal as the title.
- Create round subtasks: plan, implement, evaluate -- one set per round.
- Close tasks with evidence: link to the experiment directory path.
- Use the `bd` CLI for all task operations. Do not modify task files directly.
