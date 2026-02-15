# ADR-0009: Align Zvec Query-Time Embedding Provenance with Qdrant Strategy

**Status:** Accepted
**Date:** 2026-02-15

## Context

The vector search stack already uses payload-based embedding provenance for
Qdrant: query-time embeddings are generated per stored embedding identity to
avoid mismatches when collections contain mixed models.

Latent Zvec support originally queried with a single configured embedding model
and did not use stored provenance metadata from the local index entries.

## Decision

- Treat latent Zvec as a payload-based identity backend (not native identity).
- Discover embedding identities from Zvec local index metadata.
- Execute query-time embeddings per discovered identity and apply identity
  filtering during Zvec semantic query.
- When index entries lack provenance metadata, fallback to configured embedding
  identity and stamp fallback identity into returned hit metadata.

## Consequences

- Zvec and Qdrant now share the same provenance model for query-time embedding
  selection.
- Search quality is more robust for mixed-model indexes and model migrations.
- Legacy Zvec entries without provenance still work via configured fallback
  identity, but should be backfilled with explicit metadata over time.
