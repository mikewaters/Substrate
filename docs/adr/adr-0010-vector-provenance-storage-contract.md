# ADR-0010: Store Embedding Provenance in Vector Metadata Payloads

**Status:** Accepted
**Date:** 2026-02-15

## Context

We need a clear and backend-consistent contract for where embedding-model
provenance is stored. Without an explicit contract, provenance could drift into
separate tables/files, creating dual-write risk and query-time ambiguity.

For Qdrant, the natural storage location is point payload metadata. For Zvec,
the equivalent location is per-entry metadata in the local index file.

## Decision

- Store embedding provenance with each vector record using the standard keys:
  - `embedding_backend`
  - `embedding_model_name`
  - `embedding_profile` (`{backend}:{model_name}`)
- For Qdrant, write/read these fields as normal Qdrant payload metadata on each
  point.
- For Zvec, write/read the same fields in each local index entry metadata
  object.
- Query-time model selection must read stored provenance from the active vector
  store and use it to choose embedding models, even when current runtime
  embedding config differs.
- If provenance is missing on legacy vectors, fall back to configured identity
  for compatibility.

## Consequences

- Provenance is co-located with vectors, avoiding a separate registry and
  reducing consistency failures.
- Qdrant and Zvec use one provenance schema, making behavior easier to test and
  compare.
- Debugging is simpler because provenance is inspectable directly in vector
  payload/entry metadata.
- Mixed-profile collections remain supported, with additional query cost from
  per-profile searches.
