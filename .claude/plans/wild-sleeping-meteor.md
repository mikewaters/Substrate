# Plan: Migrate from SimpleVectorStore to Qdrant

## Overview

Replace LlamaIndex's `SimpleVectorStore` (JSON persistence) with `QdrantVectorStore` (local persistent mode) in the catalog module. This provides better performance, native filtering, and more robust persistence.

## Key Files to Modify

1. **`src/catalog/pyproject.toml`** - Add dependencies
2. **`src/catalog/catalog/core/settings.py`** - Add Qdrant/embedding settings
3. **`src/catalog/catalog/store/vector.py`** - Core rewrite
4. **`src/catalog/catalog/transform/llama.py`** - Add `dataset_name` metadata
5. **`src/catalog/tests/idx/conftest.py`** - Update test fixtures

## Implementation Steps

### 1. Add Dependencies

```bash
cd src/catalog && uv add llama-index-vector-stores-qdrant qdrant-client
```

### 2. Update Settings (`catalog/core/settings.py`)

Add `embedding_dim` to `EmbeddingSettings`:
```python
embedding_dim: int = Field(
    default=384,  # MiniLM-L6-v2 dimension
    ge=1,
    description="Embedding vector dimension",
)
```

Add new `QdrantSettings` class:
```python
class QdrantSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IDX_QDRANT_", extra="ignore")
    collection_name: str = Field(default="catalog_vectors", description="Collection name")
```

Add to `Settings` class:
```python
qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
```

### 3. Rewrite VectorStoreManager (`catalog/store/vector.py`)

Key changes:
- Replace `SimpleVectorStore` with `QdrantVectorStore`
- Add `qdrant_client.QdrantClient(path=persist_dir)` for local storage
- Collection auto-created with correct dimensions
- `persist()` becomes no-op (Qdrant auto-persists)
- `delete_by_dataset()` uses Qdrant's filter-based deletion

New internal methods:
```python
def _get_client(self) -> QdrantClient:
    """Lazy-initialize Qdrant client with local path storage."""

def _ensure_collection(self) -> None:
    """Create collection if not exists with VectorParams(size=384, distance=COSINE)."""
```

Public API remains unchanged:
- `load_or_create()` - Returns VectorStoreIndex backed by Qdrant
- `get_vector_store()` - Returns QdrantVectorStore for pipeline integration
- `insert_nodes()`, `delete_nodes()`, `get_retriever()` - Delegate to index (unchanged)
- `persist()`, `persist_vector_store()` - No-op (Qdrant auto-persists)
- `delete_by_dataset()` - Uses Qdrant filter on `dataset_name` field

### 4. Add dataset_name to Node Metadata (`catalog/transform/llama.py`)

In `ChunkPersistenceTransform`, add `dataset_name` as a separate metadata field:
```python
node.metadata["dataset_name"] = self.dataset_name
```

This enables efficient exact-match filtering in Qdrant instead of prefix matching.

### 5. Create Payload Index for Fast Filtering

In `_ensure_collection()`, add a keyword index on `dataset_name`:
```python
client.create_payload_index(
    collection_name=collection_name,
    field_name="dataset_name",
    field_schema="keyword",
)
```

### 6. Update Test Fixtures (`tests/idx/conftest.py`)

- Update `mock_vector_store` to mock `QdrantVectorStore`
- For integration tests, use in-memory Qdrant: `QdrantClient(location=":memory:")`

## Migration Notes

Per AGENTS.md (no backward compatibility):
- Delete existing `~/.idx/vector_store/` directory
- Re-run ingestion to populate Qdrant
- No JSON import needed

## Verification

1. Run differential tests: `make agent-test TESTPATH=tests/idx`
2. Test ingestion: `uv run python -m catalog.cli ingest --source vault --force`
3. Test search: `uv run python -m catalog.cli search "test query"`
4. Verify persistence: restart process, confirm vectors still accessible

## Dependencies to Add

```
llama-index-vector-stores-qdrant>=0.4.0
qdrant-client>=1.12.0
```
