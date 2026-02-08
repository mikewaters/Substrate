# ADR-0001: Lightweight JSON Schema Doc Script for Catalog Models

**Status:** Accepted
**Date:** 2026-02-06

## Context
We need documentation artifacts that convey the overall shape and relationships of
SQLAlchemy ORM models in `src/catalog/catalog/store/models.py`. This output is
for documentation only, not runtime validation, and accuracy beyond overall
shape is low priority. There are multiple valid approaches, including a full
Pydantic intermediate model generation pipeline or a direct SQLAlchemy
inspection pass.

## Decision
Implement a lightweight utility script in `scripts/` that inspects SQLAlchemy
mappers directly and emits a best-effort JSON Schema document. The script will
not add production code to the catalog module and will not require a Pydantic
intermediate model generation step.

## Consequences
- Faster implementation and simpler dependencies for a documentation-only
  workflow.
- Output is best-effort and may omit or approximate advanced constraints.
- If higher fidelity or validation-ready schemas are required later, the script
  can be extended or replaced with a Pydantic-based pipeline.
