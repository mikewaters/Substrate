# ADR-0004: Resource Metadata JSON Column

**Status:** Accepted
**Date:** 2026-02-11

## Context

Metadata currently lives on `Document` as `metadata_json`, but we need to attach metadata
to other resource types (Dataset, Bookmark, and potentially others). The current schema
also stores metadata as a serialized string, limiting JSON-aware queries in SQLite.

## Decision

- Move `metadata_json` from `Document` to the `Resource` base table so all resource
  types can store metadata.
- Store metadata using a JSON column type in SQLAlchemy.
- Surface metadata handling only in Dataset, Document, and Bookmark flows for now.
- Do not add migrations or compatibility shims; databases should be rebuilt as needed.

## Consequences

- Metadata is available on any resource instance and can be queried via JSON1 in SQLite.
- Queries that previously referenced `documents.metadata_json` must join `resources`
  instead.
- Existing databases are incompatible and must be recreated or re-ingested.
