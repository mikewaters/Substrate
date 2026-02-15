# ADR-0006: Capability-Driven Embedding Identity Strategy in VectorStoreManager

**Status:** Accepted
**Date:** 2026-02-15

## Context

Embedding identity fallback logic (payload stamping and multi-profile query
fan-out) is required for Qdrant in the current implementation because the
database does not natively route queries by embedding model identity.

We plan to support additional vector backends. Some backends may natively
support embedding identity and should not pay the cost or complexity of the
Qdrant fallback path.

## Decision

- Add a backend capability model to `VectorStoreManager`:
  - `VectorBackendCapabilities.native_embedding_identity`
- Select an embedding identity strategy once at manager initialization:
  - `NativeEmbeddingIdentityStrategy` for backends with native support.
  - `PayloadEmbeddingIdentityStrategy` for backends without native support.
- Move identity-specific behavior behind manager APIs:
  - `build_ingest_transforms(embed_model)`
  - `semantic_query(query, top_k, dataset_name)`
- Keep ingest and search callers backend-agnostic by relying only on manager
  APIs, not backend/vendor checks.

## Consequences

- Qdrant continues to use payload-based identity fallback.
- Native-support backends can bypass payload stamping and profile fan-out.
- Caller code in ingest/search remains stable as new backends are added.
- Vector backend integrations must declare capabilities correctly to select the
  right strategy.
