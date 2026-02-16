# ADR-0012: Duplicate Handling for Document URIs

**Status:** Accepted
**Date:** 2026-02-15

## Context

Document resources are identified by a unique URI stored in `resources.uri`. The URI is built from the dataset name and the document path via `make_document_uri(dataset_name, path)`. To keep URIs URL-safe and readable, the path is slugified (lowercased, non-alphanumerics replaced with hyphens). Lookups and persistence use the exact path for document identity within a dataset (`Document.path`, `get_by_path(parent_id, path)`), but the URI is what must be unique across all resources.

We observed `sqlite3.IntegrityError: UNIQUE constraint failed: resources.uri` on a fresh database during ingestion. The failure was not caused by duplicate files in the corpus.

## Finding

Slugification is not injective: different paths can produce the same slug. For example:

- `LabelFiles/Continuity.txt.md`
- `LabelFiles/Continuity txt.md` (space instead of dot)
- `LabelFiles/Continuity.Txt.Md`

all slugify to `labelfiles-continuity-txt-md`. Those distinct paths therefore generated the same URI (`document:<dataset>:labelfiles-continuity-txt-md`). The first INSERT succeeded; the second violated the UNIQUE constraint and caused the session to roll back, which then produced cascading "transaction has been rolled back" errors for subsequent nodes in the same batch.

## Decision

- Keep building document URIs from dataset name and path: `document:<dataset>:<slug>:<path_hash>`.
- Append a deterministic short hash of the original path (e.g. first 12 hex chars of SHA-256 of the UTF-8 path) so that different paths always yield different URIs even when they slugify to the same value.
- Do not rely on slugify alone for uniqueness. The slug remains for human readability; the hash guarantees uniqueness and satisfies the `resources.uri` constraint.

## Consequences

- Document URIs are unique per (dataset, path) without path collisions.
- Same path always produces the same URI (hash is deterministic).
- URI strings are slightly longer (extra `:<12-char-hex>`). The existing `resources.uri` column (e.g. 512 chars) remains sufficient.
- No change to path-based lookup or to how documents are keyed in the API; only the stored URI format changes for new documents.
