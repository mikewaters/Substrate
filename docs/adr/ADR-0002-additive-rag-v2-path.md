# ADR-0002: Additive LlamaIndex RAG v2 Namespace

**Status:** Proposed
**Date:** 2025-02-14

## Context
The catalog codebase already provides v1 search and ingestion flows built on LlamaIndex. We need to integrate a new hybrid RAG option derived from a separate design without disrupting existing clients or storage.

## Decision
Introduce a new, explicit `catalog.search_v2` namespace for the additive hybrid RAG path. The v2 path will reuse existing storage, embedding, and retrieval seams while remaining opt-in. The existing `catalog.search` API will remain unchanged.

## Consequences
- Existing clients are unaffected unless they opt into v2.
- v2 development can proceed without refactoring v1 components.
- Parallel paths require ongoing parity testing and configuration management.
