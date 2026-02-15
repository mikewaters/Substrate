# Plan: Multi-Backend Parametrized Vector Store Tests

## Context

Tests currently run against a single vector backend (usually Qdrant). With Zvec added and more backends coming, we need a way to automatically run selected tests against every supported backend without hardcoding backend names. The existing E2E tests (`test_qdrant_e2e.py`, `test_zvec_e2e.py`) duplicate test logic across separate files. We want a shared parametrized fixture that discovers backends from the settings type annotation.

## Approach

### 1. Create shared backend discovery module

**New file**: `tests/backends.py`

- `get_supported_backends() -> list[str]` -- uses `typing.get_args()` on `VectorDBSettings.backend` field annotation (`Literal["qdrant", "zvec"]`) to dynamically extract backend names. Adding a new value to the Literal automatically includes it in tests.
- `configure_backend(monkeypatch, backend, output_dir)` -- extracted from the existing `_configure_backend()` in `tests/e2e/evals/test_vector_store_comparison.py:69-85`. Handles env var setup including zvec-specific gating.
- `SUPPORTED_BACKENDS: list[str]` -- module-level constant for easy import.

### 2. Add `vector_backend` fixture to E2E conftest

**Modified file**: `tests/e2e/conftest.py`

Add a parametrized fixture:
```python
@pytest.fixture(params=SUPPORTED_BACKENDS)
def vector_backend(request, e2e, monkeypatch):
    """Configure active vector backend per test invocation."""
    backend = request.param
    configure_backend(monkeypatch, backend, e2e.output_dir)
    yield backend
```

This runs each test that uses the fixture once per backend.

### 3. Apply `vector_backend` to selected E2E tests

**Modified file**: `tests/e2e/test_catalog_e2e.py`

Add `vector_backend` parameter to:
- `TestHybridSearch.test_hybrid_search_returns_results` -- exercises hybrid (FTS + vector) search through the full production code path. Currently only runs against default Qdrant.
- `TestHybridSearch.test_full_pipeline_ingest_search_rerank` -- full pipeline flow (ingest -> hybrid search -> rerank). Backend-agnostic behavior that should work identically across backends.

These tests already use the `e2e` fixture and don't spy on backend internals, making them ideal candidates.

### 4. Refactor comparison eval to use shared helper

**Modified file**: `tests/e2e/evals/test_vector_store_comparison.py`

Replace the local `_configure_backend()` with an import from `tests/backends.py`.

### 5. Tests NOT selected (and why)

| Test | Reason |
|------|--------|
| `test_qdrant_e2e.py` / `test_zvec_e2e.py` | Backend-specific spy logic (verifies internal method was called). Keep separate. |
| `TestIngestAndSearch` (FTS tests) | FTS-only; vector backend irrelevant. |
| `TestObsidianLinks`, `TestFrontmatterOntology` | Test metadata/links, not vector search. |
| Integration tests (`test_hybrid_ingestion.py`, etc.) | Mock VectorStoreManager entirely via `patched_embedding`; backend setting has no effect. |
| Unit tests (`test_vector.py`) | Already have backend-specific test classes; mocking makes parametrization meaningless. |

## Files to modify

| File | Action |
|------|--------|
| `tests/backends.py` | **Create** -- backend discovery + `configure_backend()` helper |
| `tests/e2e/conftest.py` | **Edit** -- add `vector_backend` fixture |
| `tests/e2e/test_catalog_e2e.py` | **Edit** -- add `vector_backend` param to 2 hybrid search tests |
| `tests/e2e/evals/test_vector_store_comparison.py` | **Edit** -- import shared `configure_backend` |

## Key reuse

- `_configure_backend()` from `tests/e2e/evals/test_vector_store_comparison.py:69-85` -- already handles zvec env var gating correctly
- `typing.get_args()` on `VectorDBSettings.__fields__["backend"].annotation` (Pydantic v2) to extract Literal members
- `get_settings.cache_clear()` pattern already used throughout tests

## Verification

1. `uv run pytest tests/e2e/test_catalog_e2e.py::TestHybridSearch -v` -- should show each test running twice (once `[qdrant]`, once `[zvec]`)
2. `uv run pytest tests/e2e/evals/test_vector_store_comparison.py -v` -- should still pass with refactored import
3. `uv run pytest tests/e2e/ -v` -- full E2E suite passes
4. Verify by temporarily adding a fake backend to the Literal that it appears in parametrize output (then revert)
