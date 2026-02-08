# ADR-0002: Adopt Golden Query Evaluation Harness for Search Regression Tracking

**Status:** Proposed
**Date:** 2026-02-08

## Context

Search quality can regress when we change embedding models, FTS behavior, or
ranking logic. We need a stable, repeatable evaluation loop that can run in CI
and during local development without touching production data. The repository
already includes a golden query evaluator and a curated corpus, but there is no
formalized harness for longitudinal tracking and gating.

## Decision

Adopt a golden query evaluation harness as the primary mechanism for tracking
search quality regressions. The harness will:

- Use a fixed, versioned corpus and golden queries.
- Run evaluation via the existing CLI (`catalog eval golden`).
- Record a run record with metadata (corpus hash, model id, settings, git
  commit) for longitudinal comparisons.
- Gate changes using thresholds for hit@k metrics, with tighter thresholds for
  FTS-only and looser thresholds for vector and hybrid modes.

## Consequences

**Benefits:**

- Repeatable, deterministic evaluation suitable for CI gating.
- Clear detection of regressions when models or indexing change.
- Structured artifacts for longitudinal comparison.

**Trade-offs:**

- Golden queries and corpora require maintenance and versioning.
- Embedding drift may produce acceptable changes that still require thresholds
  and tolerances.
- The harness measures retrieval accuracy, not UI or latency behavior.
