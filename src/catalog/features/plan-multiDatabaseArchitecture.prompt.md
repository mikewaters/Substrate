# Multi-Database Architecture Requirements

## Overview

Support multiple SQLite databases within the catalog module, enabling separation of concerns while preserving cross-database query capability via SQLite ATTACH.

**Initial databases:**
- `catalog` — metadata, documents, chunks, FTS (default)
- `content` — future use (stub only in Phase 1)

**Out of scope:** Vector store (managed separately, not in relational database)

---

## R1: Database Registry (Singleton)

### Requirement
Replace singleton engine caching with a singleton registry that manages multiple named databases.

### Implementation Decisions
- **Registry class**: `DatabaseRegistry` in database.py — singleton via `@lru_cache` on factory function
- **Default database**: `"catalog"` — `get_engine()` defaults to `"catalog"` for backward compatibility
- **Initial databases**: `catalog`, `content`
- **Singleton access**: `get_registry() -> DatabaseRegistry` (cached), with `get_engine(db="catalog")` and `get_session(db="catalog")` convenience functions

**Related ADR:** `adrs/ADR-0002-multi-database-registry.md`

---

## R2: Database Initialization Order

### Requirement
All databases created before any connections are made; ATTACH always succeeds.

### Implementation Decisions
- **Initialization sequence** in `DatabaseRegistry.__init__()`:
  1. Create all engines (catalog, content)
  2. Run `Base.metadata.create_all(engine)` for each database
  3. Only then register ATTACH event listeners
- **Guarantees**: When first connection is made, all attached DBs exist
- **File creation**: SQLAlchemy auto-creates SQLite files; `create_all()` creates tables

---

## R3: Per-Database Models

### Requirement
Each database has its own `Base` class and models; no model sharing.

### Implementation Decisions
- **Separate Base classes**: `CatalogBase`, `ContentBase`
- **Directory structure**:
  - `store/models/catalog.py` — existing models (Resource hierarchy, Dataset, FTS)
  - `store/models/content.py` — stub with `ContentBase` only
  - `store/models/__init__.py` — re-exports `CatalogBase` as `Base` for backward compatibility
- **Schema creation**: Each Base's `metadata.create_all(engine)` in registry init

---

## R4: Cross-Database Query Support

### Requirement
Support cross-database queries between `catalog` and `content` via ATTACH.

### Implementation Decisions
- **Mechanism**: SQLite `ATTACH DATABASE` via `connect` event on `catalog` engine
- **Pool strategy**: `QueuePool` (default) — ATTACH persists for pooled connections
- **Event registration**: After all DBs created, register event to attach `content` to `catalog` connections
- **ORM access**: Cross-db models use `__table_args__ = {"schema": "content"}`

---

## R5: Configuration via Settings

### Requirement
Database paths configured via Settings module with environment variable overrides.

### Implementation Decisions
- **Settings structure** in settings.py:
  ```python
  class DatabasesSettings(BaseSettings):
      catalog_path: Path = Path("~/.idx/catalog.db")
      content_path: Path = Path("~/.idx/content.db")
  ```
- **Environment variables**: `IDX_DATABASES__CATALOG_PATH`, `IDX_DATABASES__CONTENT_PATH`
- **Deprecation**: Existing `database_path` → warning + map to `databases.catalog_path`

---

## R6: Session Context Updates

### Requirement
Ambient session context supports keyed access for multiple databases.

### Implementation Decisions
- **ContextVar type**: `ContextVar[dict[str, Session]]`
- **API signatures**:
  - `current_session(db: str = "catalog") -> Session`
  - `use_session(session: Session, db: str = "catalog") -> ContextManager`
- **Backward compatibility**: Default `db="catalog"`

---

## R7: FTS Placement

### Requirement
FTS virtual tables remain in `catalog` database.

### Implementation Decisions
- **No change**: `documents_fts` and `chunks_fts` stay in `catalog`
- **Rationale**: JOINs with `documents` table required for filtering

---

## R8: Test Infrastructure

### Requirement
Tests continue working with current patterns.

### Implementation Decisions
- **No enforced changes**: Tests patch as needed
- **Registry replacement**: Tests can replace singleton registry for isolation

---

## Summary of Changes

| File | Changes |
|------|---------|
| `store/database.py` | Add `DatabaseRegistry` class, `get_registry()`, update `get_engine(db=)`, ATTACH event |
| `store/session_context.py` | ContextVar → `dict[str, Session]`, keyed API |
| `store/models/__init__.py` | Re-export `CatalogBase` as `Base` |
| `store/models/catalog.py` | New file, move existing models |
| `store/models/content.py` | New file, `ContentBase` stub |
| `core/settings.py` | Add `DatabasesSettings`, deprecate `database_path` |

---


