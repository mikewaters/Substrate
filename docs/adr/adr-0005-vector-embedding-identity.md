# ADR-0005: Persist Embedding Identity with Each Vector

**Status:** Accepted
**Date:** 2026-02-15

## Context

`catalog` currently chooses the query embedding model from runtime config.
Vectors in Qdrant do not carry the embedding model identity that generated
them. If config changes after ingestion, retrieval may embed queries in a
different vector space than stored points, degrading or invalidating semantic
search.

## Decision

- Persist an embedding identity payload on every chunk/vector at ingest time:
  - `embedding_backend`
  - `embedding_model_name`
  - `embedding_profile` (`{backend}:{model_name}`)
- Resolve query-time embedding models from identities discovered in vector
  payloads rather than from current config alone.
- For vector search, query once per discovered embedding profile and merge
  ranked results.
- For hybrid search, route vector retrieval through `VectorSearch` so hybrid
  mode uses the same identity-aware behavior.

## Consequences

- Retrieval remains correct when runtime embedding config drifts from historic
  ingestion config.
- Mixed embedding profiles can coexist in the same collection without forcing
  immediate reindexing.
- Query cost increases when multiple embedding profiles are present because
  vector search executes one query per profile.
- Legacy vectors without embedding identity fall back to configured model
  behavior until they are re-ingested.
