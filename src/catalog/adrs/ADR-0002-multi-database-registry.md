# ADR-0002: Multi-Database Registry

### Status
Accepted

### Context
The catalog module needs to support multiple SQLite databases for separation of concerns (catalog metadata, content storage, future analytics). The current implementation uses singleton `@lru_cache` on `get_engine()` and `get_session_factory()` for a single database.

### Decision
Introduce a singleton `DatabaseRegistry` class that:
1. Manages multiple named engines and session factories
2. Ensures all databases are created before any connections (enabling reliable ATTACH)
3. Provides `get_engine(db="catalog")` API with backward-compatible defaults
4. Automatically ATTACHes the content database to catalog connections

### Alternatives Considered
- **Multiple independent singletons** (one per database): Rejected — no centralized lifecycle control, harder to coordinate ATTACH
- **Dependency injection only**: Rejected — too much churn for existing code expecting module-level functions

### Consequences
- Centralized database lifecycle management
- ATTACH always succeeds (all DBs exist before connections)
- Tests can replace the singleton registry for isolation
- Existing code works unchanged via default `db="catalog"`

### Implementation Notes

**Database Initialization Order:**
1. Create all engines (catalog, content)
2. Create all tables via `metadata.create_all()`
3. Register ATTACH event listener on catalog engine

**WAL Mode and Transaction Atomicity:**

With WAL (Write-Ahead Logging) mode enabled for better concurrent access, transactions spanning attached databases are **NOT fully atomic**. From SQLite documentation:

> "If main is :memory: or journal_mode is WAL, transactions are atomic only within individual database files."

This means:
- Writes within the catalog database are atomic
- Writes within the content database are atomic
- A transaction that writes to both databases may leave them in inconsistent states on crash

**Accepted Trade-off:** WAL mode provides significantly better read/write concurrency, which is more important for this use case. Content operations are expected to be independent of catalog metadata changes in most scenarios.

---
