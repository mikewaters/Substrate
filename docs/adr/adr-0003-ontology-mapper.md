# ADR-0003: Ontology Mapper in Ingestion Pipeline

**Status:** Accepted
**Date:** 2026-02-08

## Context

Frontmatter → ontology mapping previously lived in `FrontmatterTransform`, which was inserted by
source-specific `get_transforms()` implementations. This made the mapping step implicit, tied to
specific sources, and harder to reason about within the ingestion pipeline. The naming (`vault_schema`)
also reflected Obsidian/Heptabase terminology rather than the shared ontology.

## Decision

- Introduce a shared `OntologyMappingSpec` protocol with `from_frontmatter()` and
  `to_document_meta()`.
- Add a pipeline-owned `OntologyMapper` transform that runs pre-persist for all sources.
- Rename `VaultSchema` to `VaultSpec` and rename the config key to `ontology_spec`.
- Sources provide only post-persist transforms; the pipeline injects `OntologyMapper` using
  `source.ontology_spec`.

## Consequences

- Ontology mapping is consistent and explicit in the pipeline.
- Source implementations are simpler (no pre-persist mapping transform).
- Configuration is breaking: `vault_schema` is replaced by `ontology_spec`, and the primary
  mapping class is now `VaultSpec`.
- The `FrontmatterTransform` class remains available but is no longer used by the pipeline.
