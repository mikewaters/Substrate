# ADR-0002: Multi-Database Registry (Draft)

### Status
Proposed

### Context
The catalog module needs to support multiple SQLite databases for separation of concerns (catalog metadata, content storage, future analytics). The current implementation uses singleton `@lru_cache` on `get_engine()` and `get_session_factory()` for a single database.

### Decision
Introduce a singleton `DatabaseRegistry` class that:
1. Manages multiple named engines and session factories
2. Ensures all databases are created before any connections (enabling reliable ATTACH)
3. Provides `get_engine(db="catalog")` API with backward-compatible defaults

### Alternatives Considered
- **Multiple independent singletons** (one per database): Rejected — no centralized lifecycle control, harder to coordinate ATTACH
- **Dependency injection only**: Rejected — too much churn for existing code expecting module-level functions

### Consequences
- Centralized database lifecycle management
- ATTACH always succeeds (all DBs exist before connections)
- Tests can replace the singleton registry for isolation
- Existing code works unchanged via default `db="catalog"`

---
