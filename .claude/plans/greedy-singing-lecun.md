# Heptabase Integration Implementation Plan

## Summary

Create `catalog.integrations.heptabase` that reuses all Obsidian infrastructure, customizing only link extraction and VaultSchema. Three small modifications to existing code, four new files.

## Existing Code Modifications

### 1. Make link extraction overridable in ObsidianVaultReader

**File:** `src/catalog/catalog/integrations/obsidian/reader.py`

Add `_extract_links` method to `ObsidianVaultReader`:
```python
def _extract_links(self, text: str) -> list[str]:
    """Extract link targets from text. Override for different formats."""
    return extract_wikilinks(text)
```

Change line 578 in `load_data()`:
- Before: `raw_wikilinks = extract_wikilinks(doc.text)`
- After: `raw_wikilinks = self._extract_links(doc.text)`

### 2. Add MARKDOWN_LINK to DocumentLinkKind enum

**File:** `src/catalog/catalog/store/models.py` (line 80)

```python
class DocumentLinkKind(str, enum.Enum):
    WIKILINK = "wikilink"
    MARKDOWN_LINK = "markdown_link"
```

Also update `src/catalog/catalog/store/models/catalog.py` (same enum, line 87).

### 3. Make LinkResolutionTransform link kind configurable

**File:** `src/catalog/catalog/integrations/obsidian/transforms.py`

- Add `link_kind: DocumentLinkKind = DocumentLinkKind.WIKILINK` parameter to `__init__`
- Change line 198: `link_repo.upsert(doc_id, target_id, self._link_kind)`

## New Files

### 4. `catalog/integrations/heptabase/__init__.py`
- Exports + registration (`@register_ingest_config_factory("heptabase")`, `@create_source.register`, `@create_reader.register`)
- Factory: `create_heptabase_ingest_config(source_config)` -> `IngestHeptabaseConfig`
- Pattern: identical to obsidian/__init__.py

### 5. `catalog/integrations/heptabase/reader.py`
- **`extract_heptabase_links(text)`** - regex `\[([^\]]*)\]\(\./([^)]+)\)` extracts `[Display](./Target.md)` links, strips `.md` extension to get note stem
- **`HeptabaseVaultReader(ObsidianVaultReader)`** - overrides only `_extract_links()` to call `extract_heptabase_links`
- **`HeptabaseVaultSource(BaseSource)`** - same structure as `ObsidianVaultSource` but uses `HeptabaseVaultReader` and passes `link_kind=DocumentLinkKind.MARKDOWN_LINK` to `LinkResolutionTransform`
- Reuses: `ObsidianMarkdownNormalize`, `FrontmatterTransform`, `MarkdownNodeParser`, `LinkResolutionTransform`

### 6. `catalog/integrations/heptabase/schemas.py`
- **`IngestHeptabaseConfig(DatasetIngestConfig)`** - type_name="heptabase", vault_schema field
- Validation: path exists, is directory (no `.obsidian` check)
- Auto-derives dataset_name from source_path.name

### 7. `catalog/integrations/heptabase/vault_schema.py`
- **`HeptabaseVaultSchema(VaultSchema)`** - subclasses obsidian's VaultSchema
- Same from_frontmatter/to_document_meta mechanism, ready for Heptabase-specific field customization

### 8. Register in integrations init

**File:** `src/catalog/catalog/integrations/__init__.py`

Add: `from catalog.integrations import heptabase  # noqa: F401`

## Tests

### `tests/idx/unit/integrations/heptabase/test_link_extraction.py`
- Extracts `[Note.md](./Note.md)` -> `"Note"`
- Handles spaces: `[My Note.md](./My Note.md)` -> `"My Note"`
- Deduplicates multiple identical links
- Ignores external URLs `[text](https://example.com)`
- Ignores non-internal links `[text](other.md)` (no `./` prefix)
- Returns empty list for no links

### `tests/idx/unit/integrations/heptabase/test_config.py`
- Valid directory accepted
- Missing path rejected
- Non-directory rejected
- Auto-derives dataset_name

### `tests/idx/unit/integrations/heptabase/test_source.py`
- Source registration works (`create_ingest_config` with type="heptabase")
- `create_source` dispatches to `HeptabaseVaultSource`

## Parallelization

Steps 1-3 (existing file modifications) can be done in parallel.
Steps 4-8 (new files + registration) depend on steps 1-3.
Tests can run after all code is written.

## Verification

```bash
# Run new tests
make agent-test TESTPATH=tests/idx/unit/integrations/heptabase

# Run obsidian tests to verify no regressions
make agent-test TESTPATH=tests/idx/unit/integrations/obsidian

# Smoke test with a heptabase export directory (if available)
uv run python -m catalog.ingest.pipelines_v2 /path/to/heptabase/export --type heptabase
```
