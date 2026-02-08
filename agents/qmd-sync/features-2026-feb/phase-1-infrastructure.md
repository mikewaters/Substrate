# Phase 1: Infrastructure & Core Pipeline

## Overview
Phase 1 establishes the foundational infrastructure for RAG v2, including configuration management, caching, and resilient data processing. These components are prerequisites for all subsequent phases.

**Business Value:** Enables reliable, configurable RAG operations with reduced latency through caching and improved robustness through fallback mechanisms.

---

## Feature 1.1: RAG v2 Configuration System

### Business Value
Centralizes all v2 configuration in a single, environment-driven settings class. Enables operators to tune RAG behavior without code changes, supporting A/B testing and gradual rollout.

### Technical Specification

**Location:** `src/catalog/catalog/core/settings.py`

**Implementation:**
```python
class RAGv2Settings(BaseSettings):
    """RAG v2 configuration with environment variable support."""
    model_config = SettingsConfigDict(env_prefix="IDX_RAG_V2__")

    # Chunking
    chunk_size: int = 800
    chunk_overlap: int = 120
    chunk_fallback_enabled: bool = True
    chunk_chars_per_token: int = 4

    # Embedding
    embed_batch_size: int = 32
    embed_fallback_enabled: bool = True
    embed_prefix_query: str = "task: search result | query: "
    embed_prefix_doc: str = "title: {title} | text: "

    # Query expansion
    expansion_enabled: bool = True
    expansion_max_lex: int = 3
    expansion_max_vec: int = 3
    expansion_include_hyde: bool = True

    # RRF fusion
    rrf_k: int = 60
    rrf_original_weight: float = 2.0
    rrf_expansion_weight: float = 1.0
    rrf_rank1_bonus: float = 0.05
    rrf_rank23_bonus: float = 0.02

    # Reranking
    rerank_top_n: int = 10
    rerank_candidates: int = 40
    rerank_cache_enabled: bool = True

    # Caching
    cache_ttl_hours: int = 168

    # Retrieval
    vector_top_k: int = 20
    fts_top_k: int = 20
    fusion_top_k: int = 30

    # Snippets
    snippet_max_lines: int = 10
    snippet_context_lines: int = 2
```

**Integration:**
- Add `rag_v2: RAGv2Settings = RAGv2Settings()` to existing `Settings` class
- All v2 components read from `get_settings().rag_v2`

### Acceptance Criteria
- [ ] RAGv2Settings class with all config knobs
- [ ] Environment variable override support (IDX_RAG_V2__*)
- [ ] Default values match TypeScript QMD system
- [ ] Unit tests for settings loading and validation

### Dependencies
None (foundational)

### Estimated Effort
Small (1-2 hours)

---

## Feature 1.2: LLM Result Caching

### Business Value
Eliminates redundant LLM calls for repeated queries, reducing latency by 10-100x for cached results and cutting API costs. Essential for interactive search where users refine queries.

### Technical Specification

**Location:** `src/catalog/catalog/store/llm_cache.py`

**Schema:**
```sql
CREATE TABLE IF NOT EXISTS llm_cache_v2 (
    cache_key TEXT PRIMARY KEY,
    cache_type TEXT NOT NULL,  -- 'expansion' | 'rerank'
    result_json TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

**Implementation:**
```python
class LLMCacheEntry(Base):
    __tablename__ = "llm_cache_v2"
    cache_key = Column(String, primary_key=True)
    cache_type = Column(String, nullable=False)
    result_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class LLMCache:
    def __init__(self, session: Session, ttl_hours: int = 168): ...
    def _make_key(self, cache_type: str, *parts: str) -> str: ...
    def get_expansion(self, query: str, model: str) -> dict | None: ...
    def set_expansion(self, query: str, model: str, result: dict) -> None: ...
    def get_rerank(self, query: str, doc_hash: str, model: str) -> float | None: ...
    def set_rerank(self, query: str, doc_hash: str, model: str, score: float) -> None: ...
