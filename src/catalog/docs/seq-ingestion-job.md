# Sequence Diagram: Job-Based Ingestion (V2 Pipeline)

Entry point: `DatasetJob.from_yaml(path)` via YAML configuration file.

```
 Caller          DatasetJob       SourceFactory     PipelineV2        Source          DatasetService   VectorStoreMgr   Session/DB
   |                 |                 |                |                |                 |                |              |
   |  from_yaml(p)   |                 |                |                |                 |                |              |
   |────────────────>|                 |                |                |                 |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |  Hydra compose() + OmegaConf     |                |                 |                |              |
   |                 |  parse YAML into raw dict        |                |                 |                |              |
   |                 |  model_validate(raw)             |                |                 |                |              |
   |                 |  -> DatasetJob(                  |                |                 |                |              |
   |                 |      source: SourceConfig,       |                |                 |                |              |
   |                 |      embedding: EmbeddingConfig,  |                |                 |                |              |
   |                 |      pipeline: PipelineConfig)    |                |                 |                |              |
   |     <job>       |                 |                |                |                 |                |              |
   |<────────────────|                 |                |                |                 |                |              |
   |                 |                 |                |                |                 |                |              |
   | to_ingest_config()                |                |                |                 |                |              |
   |────────────────>|                 |                |                |                 |                |              |
   |                 | create_ingest_config(source_cfg) |                |                 |                |              |
   |                 |────────────────>|                |                |                 |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 | import catalog.ingest.directory  |                 |                |              |
   |                 |                 | import catalog.integrations      |                 |                |              |
   |                 |                 | lookup _ingest_config_factories[source_cfg.type]   |                |              |
   |                 |                 | call factory(source_cfg)         |                 |                |              |
   |                 |                 |  e.g. create_obsidian_ingest_config():             |                |              |
   |                 |                 |    _import_class(ontology_spec_path)                |                |              |
   |                 |                 |    -> IngestObsidianConfig(                        |                |              |
   |                 |                 |         source_path, dataset_name,                 |                |              |
   |                 |                 |         ontology_spec, force, catalog_name)          |                |              |
   |                 |   <config>      |                |                |                 |                |              |
   |                 |<────────────────|                |                |                 |                |              |
   |    <config>     |                 |                |                |                 |                |              |
   |<────────────────|                 |                |                |                 |                |              |
   |                 |                 |                |                |                 |                |              |
   | create_embed_model()              |                |                |                 |                |              |
   |────────────────>|                 |                |                |                 |                |              |
   |                 | if embedding config:             |                |                 |                |              |
   |                 |   MLXEmbedding(model, batch_size)|                |                 |                |              |
   |                 | else:                            |                |                 |                |              |
   |                 |   get_embed_model() from settings |                |                 |                |              |
   |  <embed_model>  |                 |                |                |                 |                |              |
   |<────────────────|                 |                |                |                 |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                |                |                 |                |              |
   |  DatasetIngestPipelineV2(         |                |                |                 |                |              |
   |    ingest_config=config,          |                |                |                 |                |              |
   |    embed_model=embed_model,       |                |                |                 |                |              |
   |    resilient_embedding=True)      |                |                |                 |                |              |
   |──────────────────────────────────────────────────>|                |                 |                |              |
   |                 |                 |                |                |                 |                |              |
   |  pipeline.ingest()               |                |                |                 |                |              |
   |──────────────────────────────────────────────────>|                |                 |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                |  ============ SESSION BOUNDARY ============      |              |
   |                 |                 |                |  get_session()                  |                |              |
   |                 |                 |                |──────────────────────────────────────────────────────────────>|
   |                 |                 |                |  use_session(session) [context var]              |              |
   |                 |                 |                |──────────────────────────────────────────────────────────────>|
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | ---- 1. ENSURE DATASET EXISTS ----               |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | DatasetService.create_or_update(                 |              |
   |                 |                 |                |   session, name, source_type,    |                |              |
   |                 |                 |                |   source_path, catalog_name)     |                |              |
   |                 |                 |                |────────────────────────────────>|                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                |                |  normalize_dataset_name(name)    |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                |                |  DatasetRepository(session)      |              |
   |                 |                 |                |                |  .get_by_name(normalized)        |              |
   |                 |                 |                |                |                 |───────────────────────────>|
   |                 |                 |                |                |                 |  SELECT        |              |
   |                 |                 |                |                |                 |<──────────────────────────|
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                |                |  if not exists:  |                |              |
   |                 |                 |                |                |    repo.create(name, uri,        |              |
   |                 |                 |                |                |      source_type, source_path)   |              |
   |                 |                 |                |                |                 |───────────────────────────>|
   |                 |                 |                |                |                 |  INSERT Dataset|              |
   |                 |                 |                |                |                 |<──────────────────────────|
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                |                |  if catalog_name:                |              |
   |                 |                 |                |                |    CatalogRepo.get_or_create()   |              |
   |                 |                 |                |                |    CatalogRepo.add_entry()       |              |
   |                 |                 |                |                |                 |───────────────────────────>|
   |                 |                 |                |                |                 |  INSERT Catalog|              |
   |                 |                 |                |                |                 |  + CatalogEntry|              |
   |                 |                 |                |                |                 |<──────────────────────────|
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                |  <DatasetInfo> |                 |                |              |
   |                 |                 |                |<────────────────────────────────|                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | ---- 2. FORCE MODE (if config.force) ----        |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | VectorStoreManager()             |                |              |
   |                 |                 |                |──────────────────────────────────────────────────>|              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | vm.delete_by_dataset(name)       |                |              |
   |                 |                 |                |──────────────────────────────────────────────────>|              |
   |                 |                 |                |                |                 |    Qdrant      |              |
   |                 |                 |                |                |                 |    filter      |              |
   |                 |                 |                |                |                 |    delete      |              |
   |                 |                 |                |<─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─|              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | clear_cache(dataset_name)        |                |              |
   |                 |                 |                |  (removes filesystem cache)      |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | ---- 3. LOAD SOURCE ----         |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | create_source(config)            |                |              |
   |                 |                 |                |  -> singledispatch on config type |                |              |
   |                 |                 |                |  -> e.g. ObsidianVaultSource(path, ontology_spec)  |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | source.get_transforms(dataset_id)                |              |
   |                 |                 |                |───────────────>|                 |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                |                | returns:        |                |              |
   |                 |                 |                |                |  pre:  [FrontmatterTransform]    |              |
   |                 |                 |                |                |  post: [LinkResolutionTransform, |              |
   |                 |                 |                |                |         ObsidianMarkdownNormalize,               |
   |                 |                 |                |                |         MarkdownNodeParser]      |              |
   |                 |                 |                |  <(pre, post)> |                 |                |              |
   |                 |                 |                |<───────────────|                 |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | ---- 4. BUILD PIPELINE ----      |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | build_pipeline(dataset_id, dataset_name,          |              |
   |                 |                 |                |   vector_manager, source_transforms, force)       |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                |  PersistenceTransform(dataset_id, force)          |              |
   |                 |                 |                |  ResilientSplitter(chunk_size, chunk_overlap,     |              |
   |                 |                 |                |    chars_per_token, fallback_enabled)             |              |
   |                 |                 |                |  ChunkPersistenceTransform(dataset_name)          |              |
   |                 |                 |                |  EmbeddingPrefixTransform(prefix_template)        |              |
   |                 |                 |                |  embed_model (from _get_embed_model())            |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                |  transformations = [              |                |              |
   |                 |                 |                |    *pre_transforms,   <-- source-specific         |              |
   |                 |                 |                |    persist,                       |                |              |
   |                 |                 |                |    *post_transforms,  <-- source-specific         |              |
   |                 |                 |                |    splitter,                      |                |              |
   |                 |                 |                |    chunk_persist,                 |                |              |
   |                 |                 |                |    prefix_transform,              |                |              |
   |                 |                 |                |    embed_model,                   |                |              |
   |                 |                 |                |  ]                                |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                |  vm.get_vector_store()            |                |              |
   |                 |                 |                |──────────────────────────────────────────────────>|              |
   |                 |                 |                |                |                 |   _ensure_     |              |
   |                 |                 |                |                |                 |   collection() |              |
   |                 |                 |                |                |                 |   QdrantVector |              |
   |                 |                 |                |                |                 |   Store()      |              |
   |                 |                 |                |  <vector_store>|                 |                |              |
   |                 |                 |                |<─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─|              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                |  IngestionPipeline(              |                |              |
   |                 |                 |                |    transformations,              |                |              |
   |                 |                 |                |    docstore=SimpleDocumentStore,  |                |              |
   |                 |                 |                |    docstore_strategy=UPSERTS_AND_DELETE,          |              |
   |                 |                 |                |    vector_store=vector_store)     |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                |  load_pipeline(dataset_name, pipeline)            |              |
   |                 |                 |                |    (restore cached docstore state from filesystem)|              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | ---- 5. LOAD DOCUMENTS ----     |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | source.documents (cached_property)                |              |
   |                 |                 |                |───────────────>|                 |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                |                | ObsidianVaultReader.load_data()  |              |
   |                 |                 |                |                |   glob *.md files               |              |
   |                 |                 |                |                |   for each file:                |              |
   |                 |                 |                |                |     ObsidianMarkdownReader       |              |
   |                 |                 |                |                |       .load_data(file)           |              |
   |                 |                 |                |                |     parse_frontmatter()          |              |
   |                 |                 |                |                |     get_file_metadata()          |              |
   |                 |                 |                |                |   extract_wikilinks()            |              |
   |                 |                 |                |                |   build backlinks graph          |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | <list[Document]>                 |                |              |
   |                 |                 |                |<───────────────|                 |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | ==== 6. RUN PIPELINE ====        |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | pipeline.run(documents)          |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | For each document, transforms run in order:       |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | ---- 6a. FrontmatterTransform (pre-persist) ----  |              |
   |                 |                 |                |   parse YAML frontmatter from metadata            |              |
   |                 |                 |                |   derive title (frontmatter -> aliases -> name)   |              |
   |                 |                 |                |   derive description                              |              |
   |                 |                 |                |   promote tags/categories to metadata              |              |
   |                 |                 |                |   write _ontology_meta to node.metadata            |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | ---- 6b. PersistenceTransform ----                |              |
   |                 |                 |                |   reset stats                    |                |              |
   |                 |                 |                |   current_session() [from context var]            |              |
   |                 |                 |                |   DocumentRepository(session)    |                |              |
   |                 |                 |                |   FTSManager(session)            |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                |   doc_repo.list_paths_by_parent(dataset_id)       |              |
   |                 |                 |                |──────────────────────────────────────────────────────────────>|
   |                 |                 |                |   <existing paths>               |                |              |
   |                 |                 |                |<─────────────────────────────────────────────────────────────|
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                |   pre-fetch existing docs by path                 |              |
   |                 |                 |                |──────────────────────────────────────────────────────────────>|
   |                 |                 |                |   <existing_docs dict>           |                |              |
   |                 |                 |                |<─────────────────────────────────────────────────────────────|
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                |   for each node:                 |                |              |
   |                 |                 |                |     path = metadata["relative_path"]              |              |
   |                 |                 |                |     content_hash = SHA256(body)   |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                |     if exists && hash unchanged && !force:        |              |
   |                 |                 |                |       stats.skipped++             |                |              |
   |                 |                 |                |       node.metadata["doc_id"] = existing.id       |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                |     if exists && (hash changed || force):         |              |
   |                 |                 |                |       update existing.body, .content_hash, etc    |              |
   |                 |                 |                |       session.flush()             |                |              |
   |                 |                 |                |──────────────────────────────────────────────────────────────>|
   |                 |                 |                |                |                 |      UPDATE    |              |
   |                 |                 |                |<─────────────────────────────────────────────────────────────|
   |                 |                 |                |       FTSManager.upsert(id, path, body)           |              |
   |                 |                 |                |──────────────────────────────────────────────────────────────>|
   |                 |                 |                |                |                 |   documents_fts|              |
   |                 |                 |                |<─────────────────────────────────────────────────────────────|
   |                 |                 |                |       stats.updated++             |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                |     if not exists:                |                |              |
   |                 |                 |                |       doc_repo.create(parent_id, path, uri,       |              |
   |                 |                 |                |         content_hash, body, title, ...)            |              |
   |                 |                 |                |──────────────────────────────────────────────────────────────>|
   |                 |                 |                |                |                 |      INSERT    |              |
   |                 |                 |                |<─────────────────────────────────────────────────────────────|
   |                 |                 |                |       FTSManager.upsert(id, path, body)           |              |
   |                 |                 |                |──────────────────────────────────────────────────────────────>|
   |                 |                 |                |                |                 |   documents_fts|              |
   |                 |                 |                |<─────────────────────────────────────────────────────────────|
   |                 |                 |                |       stats.created++             |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                |   session.flush()                 |                |              |
   |                 |                 |                |   returns nodes with doc_id in metadata           |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | ---- 6c. LinkResolutionTransform (post-persist) --|              |
   |                 |                 |                |   for each node:                 |                |              |
   |                 |                 |                |     extract wikilinks from metadata               |              |
   |                 |                 |                |     for each wikilink:            |                |              |
   |                 |                 |                |       lookup target doc by filename stem           |              |
   |                 |                 |                |──────────────────────────────────────────────────────────────>|
   |                 |                 |                |       if found:                   |                |              |
   |                 |                 |                |         DocumentLinkRepo.create(  |                |              |
   |                 |                 |                |           source_id, target_id, WIKILINK)         |              |
   |                 |                 |                |──────────────────────────────────────────────────────────────>|
   |                 |                 |                |                |                 |   INSERT link  |              |
   |                 |                 |                |<─────────────────────────────────────────────────────────────|
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | ---- 6d. ObsidianMarkdownNormalize (post-persist) |              |
   |                 |                 |                |   strip/normalize Obsidian markdown syntax        |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | ---- 6e. MarkdownNodeParser (post-persist) ----   |              |
   |                 |                 |                |   parse markdown structure into sub-nodes         |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | ---- 6f. ResilientSplitter ----  |                |              |
   |                 |                 |                |   attempt TokenTextSplitter(     |                |              |
   |                 |                 |                |     chunk_size_tokens, chunk_overlap_tokens)      |              |
   |                 |                 |                |   if tokenizer fails && fallback_enabled:         |              |
   |                 |                 |                |     SentenceSplitter(            |                |              |
   |                 |                 |                |       chunk_size=tokens*chars_per_token,          |              |
   |                 |                 |                |       chunk_overlap=overlap*chars_per_token)      |              |
   |                 |                 |                |   returns chunk nodes             |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | ---- 6g. ChunkPersistenceTransform ----           |              |
   |                 |                 |                |   FTSChunkManager() [ambient session]             |              |
   |                 |                 |                |   group nodes by source document  |                |              |
   |                 |                 |                |   for each chunk:                 |                |              |
   |                 |                 |                |     node_id = UUID5(content_hash:chunk_seq)       |              |
   |                 |                 |                |     metadata["source_doc_id"] = "{dataset}:{path}"|              |
   |                 |                 |                |     metadata["chunk_seq"] = seq   |                |              |
   |                 |                 |                |     FTSChunkManager.upsert(       |                |              |
   |                 |                 |                |       node_id, text, source_doc_id)               |              |
   |                 |                 |                |──────────────────────────────────────────────────────────────>|
   |                 |                 |                |                |                 |   chunks_fts   |              |
   |                 |                 |                |<─────────────────────────────────────────────────────────────|
   |                 |                 |                |     stats.created++               |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | ---- 6h. EmbeddingPrefixTransform ----            |              |
   |                 |                 |                |   for each chunk node:            |                |              |
   |                 |                 |                |     title = metadata.get("title") |                |              |
   |                 |                 |                |     prefix = template.format(title=title)         |              |
   |                 |                 |                |     metadata["original_text"] = node.text         |              |
   |                 |                 |                |     node.text = prefix + node.text                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | ---- 6i. EmbeddingModel ----     |                |              |
   |                 |                 |                |   MLXEmbedding / ResilientEmbedding               |              |
   |                 |                 |                |   batch embed all chunk texts     |                |              |
   |                 |                 |                |   -> node.embedding = [float, ...]                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | ---- 6j. IngestionPipeline inserts to Qdrant ---- |              |
   |                 |                 |                |   vector_store.add(nodes_with_embeddings)         |              |
   |                 |                 |                |──────────────────────────────────────────────────>|              |
   |                 |                 |                |                |                 |    Qdrant      |              |
   |                 |                 |                |                |                 |    upsert      |              |
   |                 |                 |                |<─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─|              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                |  <nodes>       |                 |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | ---- 7. COLLECT STATS & PERSIST ----              |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | walk pipeline.transformations:   |                |              |
   |                 |                 |                |   PersistenceTransform.stats     |                |              |
   |                 |                 |                |     -> result.documents_created/updated/skipped   |              |
   |                 |                 |                |   ChunkPersistenceTransform.stats                 |              |
   |                 |                 |                |     -> result.chunks_created      |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | result.documents_read = len(source.documents)     |              |
   |                 |                 |                | result.vectors_inserted = len(nodes)              |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | vm.persist_vector_store()        |                |              |
   |                 |                 |                |──────────────────────────────────────────────────>|              |
   |                 |                 |                |   (no-op: Qdrant auto-persists)   |                |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                | persist_pipeline(dataset_name, pipeline)          |              |
   |                 |                 |                |   (save docstore state to filesystem cache)       |              |
   |                 |                 |                |                |                 |                |              |
   |                 |                 |                |  ============ END SESSION ============            |              |
   |                 |                 |                |  session auto-commits on context exit             |              |
   |                 |                 |                |                |                 |                |              |
   |  <IngestResult> |                 |                |                |                 |                |              |
   |<──────────────────────────────────────────────────|                |                 |                |              |
   |                 |                 |                |                |                 |                |              |
   |  IngestResult:                    |                |                |                 |                |              |
   |    dataset_id, dataset_name       |                |                |                 |                |              |
   |    documents_read                 |                |                |                 |                |              |
   |    documents_created/updated/skipped/failed        |                |                 |                |              |
   |    chunks_created                 |                |                |                 |                |              |
   |    vectors_inserted               |                |                |                 |                |              |
   |    errors[]                       |                |                |                 |                |              |
   |    started_at, completed_at       |                |                |                 |                |              |
   |                 |                 |                |                |                 |                |              |
```

## Notes

- **Session boundary**: The entire `ingest()` method runs within a single SQLAlchemy session context. All transforms use the ambient session via `current_session()` context var.
- **Transform ordering**: The LlamaIndex `IngestionPipeline` runs transforms sequentially in list order. Each transform receives all nodes, processes them, and passes them to the next.
- **Change detection**: `PersistenceTransform` pre-fetches existing documents and compares SHA-256 content hashes. Unchanged docs (when `force=False`) are skipped but still passed downstream for vector embedding.
- **Qdrant auto-persist**: `persist_vector_store()` is a no-op since Qdrant in local mode auto-persists. The call is kept for API compatibility.
- **Pipeline cache**: `load_pipeline()` / `persist_pipeline()` save and restore the LlamaIndex docstore state to disk for incremental ingestion across runs.
- **Obsidian-specific path**: When `source.type == "obsidian"`, the source provides extra pre/post transforms (FrontmatterTransform, LinkResolution, etc.). For `directory` sources, both transform lists are empty.
