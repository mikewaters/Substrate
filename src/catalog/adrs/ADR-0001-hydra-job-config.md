# ADR-0001: Hydra for YAML-Based Job Configuration

**Status:** Accepted
**Date:** 2026-02-01

## Context

Ingestion pipeline configuration (source paths, embedding models, caching strategy) was hardcoded in `IngestPipeline`. We need a way to define reusable, parameterized ingestion jobs as YAML files so users can run different configurations without code changes.

Options considered:
- Raw YAML + PyYAML: Simple but no variable interpolation or config composition.
- Pydantic YAML: Would require custom loader; no composition support.
- Hydra + OmegaConf: Industry-standard config framework with variable interpolation (`${source.source_path}`), config composition via defaults lists, and override syntax from callers.

## Decision

Use Hydra's `compose()` API (not `@hydra.main()`) to load YAML job configs into a `DatasetJob` Pydantic model. This is library code, not a CLI entry point, so we use the programmatic API.

- `DatasetJob` is a Pydantic model that validates the loaded config.
- `ontology_spec` is stored as a dotted import path string in YAML, resolved to a Python class at runtime via `_import_class()` (same pattern as Hydra `_target_` and Django `import_string()`).
- `DatasetJob` converts to `IngestObsidianConfig` via `to_ingest_config()` — clean separation between job config (superset with embedding + pipeline settings) and the existing ingest config hierarchy.

## Consequences

- **Easier**: Adding new ingestion jobs is a YAML file, not code. Embedding model and caching strategy are per-job configurable.
- **Harder**: Adds two dependencies (`hydra-core`, `omegaconf`). Hydra's `compose()` requires a config search path setup.
- **Trade-off**: The existing `ingest()` method is unchanged — `ingest_from_config()` is additive.