```

**Cache Key Strategy:**
- SHA-256 hash of `"{cache_type}:{query}:{model}:{extra}"`
- TTL-based expiration (default 1 week)

### Acceptance Criteria
- [ ] LLMCacheEntry SQLAlchemy model
- [ ] LLMCache class with get/set methods
- [ ] TTL-based expiration
- [ ] Cache key collision resistance (SHA-256)
- [ ] Unit tests for cache operations
- [ ] Integration test with database

### Dependencies
- catalog.store.database (existing)

### Estimated Effort
Small (2-3 hours)

---

## Feature 1.3: Resilient Embedding Infrastructure

### Business Value
Prevents ingestion failures due to transient embedding errors. When batch embedding fails, falls back to single-item processing, ensuring data is never lost due to temporary issues.

### Technical Specification

**Location:** `src/catalog/catalog/embedding/resilient.py`

**Implementation:**
```python
class ResilientEmbedding(BaseEmbedding):
    """Wrapper that falls back to single-item embedding on batch errors."""

    def __init__(self, embed_model: BaseEmbedding, batch_size: int = 32):
        self._embed_model = embed_model
        self._batch_size = batch_size

    def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        try:
            return self._embed_model._get_text_embeddings(texts)
        except Exception as e:
            logger.warning(f"Batch embedding failed: {e}, falling back to individual")
            return self._individual_embed(texts)

    def _individual_embed(self, texts: list[str]) -> list[list[float]]:
        embeddings = []
        for text in texts:
            try:
                embeddings.append(self._embed_model._get_text_embedding(text))
            except Exception as e:
                logger.error(f"Failed to embed text: {e}")
                raise
        return embeddings
```

**Integration:**
- Update `get_embed_model(resilient: bool = False)` factory function
- V2 ingestion uses `get_embed_model(resilient=True)`

### Acceptance Criteria
- [ ] ResilientEmbedding wrapper class
- [ ] Batch-to-single fallback logic
- [ ] Logging of fallback events
- [ ] Updated factory function
- [ ] Unit tests with mocked failures

### Dependencies
- catalog.embedding (existing)
- Feature 1.1 (settings)

### Estimated Effort
Small (2-3 hours)

---

## Feature 1.4: Resilient Text Chunking

### Business Value
Ensures document processing succeeds even when tokenizer-based chunking fails. Falls back to character-based chunking, maintaining ingestion reliability across diverse document types.

### Technical Specification

**Location:** `src/catalog/catalog/transform/splitter.py`

**Implementation:**
```python
class ResilientSplitter(TransformComponent):
    """Token-based splitter with char-based fallback."""

    def __init__(
        self,
        chunk_size_tokens: int = 800,
        chunk_overlap_tokens: int = 120,
        chars_per_token: int = 4,
        fallback_enabled: bool = True,
    ):
        self.token_splitter = TokenTextSplitter(
            chunk_size=chunk_size_tokens,
            chunk_overlap=chunk_overlap_tokens,
        )
        self.char_splitter = SentenceSplitter(
            chunk_size=chunk_size_tokens * chars_per_token,
            chunk_overlap=chunk_overlap_tokens * chars_per_token,
        )
        self.fallback_enabled = fallback_enabled

    def __call__(self, nodes: list[BaseNode], **kwargs) -> list[BaseNode]:
        try:
            return self.token_splitter(nodes, **kwargs)
        except Exception as e:
            if not self.fallback_enabled:
                raise
            logger.warning(f"Token splitting failed: {e}, falling back to char-based")
            return self.char_splitter(nodes, **kwargs)
```

### Acceptance Criteria
- [ ] ResilientSplitter TransformComponent
- [ ] Token-to-char fallback logic
- [ ] Configurable fallback enable/disable
- [ ] Logging of fallback events
- [ ] Unit tests with various document types

### Dependencies
- llama_index.core.node_parser
- Feature 1.1 (settings)

### Estimated Effort
Small (2-3 hours)

---

## Feature 1.5: Embedding Prefix Transform

### Business Value
Improves embedding quality by adding semantic prefixes that help the embedding model understand document context. Matches TypeScript QMD's Nomic-style formatting for retrieval parity.

### Technical Specification

**Location:** `src/catalog/catalog/transform/embedding.py`

**Implementation:**
```python
class EmbeddingPrefixTransform(TransformComponent):
    """Apply prefix formatting to node text before embedding."""

    def __init__(self, prefix_template: str = "title: {title} | text: "):
        self.prefix_template = prefix_template

    def __call__(self, nodes: list[BaseNode], **kwargs) -> list[BaseNode]:
        for node in nodes:
            title = node.metadata.get("title", "")
            prefix = self.prefix_template.format(title=title)
            node.metadata["original_text"] = node.text
            node.text = prefix + node.text
        return nodes
