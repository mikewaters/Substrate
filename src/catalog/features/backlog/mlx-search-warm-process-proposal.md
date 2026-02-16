# MLX Search Warm-Process Proposal

## Context

Current catalog search usage is often CLI-driven. On macOS with MLX embeddings,
one-shot commands pay model cold-start cost repeatedly because process memory is
released after each invocation. A process-local cache helps only within one
process lifetime and does not provide cross-invocation warm behavior.

## Problem Statement

Users observe latency spikes when running search commands repeatedly. The main
contributors are:

- embedding model initialization and first inference warm-up
- repeated creation of search-layer objects in new processes
- no persistent runtime that can hold model state in memory across commands

## Goals

- Reduce p95/p99 query latency for repeated local search queries.
- Preserve existing retrieval logic (fts/vector/hybrid/rerank) while improving
  runtime behavior.
- Provide a macOS-native operational path for MLX warm-state retention.

## Non-Goals

- Changing retrieval scoring semantics.
- Introducing migration/fallback complexity.
- Replacing the current CLI UX immediately.

## Recommended Approaches for macOS (MLX)

### 1) Long-lived local search service (recommended)

Run a persistent process (FastAPI or lightweight IPC service) that owns:

- `SearchService`
- `VectorStoreManager`
- embedding model instance

At startup, issue a synthetic embedding call (for example: `"warmup"`) so model
load and first-kernel compilation happen before user traffic.

Why this is preferred:

- true warm state across CLI invocations
- simplest mental model for users (CLI becomes a client)
- easiest place to add health checks and latency instrumentation

### 2) LaunchAgent-managed daemon (recommended for developer UX)

Package the local service under a macOS `launchd` LaunchAgent so it starts at
login and auto-restarts if it exits.

Why this helps:

- no manual service startup after reboot
- consistent warm behavior during a work session

### 3) Background embedding worker with IPC (optional variant)

Use a dedicated embedding worker process and call it from the main search
process/CLI via Unix domain socket.

Tradeoffs:

- can isolate model memory and crash domain
- adds transport complexity versus a single service process

## Why process-only caches are insufficient

In-process caches improve repeated object construction inside one Python
interpreter, but the cache is cleared when the process exits. For one-shot CLI
patterns, this does not solve repeated cold starts between commands.

## Proposed Implementation Plan

1. Add `catalog serve` to run a local persistent search API.
2. Add a startup warm-up hook that executes one embedding request.
3. Add `catalog search` as a client command that targets the local service.
4. Add timeout + health probe (`/health`) and clear startup errors.
5. Add optional LaunchAgent template and documentation for macOS setup.
6. Add latency telemetry fields (`cold_start`, `model_load_ms`, `query_ms`).

## Required ADRs to Define Before Implementation

To avoid unclear architecture decisions, the following ADRs should be created in
`src/catalog/adrs/` (next sequence numbers shown):

1. **ADR-0005: Local Search Runtime Mode (one-shot CLI vs long-lived service)**
   - Decision: adopt persistent local service for query execution.
   - Include scope, operational model, and rollback strategy.

2. **ADR-0006: Warm-State Lifecycle and Startup Policy**
   - Decision: explicit startup warm-up behavior, readiness gating, and failure
     handling semantics.
   - Include when warm-up is mandatory vs best-effort.

3. **ADR-0007: macOS Persistence Method for Local Runtime**
   - Decision: `launchd` LaunchAgent as the supported persistence mechanism for
     local developer machines.
   - Include service ownership, logs, restart policy, and security posture.

4. **ADR-0008: Client/Service Transport Contract**
   - Decision: transport protocol for CLI-to-service calls (HTTP loopback vs
     Unix socket IPC), authentication assumptions for local-only usage, and
     versioning strategy.

## Success Metrics

- Cold start paid once per daemon lifecycle, not once per query.
- Improved repeated-query latency during a session.
- No retrieval-quality regressions (hit@k unchanged within variance).

## Risks and Mitigations

- **Risk:** daemon lifecycle confusion.
  - **Mitigation:** explicit `catalog serve status|start|stop` commands.
- **Risk:** stale runtime after config/model change.
  - **Mitigation:** config hash check and controlled restart requirement.
- **Risk:** increased local operational complexity.
  - **Mitigation:** provide default LaunchAgent template and short setup docs.
