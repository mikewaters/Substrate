# C2 Component Diagram: Ingestion Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                     catalog (Ingestion System)                                   │
│                                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │                                    ENTRY POINTS                                             │ │
│  │                                                                                             │ │
│  │  ┌──────────────────────┐    ┌──────────────────────────┐    ┌────────────────────────┐    │ │
│  │  │   CLI __main__       │    │    DatasetJob             │    │ Manual / Programmatic  │    │ │
│  │  │                      │    │                          │    │                        │    │ │
│  │  │ python -m catalog.   │    │ Hydra YAML config loader │    │ Direct instantiation   │    │ │
│  │  │ ingest.pipelines     │    │ Pydantic model           │    │ of pipeline + config   │    │ │
│  │  │ <path_or_yaml>       │    │                          │    │                        │    │ │
│  │  │ [--force]            │    │ .source: SourceConfig     │    │ DatasetIngestConfig +  │    │ │
│  │  │                      │    │ .embedding: EmbedConfig   │    │ Pipeline constructor   │    │ │
│  │  │                      │    │ .pipeline: PipelineConfig │    │                        │    │ │
│  │  └──────────┬───────────┘    └────────────┬─────────────┘    └───────────┬────────────┘    │ │
│  │             │                             │                              │                  │ │
│  └─────────────┼─────────────────────────────┼──────────────────────────────┼──────────────────┘ │
│                │                             │                              │                    │
│                └──────────────┬───────────────┘                              │                    │
│                               │ creates                                     │                    │
│                               ▼                                             │                    │
│  ┌─────────────────────────────────────────────────┐                        │                    │
│  │              CONFIGURATION                       │                        │                    │
│  │                                                  │◄───────────────────────┘                    │
│  │  ┌────────────────────────────────────────────┐  │                                            │
│  │  │ DatasetIngestConfig (base)                 │  │       ┌──────────────────────────────┐     │
│  │  │ .source_path .dataset_name .force          │  │       │ Settings (core.settings)     │     │
│  │  │                                            │  │       │                              │     │
│  │  │  ┌─────────────────┐ ┌──────────────────┐  │  │       │ .embedding: EmbeddingSettings │     │
│  │  │  │IngestDirectory  │ │IngestObsidian    │  │  │       │ .rag_v2: RAGv2Settings       │     │
│  │  │  │Config           │ │Config            │  │  │       │ .qdrant: QdrantSettings      │     │
│  │  │  │                 │ │                  │  │  │       │ .database_path              │     │
│  │  │  │.patterns        │ │.vault_schema     │  │  │       │ .vector_store_path          │     │
│  │  │  │.encoding        │ │                  │  │  │       │ .cache_path                 │     │
│  │  │  └─────────────────┘ └──────────────────┘  │  │       └──────────────┬───────────────┘     │
│  │  └────────────────────────────────────────────┘  │                      │ read by all          │
│  └──────────────────────┬───────────────────────────┘                      │                      │
│                         │ dispatches via                                   │                      │
│                         │ Source Factory                                   │                      │
│                         ▼                                                  │                      │
│  ┌──────────────────────────────────────────────────────┐                  │                      │
│  │                   SOURCE LAYER                        │                  │                      │
│  │                                                       │                  │                      │
│  │  ┌────────────────────────────────────────────────┐   │                  │                      │
│  │  │ BaseSource (abstract)                          │   │                  │                      │
│  │  │ .documents -> list[Document]                   │   │                  │                      │
│  │  │ .get_transforms(dataset_id) -> (pre, post)     │   │                  │                      │
│  │  └─────────────────┬──────────────────────────────┘   │                  │                      │
│  │                    │                                   │                  │                      │
│  │    ┌───────────────┴───────────────────┐               │                  │                      │
│  │    │                                   │               │                  │                      │
│  │    ▼                                   ▼               │                  │                      │
│  │  ┌──────────────────┐  ┌─────────────────────────┐    │                  │                      │
│  │  │ DirectorySource  │  │ ObsidianVaultSource     │    │                  │                      │
│  │  │                  │  │                         │    │                  │                      │
│  │  │ Glob patterns    │  │ ObsidianVaultReader     │    │                  │                      │
│  │  │ File loading     │  │ ObsidianMarkdownReader  │    │                  │                      │
│  │  │                  │  │                         │    │                  │                      │
│  │  │ get_transforms:  │  │ Frontmatter extraction  │    │                  │                      │
│  │  │  pre: []         │  │ Wikilink extraction     │    │                  │                      │
│  │  │  post: []        │  │ Backlink graph          │    │                  │                      │
│  │  │                  │  │                         │    │                  │                      │
│  │  │                  │  │ get_transforms:         │    │                  │                      │
│  │  │                  │  │  pre: [Frontmatter]     │    │                  │                      │
│  │  │                  │  │  post: [LinkResolution,  │    │                  │                      │
│  │  │                  │  │   ObsidianNormalize,    │    │                  │                      │
│  │  │                  │  │   MarkdownNodeParser]   │    │                  │                      │
│  │  └──────────────────┘  └─────────────────────────┘    │                  │                      │
│  └───────────────────────────┬────────────────────────────┘                  │                      │
│                              │ list[Document]                                │                      │
│                              ▼                                               │                      │
│  ┌───────────────────────────────────────────────────────────────────────────┤──────────────────┐   │
│  │                    PIPELINE ORCHESTRATION                                 │                  │   │
│  │                                                                          │                  │   │
│  │  ┌──────────────────────────┐    ┌────────────────────────────────────┐   │                  │   │
│  │  │ DatasetIngestPipeline    │    │ DatasetIngestPipelineV2           │◄──┘                  │   │
│  │  │ (V1)                     │    │ (V2 - current)                    │                      │   │
│  │  │                          │    │                                   │                      │   │
│  │  │ SentenceSplitter         │    │ ResilientSplitter (token-based)   │                      │   │
│  │  │ (char-based chunking)    │    │ EmbeddingPrefixTransform          │                      │   │
│  │  │                          │    │ Pipeline caching                  │                      │   │
│  │  └──────────┬───────────────┘    └──────────────────┬─────────────────┘                      │   │
│  │             │                                       │                                       │   │
│  │             └─────────────┬─────────────────────────┘                                       │   │
│  │                           │ wraps                                                           │   │
│  │                           ▼                                                                 │   │
│  │              ┌──────────────────────────────┐                                               │   │
│  │              │ LlamaIndex IngestionPipeline │                                               │   │
│  │              │                              │                                               │   │
│  │              │ Orchestrates transform chain │                                               │   │
│  │              │ Manages vector_store insert  │                                               │   │
│  │              └──────────────┬───────────────┘                                               │   │
│  │                             │                                                               │   │
│  └─────────────────────────────┼───────────────────────────────────────────────────────────────┘   │
│                                │ runs transforms in order                                         │
│                                ▼                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────┐   │
│  │                         TRANSFORM CHAIN                                                    │   │
│  │                                                                                            │   │
│  │  ┌─────────────────┐   ┌──────────────────┐   ┌─────────────────────────────┐             │   │
│  │  │ FrontmatterXform│   │PersistenceXform  │   │ LinkResolutionXform         │             │   │
│  │  │ (pre-persist)   │──▶│                  │──▶│ (post-persist, Obsidian)    │             │   │
│  │  │                 │   │ SHA256 hashing   │   │                             │             │   │
│  │  │ YAML parse      │   │ Doc create/update│   │ Wikilink -> doc_id mapping  │             │   │
│  │  │ DocumentMeta    │   │ Change detection │   │ Creates DocumentLink rows   │             │   │
│  │  │ Tag promotion   │   │ FTS upsert       │   │                             │             │   │
│  │  └─────────────────┘   │                  │   └──────────────┬──────────────┘             │   │
│  │                        │ PersistenceStats │                  │                             │   │
│  │                        └────────┬─────────┘                  │                             │   │
│  │                                 │                            ▼                             │   │
│  │                                 │              ┌──────────────────────────┐                │   │
│  │                                 │              │ ResilientSplitter (V2)   │                │   │
│  │                                 │              │ / SentenceSplitter (V1)  │                │   │
│  │                                 │              │                          │                │   │
│  │                                 │              │ Token-based chunking     │                │   │
│  │                                 │              │ Char-based fallback      │                │   │
│  │                                 │              └────────────┬─────────────┘                │   │
│  │                                 │                           │                              │   │
│  │                                 │                           ▼                              │   │
│  │                                 │              ┌──────────────────────────┐                │   │
│  │                                 │              │ChunkPersistenceXform    │                │   │
│  │                                 │              │                          │                │   │
│  │                                 │              │ UUID5(hash:seq) IDs      │                │   │
│  │                                 │              │ FTS chunk upsert         │                │   │
│  │                                 │              │ ChunkPersistenceStats    │                │   │
│  │                                 │              └────────────┬─────────────┘                │   │
│  │                                 │                           │                              │   │
│  │                                 │                           ▼                              │   │
│  │                                 │              ┌──────────────────────────┐                │   │
│  │                                 │              │EmbeddingPrefixXform (V2)│                │   │
│  │                                 │              │                          │                │   │
│  │                                 │              │ Nomic-style prefix       │                │   │
│  │                                 │              │ "search_document: ..."   │                │   │
│  │                                 │              └────────────┬─────────────┘                │   │
│  │                                 │                           │                              │   │
│  │                                 │                           ▼                              │   │
│  │                                 │              ┌──────────────────────────┐                │   │
│  │                                 │              │ EmbeddingModel           │                │   │
│  │                                 │              │                          │                │   │
│  │                                 │              │ MLXEmbedding (Apple Si)  │                │   │
│  │                                 │              │ / HuggingFace            │                │   │
│  │                                 │              │ ResilientEmbedding wrap  │                │   │
│  │                                 │              └────────────┬─────────────┘                │   │
│  │                                 │                           │                              │   │
│  └─────────────────────────────────┼───────────────────────────┼──────────────────────────────┘   │
│                                    │                           │                                  │
│           writes docs/links ───────┘    writes vectors ────────┘                                  │
│                                    │                           │                                  │
│                                    ▼                           ▼                                  │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────┐   │
│  │                           STORAGE LAYER                                                    │   │
│  │                                                                                            │   │
│  │  ┌───────────────────────────────────┐                                                    │   │
│  │  │        SERVICE LAYER              │                                                    │   │
│  │  │                                   │                                                    │   │
│  │  │  ┌─────────────────────────────┐  │                                                    │   │
│  │  │  │ DatasetService              │  │                                                    │   │
│  │  │  │                             │  │                                                    │   │
│  │  │  │ create_or_update()          │  │  Called by pipeline at start of ingest()            │   │
│  │  │  │ normalize_dataset_name()    │  │                                                    │   │
│  │  │  └─────────────┬───────────────┘  │                                                    │   │
│  │  └────────────────┼──────────────────┘                                                    │   │
│  │                   │ uses                                                                   │   │
│  │                   ▼                                                                        │   │
│  │  ┌───────────────────────────────────────────────────────────────────┐                     │   │
│  │  │              REPOSITORY LAYER                                     │                     │   │
│  │  │                                                                   │                     │   │
│  │  │  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐  │                     │   │
│  │  │  │DatasetRepository │ │DocumentRepository│ │DocLinkRepository │  │                     │   │
│  │  │  │                  │ │                  │ │                  │  │                     │   │
│  │  │  │create()          │ │create()          │ │create()          │  │                     │   │
│  │  │  │get_by_name()     │ │get_by_path()     │ │                  │  │                     │   │
│  │  │  │get_by_id()       │ │get_by_id()       │ │                  │  │                     │   │
│  │  │  └────────┬─────────┘ └────────┬─────────┘ └────────┬─────────┘  │                     │   │
│  │  └───────────┼────────────────────┼────────────────────┼────────────┘                     │   │
│  │              │                    │                    │                                   │   │
│  │              ▼                    ▼                    ▼                                   │   │
│  │  ┌────────────────────────────────────────────────────────────┐                            │   │
│  │  │             ORM MODELS (SQLAlchemy)                        │                            │   │
│  │  │                                                            │                            │   │
│  │  │  ┌──────────┐   ┌──────────────┐   ┌──────────────────┐   │                            │   │
│  │  │  │ Dataset  │──▶│  Document    │──▶│  DocumentLink    │   │                            │   │
│  │  │  │          │ 1 │              │ * │                  │   │                            │   │
│  │  │  │source_   │:N │path          │   │source_id         │   │                            │   │
│  │  │  │type      │   │body          │   │target_id         │   │                            │   │
│  │  │  │source_   │   │content_hash  │   │kind (WIKILINK)   │   │                            │   │
│  │  │  │path      │   │title         │   │                  │   │                            │   │
│  │  │  │          │   │metadata_json │   │                  │   │                            │   │
│  │  │  │          │   │active        │   │                  │   │                            │   │
│  │  │  └──────────┘   └──────────────┘   └──────────────────┘   │                            │   │
│  │  └────────────────────────────────────────────────────────────┘                            │   │
│  │              │                                                                             │   │
│  │              ▼                                                                             │   │
│  │  ┌──────────────────────────────────────────────┐    ┌──────────────────────────────────┐  │   │
│  │  │           SQLite Database                     │    │     Qdrant (Vector Store)        │  │   │
│  │  │                                               │    │                                  │  │   │
│  │  │  ┌─────────────────────────────────────────┐  │    │  ┌────────────────────────────┐  │  │   │
│  │  │  │ resources / datasets / documents tables  │  │    │  │ VectorStoreManager         │  │  │   │
│  │  │  │ document_links table                     │  │    │  │                            │  │  │   │
│  │  │  └─────────────────────────────────────────┘  │    │  │ get_vector_store()         │  │  │   │
│  │  │                                               │    │  │ delete_by_dataset()        │  │  │   │
│  │  │  ┌─────────────────────────────────────────┐  │    │  │ persist_vector_store()     │  │  │   │
│  │  │  │ documents_fts (FTS5)                    │  │    │  │                            │  │  │   │
│  │  │  │   managed by FTSManager                 │  │    │  │ Embeddings + metadata      │  │  │   │
│  │  │  │   path, body                            │  │    │  │ per chunk node             │  │  │   │
│  │  │  └─────────────────────────────────────────┘  │    │  └────────────────────────────┘  │  │   │
│  │  │                                               │    │                                  │  │   │
│  │  │  ┌─────────────────────────────────────────┐  │    └──────────────────────────────────┘  │   │
│  │  │  │ chunks_fts (FTS5)                       │  │                                          │   │
│  │  │  │   managed by FTSChunkManager            │  │    ┌──────────────────────────────────┐  │   │
│  │  │  │   node_id, text, source_doc_id          │  │    │     Pipeline Cache (filesystem)  │  │   │
│  │  │  └─────────────────────────────────────────┘  │    │                                  │  │   │
│  │  │                                               │    │  persist_pipeline()              │  │   │
│  │  └───────────────────────────────────────────────┘    │  load_pipeline()                 │  │   │
│  │                                                       │  persist_documents()             │  │   │
│  │                                                       │  clear_cache()                   │  │   │
│  │                                                       └──────────────────────────────────┘  │   │
│  └────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────┐   │
│  │                           OUTPUT                                                           │   │
│  │                                                                                            │   │
│  │  ┌─────────────────────────────────────────────────────┐                                   │   │
│  │  │ IngestResult                                        │                                   │   │
│  │  │                                                     │                                   │   │
│  │  │ .dataset_id          .documents_created             │                                   │   │
│  │  │ .dataset_name        .documents_updated             │                                   │   │
│  │  │ .documents_read      .documents_skipped             │                                   │   │
│  │  │ .chunks_created      .documents_failed              │                                   │   │
│  │  │ .vectors_inserted    .errors: list[str]             │                                   │   │
│  │  │ .started_at          .completed_at                  │                                   │   │
│  │  │                                                     │                                   │   │
│  │  │  Aggregated from: PersistenceStats,                 │                                   │   │
│  │  │    ChunkPersistenceStats, LinkResolutionStats       │                                   │   │
│  │  └─────────────────────────────────────────────────────┘                                   │   │
│  └────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘


