# Plan: Wire Snippet Formatting into Search Results

## Context

`formatting.py` defines `Snippet` (dataclass) and `extract_snippet()` -- both implemented and tested, but not wired into any search path. The feature spec (`features/snippet-formatters.md`) proposes a rich snippet system with strategies, spans, sanitization, etc. We're adapting the **minimal useful subset** to our architecture: add a snippet to every `SearchResult` so consumers get formatted, provenance-tracked text.

The spec's future concerns (spans, sanitization, strategy selection, FTS5 `snippet()`) are explicitly out of scope.

## Changes

### 1. Add `SnippetResult` Pydantic model to `models.py`

Per project conventions: dataclasses for internals, Pydantic for I/O. The existing `Snippet` dataclass stays (internal), and we add a Pydantic equivalent for the API surface.

```python
class SnippetResult(BaseModel):
    text: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    header: str
```

**On `SearchResult`**: Replace `chunk_text: str | None` with `snippet: SnippetResult | None`. Pre-alpha, no backward compat.

**File**: `catalog/search/models.py`

### 2. Add `build_snippet` utility to `formatting.py`

A simpler variant of `extract_snippet` that works without `doc_content` (which we don't have at search time). Builds a snippet from chunk text alone, with line numbers relative to the chunk (start_line=1).

```python
def build_snippet(chunk_text: str, doc_path: str, max_lines: int | None = None) -> Snippet:
```

This avoids duplicating truncation + header logic across service.py and vector.py.

**File**: `catalog/search/formatting.py`

### 3. Wire snippets into `SearchService._nodes_to_search_results`

Replace `chunk_text=node.node.get_content()` with a call to `build_snippet` -> convert to `SnippetResult`.

**File**: `catalog/search/service.py` (line ~414)

### 4. Wire snippets into `VectorSearch.search`

Replace `chunk_text=chunk_text` with `build_snippet` -> `SnippetResult`.

**File**: `catalog/search/vector.py` (line ~226)

### 5. Pass `snippet` through bonus + rerank paths

- `_apply_top_rank_bonus` (line ~448): `chunk_text=result.chunk_text` -> `snippet=result.snippet`
- `_apply_rerank` (line ~502): use `result.snippet.text` for TextNode text; (line ~523): `chunk_text=original.chunk_text` -> `snippet=original.snippet`
- `llm/reranker.py` (line ~156, ~294-299): read from `result.snippet.text` instead of `result.chunk_text`

**Files**: `catalog/search/service.py`, `catalog/llm/reranker.py`

### 6. Update consumers

- `catalog/api/mcp/tools.py` (line ~77): `"chunk_text": result.chunk_text` -> serialize snippet
- `catalog/search/__init__.py`: export `SnippetResult`, `build_snippet`

### 7. Update tests

All test files constructing `SearchResult(chunk_text=...)` must switch to `snippet=SnippetResult(...)` or `snippet=None`. Key files:
- `tests/idx/unit/search/test_service.py`
- `tests/idx/unit/search/test_formatting.py` (add `build_snippet` tests)
- `tests/idx/unit/llm/test_reranker.py`
- `tests/idx/unit/api/test_mcp_tools.py`
- `tests/idx/unit/cli/test_search_cli.py`
- `tests/idx/integration/test_vector_hybrid_rerank.py`
- `tests/rag_v2/test_eval.py`
- `tests/e2e/test_catalog_e2e.py`

## Verification

```bash
uv run pytest src/catalog/tests/idx/unit/search/ -v
uv run pytest src/catalog/tests/idx/unit/llm/test_reranker.py -v
uv run pytest src/catalog/tests/idx/unit/api/test_mcp_tools.py -v
uv run pytest src/catalog/tests/idx/unit/cli/test_search_cli.py -v
```
