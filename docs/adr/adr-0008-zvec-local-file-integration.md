# ADR-0008: Use Local File Input for Latent Zvec Queries

**Status:** Accepted
**Date:** 2026-02-15

## Context

ADR-0007 introduced latent Zvec support via an HTTP endpoint for semantic query
evaluation. We now require Zvec integration to query a local file directly
instead of making API calls.

## Decision

- Keep `vector_db.backend=zvec` and the existing experimental feature gate.
- Replace Zvec HTTP configuration with a local index path:
  - `SUBSTRATE_ZVEC__INDEX_PATH`
  - `SUBSTRATE_ZVEC__COLLECTION_NAME`
- Execute Zvec semantic queries in-process by reading the configured local JSON
  file and ranking entries with cosine similarity.
- Remove Zvec HTTP endpoint/timeout settings from runtime configuration.

## Consequences

- Zvec query behavior no longer depends on network reachability or external API
  availability.
- Local and CI runs can test Zvec behavior deterministically with fixture files.
- Zvec remains latent and query-only; ingest and persistence flows are still
  implemented through the Qdrant backend.