LEGEND:
  ──▶  Data flow / dependency
  ─┬─  Inheritance / specialization
   │   Containment / composition
```

## Key Relationships

| From | To | Relationship |
|------|----|--------------|
| CLI / DatasetJob / Manual | DatasetIngestConfig | Creates config via factory dispatch |
| DatasetIngestConfig | BaseSource (Directory/Obsidian) | Source factory creates source from config |
| Pipeline (V1/V2) | LlamaIndex IngestionPipeline | Wraps and configures with transforms + vector_store |
| Pipeline.ingest() | DatasetService.create_or_update() | Ensures Dataset row exists before transforms run |
| PersistenceTransform | DocumentRepository + FTSManager | Persists documents and FTS index entries |
| ChunkPersistenceTransform | FTSChunkManager | Persists chunk FTS index entries |
| LinkResolutionTransform | DocumentLinkRepository | Creates wikilink relationship rows |
| EmbeddingModel | VectorStoreManager (Qdrant) | Vectors inserted via IngestionPipeline.vector_store |
| All transforms | Stats objects | Each transform tracks its own stats, aggregated into IngestResult |
| Settings | Pipeline, Embedding, Splitter, VectorStore | Global config consumed throughout |

## Session Context

All database writes flow through an **ambient session** (`use_session()` context manager)
set at the pipeline level, ensuring transactional consistency across transforms.
