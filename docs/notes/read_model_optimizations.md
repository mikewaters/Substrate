# Read Model Optimizations

Story 3.2 focuses on surfacing fast read paths for the ontology topics domain:

- **Indexes**: Added B-tree indexes on `(taxonomy_id, status)`, `created_at`, and `path` to
  accelerate common filters, as well as keeping existing individual indexes.
- **Aggregations**: Implemented repository and service helpers for status and taxonomy
  counts, exposing lightweight read-model endpoints for dashboards and UI.
- **Recent Activity**: Added recency-oriented queries keyed by the new `created_at`
  index for quick “what changed?” views.

The `/read-model/topics/*` API routes now serve these optimized queries for downstream
clients without requiring bespoke SQL.
