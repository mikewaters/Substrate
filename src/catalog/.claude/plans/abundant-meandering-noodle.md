# Plan: Ingest `format`, `media_type`, `subject` Through the Catalog Pipeline

## Context

The Resource ORM, Pydantic schemas, and repository layer already have `format`, `media_type`, and `subject` columns/fields (added earlier this session). What's missing is **pipeline-level ingestion** -- getting values into these fields during the document processing flow.

The design mirrors how `title` and `description` already flow: sources set initial metadata, OntologyMapper enriches from frontmatter, PersistenceTransform reads and persists.

## Data Flow

```
Source (DirectorySource / ObsidianVaultReader)
  |-- sets node.metadata["_format"] = "Markdown"     (from file extension)
  |-- sets node.metadata["_media_type"] = "text/markdown"  (from mimetypes)
  v
OntologyMapper
  |-- reads frontmatter["subject"] -> DocumentMeta.subject
  |-- writes node.metadata["_subject"] = doc_meta.subject
  |-- (format/media_type pass through unchanged from source)
  v
PersistenceTransform
  |-- reads _format, _media_type, _subject from node.metadata
  |-- sets on Document ORM (which inherits these columns from Resource)
```

Underscore-prefixed keys (`_format`, `_media_type`, `_subject`) follow the existing `_ontology_meta` convention for pipeline-internal metadata that should not leak into embeddings.

## Changes

### 1. Sources: Set `_format` and `_media_type`

**`catalog/ingest/directory.py`** -- DirectorySource
- Add `_extension_to_format()` helper mapping extensions to human-readable format names (`.md` -> `"Markdown"`, `.pdf` -> `"PDF"`, etc.)
- Use `mimetypes.guess_type()` for media_type
- Set `_format` and `_media_type` in each Document's metadata dict

**`catalog/integrations/obsidian/reader.py`** -- ObsidianVaultReader
- In `get_file_metadata()` (which already sets `file_type: "text/markdown"`), add `_media_type` and `_format` keys
- Keep existing `file_type` key for backward compatibility

**Heptabase** -- no changes needed, inherits from ObsidianVaultReader

### 2. DocumentMeta: Add `subject` field

**`catalog/ontology/schema.py`**
- Add `subject: str | None = None` to DocumentMeta dataclass
- Update `to_dict()` and `from_dict()` to handle it

`format`/`media_type` are NOT added to DocumentMeta -- they're file-intrinsic properties, not content metadata.

### 3. OntologyMapper: Extract `subject` from frontmatter

**`catalog/transform/ontology.py`**
- In `_build_document_meta()`: add `"subject"` to known_keys, extract from frontmatter
- In `_process_node()`: after writing title/description, write `meta["_subject"] = doc_meta.subject`
- VaultSpec compatibility is automatic: `_VALID_ONTOLOGY_TARGETS` is computed from DocumentMeta fields

### 4. PersistenceTransform: Read and persist all three

**`catalog/transform/llama.py`** -- `_process_node()` method
- Extract `_format`, `_media_type`, `_subject` from node.metadata (alongside existing title/description extraction)
- **Update path** (existing docs): set `existing.format`, `existing.media_type`, `existing.subject` when non-None
- **Create path** (new docs): pass to `doc_repo.create()`

**`catalog/store/repositories.py`** -- `DocumentRepository.create()`
- Add `format`, `media_type`, `subject` keyword parameters
- Pass to Document constructor

### 5. Tests

- **OntologyMapper unit tests**: subject extracted from frontmatter, written to `_subject`
- **PersistenceTransform unit tests**: all three fields persisted on create and update, NULL when absent
- **DirectorySource unit tests**: `_format` and `_media_type` set from file extension
- **DocumentMeta unit tests**: subject round-trip through `to_dict()`/`from_dict()`
- **Integration test** (`test_frontmatter_ontology.py`): end-to-end subject flow from vault frontmatter to DB

## Verification

1. Run existing tests to confirm no regressions: `uv run pytest src/catalog/tests/ -v` (from workspace root)
2. New tests validate the full flow from source metadata through transforms to database columns
