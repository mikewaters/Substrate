# ADR-0007: Add Latent Zvec Vector Backend Support

**Status:** Accepted
**Date:** 2026-02-15

## Context

The catalog currently uses Qdrant as its vector database backend.

We want to explore multi-backend API surface area without changing runtime
behavior in production by default. We specifically want to evaluate Zvec
(<https://github.com/alibaba/zvec>) as a secondary backend candidate.

## Decision

- Keep Qdrant as the default runtime backend.
- Introduce vector backend selection settings with:
  - `vector_db.backend` (`qdrant` or `zvec`)
  - `vector_db.enable_experimental_zvec` (must be true to opt in)
- Add latent Zvec support in `VectorStoreManager` for semantic query calls.
- Mark Zvec support as experimental and opt-in only.
- Keep Qdrant code paths intact; do not add legacy fallback branches.

## Consequences

- Existing deployments continue using Qdrant unchanged.
- Teams can test Zvec in production-like environments by explicit
  configuration changes.
- The codebase gains a concrete secondary backend API surface for future
  expansion while limiting rollout risk.
