# Plan: Decouple Ingest and Index Pipelines via catalog/sync.py

## Context

DatasetIngestPipeline currently instantiates and calls DatasetIndexPipeline directly (lines 331-345 of ingest/pipelines.py). This couples the two stages. The user wants:
1. Ingest pipeline returns after persistence -- does NOT call index
2. Index pipeline loads its own documents from DB by dataset_id
3. A new orchestrator `catalog/sync.py` coordinates the two stages
4. `catalog/index/index.py` (IndexSync) is removed; its job-loading logic moves to sync.py
5. Index pipeline supports instantiation without dataset_id for manual testing

## Changes

### 1. Update `DatasetIndexPipeline` to load documents from DB (`catalog/index/pipelines.py`)

Remove the `nodes` parameter from `index()`. Instead, load active documents from the database:

```python
def _load_nodes(self) -> list[BaseNode]:
    """Load active documents from DB and convert to LlamaIndex nodes."""
    doc_repo = DocumentRepository()
    docs = doc_repo.list_by_parent(self.dataset_id, active_only=True)
    nodes = []
    for doc in docs:
        metadata = doc.metadata_json or {}
        metadata["doc_id"] = doc.id
        metadata["relative_path"] = doc.path
        if doc.title:
            metadata["title"] = doc.title
        if doc.description:
            metadata["description"] = doc.description
        node = LlamaDocument(text=doc.body, metadata=metadata, id_=doc.path)
        nodes.append(node)
    return nodes

def index(self, vector_manager=None) -> IndexResult:
    nodes = self._load_nodes()
    # ... rest of pipeline run
```

Also support `index(nodes=...)` override for manual testing (if nodes passed, use them; otherwise load from DB).

### 2. Remove index call from `DatasetIngestPipeline.ingest()` (`catalog/ingest/pipelines.py`)

Remove lines 331-345 (the `DatasetIndexPipeline` import and call). Remove the merging of index stats into IngestResult. The ingest method returns after persistence + deletion sync + cache persist.

Remove `chunks_created` and `vectors_inserted` from IngestResult (`catalog/ingest/schemas.py`) since those are now exclusively IndexResult concerns.

### 3. Create `catalog/sync.py` -- the new orchestrator

This replaces `catalog/index/index.py` (IndexSync). It:
- Loads job configs from YAML (reuse `DatasetJob.from_yaml()` from `catalog/ingest/job.py`)
- For each job: runs ingest, then runs index
- Provides `sync_dataset(config)` as the main entry point

```python
class DatasetSync:
    """Orchestrates ingest -> index for dataset jobs."""

    def sync(self, config: DatasetSourceConfig) -> SyncResult:
        """Run ingest then index for a single dataset."""
        ingest_pipeline = DatasetIngestPipeline(ingest_config=config)
        ingest_result = ingest_pipeline.ingest()

        index_pipeline = DatasetIndexPipeline(
            dataset_id=ingest_result.dataset_id,
            dataset_name=ingest_result.dataset_name,
        )
        index_result = index_pipeline.index()

        return SyncResult(ingest=ingest_result, index=index_result)

    def load_jobs(self) -> list[DatasetSourceConfig]:
        """Load job configs from YAML files."""
        # Move logic from IndexSync.load_jobs()

    async def arun(self):
        """Run all configured jobs."""
        # Move logic from IndexSync.arun()
```

Add `SyncResult` (composite of IngestResult + IndexResult) to `catalog/sync.py` or a schemas file.

### 4. Delete `catalog/index/index.py`

Its logic moves to `catalog/sync.py`.

### 5. Update `catalog/ingest/schemas.py`

Remove `chunks_created` and `vectors_inserted` from `IngestResult` -- those belong to `IndexResult`.

## Files

| File | Action |
|---|---|
| `catalog/sync.py` | NEW -- `DatasetSync` orchestrator, `SyncResult` |
| `catalog/index/pipelines.py` | Update `index()` to load docs from DB; accept optional `nodes` override |
| `catalog/ingest/pipelines.py` | Remove lines 331-345 (index pipeline call + stat merging) |
| `catalog/ingest/schemas.py` | Remove `chunks_created`, `vectors_inserted` from IngestResult |
| `catalog/index/index.py` | DELETE -- logic moved to sync.py |

## Verification

1. `uv run python -c "from catalog.sync import DatasetSync, SyncResult"` -- imports work
2. `uv run python -c "from catalog.index.pipelines import DatasetIndexPipeline"` -- still works
3. Run differential tests from project root: `make agent-test`
4. Verify IngestResult no longer has chunks_created/vectors_inserted
5. Verify DatasetIndexPipeline can be instantiated without dataset_id for manual testing