```

### Acceptance Criteria
- [ ] EmbeddingPrefixTransform class
- [ ] Configurable prefix template
- [ ] Original text preservation in metadata
- [ ] Unit tests verifying prefix application

### Dependencies
- llama_index.core.schema
- Feature 1.1 (settings)

### Estimated Effort
Small (1-2 hours)

---

## Feature 1.6: V2 Ingestion Pipeline

### Business Value
Combines all Phase 1 components into a production-ready ingestion pipeline. Provides the foundation for v2 search by ensuring documents are properly chunked, formatted, and embedded.

### Technical Specification

**Location:** `src/catalog/catalog/ingest/pipelines_v2.py`

**Implementation:**
```python
class DatasetIngestPipelineV2:
    """V2 ingestion with resilient chunking and embedding prefixes."""

    def __init__(self, session):
        self.session = session
        self._settings = get_settings().rag_v2

    def build_pipeline(self, dataset_id: int, dataset_name: str) -> IngestionPipeline:
        docstore = load_pipeline(dataset_name) or SimpleDocumentStore()
        embed_model = get_embed_model(resilient=True)

        return IngestionPipeline(
            transformations=[
                PersistenceTransform(dataset_id=dataset_id, session=self.session),
                ResilientSplitter(
                    chunk_size_tokens=self._settings.chunk_size,
                    chunk_overlap_tokens=self._settings.chunk_overlap,
                    chars_per_token=self._settings.chunk_chars_per_token,
                    fallback_enabled=self._settings.chunk_fallback_enabled,
                ),
                ChunkPersistenceTransform(dataset_name=dataset_name, session=self.session),
                EmbeddingPrefixTransform(prefix_template=self._settings.embed_prefix_doc),
            ],
            docstore=docstore,
            docstore_strategy=DocstoreStrategy.UPSERTS_AND_DELETE,
        )

    def persist_state(self, dataset_name: str, pipeline: IngestionPipeline) -> None:
        persist_pipeline(dataset_name, pipeline)
```

### Acceptance Criteria
- [ ] DatasetIngestPipelineV2 class
- [ ] Integration with all Phase 1 transforms
- [ ] Docstore-based deduplication
- [ ] Pipeline state persistence
- [ ] Integration test with sample documents

### Dependencies
- Feature 1.1 (settings)
- Feature 1.3 (resilient embedding)
- Feature 1.4 (resilient splitter)
- Feature 1.5 (embedding prefix)
- catalog.ingest.cache (existing)
- catalog.transform.llama (existing)

### Estimated Effort
Medium (3-4 hours)

---

## Phase 1 Test Plan

**Unit Tests:** `tests/rag_v2/test_transforms.py`
- ResilientSplitter fallback behavior
- EmbeddingPrefixTransform prefix application
- ResilientEmbedding batch fallback

**Unit Tests:** `tests/rag_v2/test_cache.py`
- LLMCache get/set operations
- TTL expiration
- Cache key generation

**Integration Tests:** `tests/rag_v2/test_ingestion_v2.py`
- Full pipeline execution with sample documents
- Deduplication behavior
- Error recovery scenarios

---

## Phase 1 Deliverables

| Deliverable | Location |
|-------------|----------|
| RAGv2Settings | `catalog/core/settings.py` |
| LLMCache | `catalog/store/llm_cache.py` |
| ResilientEmbedding | `catalog/embedding/resilient.py` |
| ResilientSplitter | `catalog/transform/splitter.py` |
| EmbeddingPrefixTransform | `catalog/transform/embedding.py` |
| DatasetIngestPipelineV2 | `catalog/ingest/pipelines_v2.py` |
| Unit tests | `tests/rag_v2/test_transforms.py`, `tests/rag_v2/test_cache.py` |
| Integration tests | `tests/rag_v2/test_ingestion_v2.py` |
