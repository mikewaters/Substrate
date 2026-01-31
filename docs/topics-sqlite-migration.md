# Topics Module SQLite Migration

This document records the steps taken to migrate the `ontology.topics` module from PostgreSQL to SQLite and the architectural decisions made.

## Goals
- Eliminate dependency on external PostgreSQL service for local/dev usage.
- Preserve domain logic and Pydantic validation.
- Keep tests fast, isolated, and deterministic using a temp file-backed SQLite DB.

## Summary of Changes
1. Configuration
   - `config.database` now holds `db_path` and `pragmas` instead of PG host/port/user.
   - Tests override `config.database.db_path` with a temporary file.

2. Connection Management (`database.py`)
   - Replaced psycopg2 pool with `SQLiteManager` producing fresh `sqlite3.Connection` objects.
   - Applied pragmas (`foreign_keys=ON`, `journal_mode=WAL`, etc.) per connection.
   - Added `get_db_connection()` context manager using `BEGIN IMMEDIATE` to ensure transactional rollback semantics for DDL in tests.
   - Added `transactional` decorator to mimic previous manual transaction control.

3. ORM Models (`models.py`)
   - UUID columns stored as `String(36)` (text) rather than PG UUID type.
   - Arrays / JSONB replaced by SQLite JSON1 (`SQLITE_JSON`) or TEXT.
   - Dropped PG-specific indexes (GIN) and dialect-specific types.
   - Constraints preserved via `CheckConstraint` and `UniqueConstraint` where feasible.

4. Repository (`topic_repository.py`)
   - Switched parameter placeholders to `?` for sqlite3 API.
   - Implemented explicit JSON serialization/deserialization for `aliases` and `external_refs`.
   - Implemented simple case-insensitive title search using `LOWER(title) LIKE LOWER(?)`.
   - Added slug auto-generation and UTC timestamp handling with `datetime.now(timezone.utc).isoformat()`.

5. Service Layer (`taxonomy_service.py`)
   - Ensure timestamps (`created_at`, `updated_at`) are populated prior to Pydantic response validation.
   - Cast incoming UUID arguments to `str` in queries (since PK stored as text).
   - Filter `None` values out during update operations to avoid wiping required fields.

6. Tests
   - Reworked `conftest.py` to create a single temporary SQLite DB for the session.
   - Added idempotent minimal DDL inside `test_topic_repository.py` fixture for raw sqlite repository tests to prevent race/lock conditions.
   - Adjusted expectations from PG-specific behavior (e.g., JSON binding) to new serialization.
   - Converted UUID usage in direct sqlite tests to strings where necessary.
   - Updated taxonomy service tests to differentiate Pydantic field length validation from service-level validation.
   - Added integration tests using SQLAlchemy session with temporary file DB.

7. Transaction Semantics
   - Use `BEGIN IMMEDIATE` to group DDL/DML for rollback tests; avoids SQLite auto-commit of DDL when executed outside a transaction.

8. Performance / Concurrency
   - Enabled WAL for better read concurrency; acceptable for local dev.

## Removed / Deprecated
- PostgreSQL connection pooling (psycopg2).
- PG-specific data types and index strategies.
- Fuzzy search similarity scoring (replaced by LIKE pattern).

## Follow-up Suggestions
- Consider registering custom pytest `integration` mark to silence warnings.
- Add migration notes to main `README.md` linking to this file.
- Evaluate whether to keep `alembic` if schema evolution is now simple; could still be useful for production migrations.

## Dependency Cleanup
- Removed `psycopg2-binary` from dependencies (see pyproject update).
- Audit for any lingering PG-only utilities or environment variables (none found in topics module after migration).

## Edge Cases Considered
- Rollback of DDL (ensured via explicit transaction start).
- Serialization of empty `aliases` / `external_refs` (normalized to JSON `[]` / `{}`).
- Updates with explicit `None` values (ignored rather than nulling required fields).
- Rapid test execution causing database locks (resolved by removing per-test metadata creation).

---
Document last updated: 2025-10-17
