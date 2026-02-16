# LlamaIndex Hybrid RAG v2 (Additive) Integration Design

## Summary
This document proposes an additive LlamaIndex-based RAG + hybrid retrieval path for the catalog codebase. The design keeps existing search and ingestion flows intact while introducing an opt-in v2 path that reuses current storage, embedding, and retrieval seams.

## Existing Seams & Contracts

### A) Storage & Vector I/O
- Vector persistence and retrieval is managed via `catalog.store.vector.VectorStoreManager`, which creates/loads a `VectorStoreIndex` and persists to the configured `SUBSTRATE_VECTOR_STORE_PATH` directory.
- Vector queries are executed either directly against `SimpleVectorStore` (`catalog.search.vector.VectorSearch`) or via `VectorStoreIndex.as_retriever()` in the hybrid path (`catalog.search.hybrid.HybridSearch`).
- Dataset scoping relies on `source_doc_id = "{dataset}:{path}"` in node metadata. The hybrid retriever uses LlamaIndex `MetadataFilters` with `FilterOperator.CONTAINS` on `source_doc_id`, while direct vector search filters results in Python.

### B) Embeddings Access
- Embedding model creation is centralized in `catalog.embedding.get_embed_model()` and `catalog.store.vector.VectorStoreManager._get_embed_model()`.
- MLX and HuggingFace embeddings are supported, with batch size defined by `SUBSTRATE_EMBEDDING__BATCH_SIZE`.
- No explicit embedding cache or retry middleware exists; models are lazily initialized.

### C) Document/Node Persistence
- Documents are persisted via `catalog.transform.llama.PersistenceTransform`, which writes to SQLite and updates `documents_fts`.
- Chunk nodes are persisted via `catalog.transform.llama.ChunkPersistenceTransform`, which sets stable node IDs (`{content_hash}:{chunk_seq}`) and writes to `chunks_fts` with `source_doc_id` metadata.

### D) Retrieval Pipeline Assembly
- `catalog.search.fts_chunk.FTSChunkRetriever` implements a LlamaIndex `BaseRetriever` over the `chunks_fts` FTS5 index.
- `catalog.search.hybrid.HybridSearch` assembles a `QueryFusionRetriever` (RRF mode) over FTS and vector retrievers.
- `catalog.search.rerank.Reranker` wraps LlamaIndex `LLMRerank` postprocessing.

### E) External Function API Layer
- The public `catalog.search.search()` function returns `SearchResults` and sets up sessions.
- `catalog.search.service.SearchService` is the primary orchestrator and uses `SearchCriteria` and `SearchResult` Pydantic models.

### F) Ingestion Pipeline Assembly
- `catalog.ingest.pipelines.DatasetIngestPipeline` orchestrates ingestion using a LlamaIndex `IngestionPipeline`, with persistence and chunking transforms (`PersistenceTransform`, `ChunkPersistenceTransform`, and `SentenceSplitter`).
- Dataset-level metadata normalization and source-specific transforms are attached via `catalog.ingest.sources.create_source()` and its transform hooks.
- FTS and chunk FTS tables are ensured during ingestion through `catalog.store.fts.create_fts_table()` and `catalog.store.fts_chunk.create_chunks_fts_table()`.

---

## Module Responsibility Summary

Before detailing the v2 design, here's where new abstractions belong based on the catalog's architecture:

| Module | Responsibility | New v2 Additions |
|--------|----------------|------------------|
| `catalog.core.settings` | Configuration management | All `SUBSTRATE_RAG_V2__*` config knobs |
| `catalog.embedding` | Embedding model abstraction | `ResilientEmbedding` (batch fallback) |
| `catalog.transform` | LlamaIndex TransformComponents | `EmbeddingPrefixTransform`, `ResilientSplitter` |
| `catalog.store` | Persistence layer | `LLMCache` (new submodule for LLM result caching) |
| `catalog.search` | Search orchestration & retrieval | `SearchServiceV2`, postprocessors, query expansion, formatting |
| `catalog.llm` | LLM providers & reranking | `CachedReranker`, expansion prompts |
| `catalog.ingest` | Ingestion pipelines | `DatasetIngestPipelineV2` |
| `catalog.api.mcp` | MCP server & tools (new) | `MCPToolProvider`, MCP server |

---

## Parallel Path Strategy

### Exposure Strategy
The v2 path is exposed through:
- `catalog.search.search_v2()` convenience function (new)
- `catalog.search.service.SearchServiceV2` orchestrator (new)

Default behavior stays unchanged; v2 is opt-in.

### Compatibility & Migration
- Clients can adopt v2 without changing existing `catalog.search` flows.
- Provide a side-by-side comparison mode in v2 (`compare_with_v1=True`) for internal evaluation.
- Rollback is achieved by reverting to `catalog.search.search()`.

---

## Design-to-Repo Mapping Table

| Capability | LlamaIndex abstraction | Existing seam | Proposed location | Config knobs |
| --- | --- | --- | --- | --- |
| Chunking with fallback | `TokenTextSplitter` / `SentenceSplitter` | `catalog.ingest.pipelines` | `catalog.transform.splitter` | `SUBSTRATE_RAG_V2__CHUNK_*` |
| Embedding prefixes | `TransformComponent` | `catalog.transform.llama` | `catalog.transform.embedding` | `SUBSTRATE_RAG_V2__EMBED_PREFIX_*` |
| Resilient embedding | `TransformComponent` | `catalog.embedding` | `catalog.embedding.resilient` | `SUBSTRATE_RAG_V2__EMBED_*` |
| Ingestion pipeline v2 | `IngestionPipeline` | `catalog.ingest.pipelines` | `catalog.ingest.pipelines` | `SUBSTRATE_RAG_V2__INGEST_*` |
| Vector retrieval | `VectorIndexRetriever` | `catalog.search.vector` | reuse existing | `SUBSTRATE_RAG_V2__VECTOR_TOP_K` |
| Lexical retrieval | `BaseRetriever` | `catalog.search.fts_chunk` | reuse existing | `SUBSTRATE_RAG_V2__FTS_TOP_K` |
| Hybrid fusion v2 | `QueryFusionRetriever` | `catalog.search.hybrid` | `catalog.search.hybrid` | `SUBSTRATE_RAG_V2__FUSION_*` |
| Query expansion | `QueryTransform` | None | `catalog.search.query_expansion` | `SUBSTRATE_RAG_V2__EXPANSION_*` |
| RRF postprocessing | `BaseNodePostprocessor` | None | `catalog.search.postprocessors` | `SUBSTRATE_RAG_V2__RRF_*` |
| Reranking with cache | `LLMRerank` wrapper | `catalog.llm.reranker` | `catalog.llm.reranker` | `SUBSTRATE_RAG_V2__RERANK_*` |
| LLM caching | Custom adapter | None | `catalog.store.llm_cache` | `SUBSTRATE_RAG_V2__CACHE_*` |
| Snippet formatting | Pure utility | `catalog.search.models` | `catalog.search.formatting` | `SUBSTRATE_RAG_V2__SNIPPET_*` |
| MCP tools | `FunctionTool` | None | `catalog.api.mcp` | tool schemas |
| Evaluation harness | Pytest | existing tests | `tests/rag_v2/` | thresholds |

---

## New Abstractions by Module

### `catalog.core.settings` — Configuration

Add v2 configuration to the existing `Settings` class:

```python
# In catalog/core/settings.py

class RAGv2Settings(BaseSettings):
    """RAG v2 configuration."""
    model_config = SettingsConfigDict(env_prefix="SUBSTRATE_RAG_V2__")

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
    cache_ttl_hours: int = 168  # one week

    # Retrieval
    vector_top_k: int = 20
    fts_top_k: int = 20
    fusion_top_k: int = 30

    # Snippets
    snippet_max_lines: int = 10
    snippet_context_lines: int = 2


class Settings(BaseSettings):
    # ... existing settings ...
    rag_v2: RAGv2Settings = RAGv2Settings()
```

---

### `catalog.embedding` — Resilient Embedding

**New file:** `catalog/embedding/resilient.py`

```python
"""Resilient embedding with batch fallback."""
from llama_index.core.base.embeddings.base import BaseEmbedding
from loguru import logger


class ResilientEmbedding(BaseEmbedding):
    """Wrapper that falls back to single-item embedding on batch errors."""

    def __init__(self, embed_model: BaseEmbedding, batch_size: int = 32):
        self._embed_model = embed_model
        self._batch_size = batch_size

    def _get_text_embedding(self, text: str) -> list[float]:
        return self._embed_model._get_text_embedding(text)

    def _get_query_embedding(self, query: str) -> list[float]:
        return self._embed_model._get_query_embedding(query)

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

**Update:** `catalog/embedding/__init__.py`

```python
from catalog.embedding.resilient import ResilientEmbedding

def get_embed_model(resilient: bool = False) -> BaseEmbedding:
    """Get configured embedding model, optionally with resilient wrapper."""
    model = _get_base_embed_model()
    if resilient:
        settings = get_settings().rag_v2
        return ResilientEmbedding(model, batch_size=settings.embed_batch_size)
    return model
```

---

### `catalog.transform` — Embedding Prefix & Resilient Splitter

**New file:** `catalog/transform/embedding.py`

```python
"""Embedding prefix transform for QMD-style formatting."""
from llama_index.core.schema import BaseNode, TransformComponent


class EmbeddingPrefixTransform(TransformComponent):
    """Apply prefix formatting to node text before embedding."""

    def __init__(self, prefix_template: str = "title: {title} | text: "):
        self.prefix_template = prefix_template

    def __call__(self, nodes: list[BaseNode], **kwargs) -> list[BaseNode]:
        for node in nodes:
            title = node.metadata.get("title", "")
            prefix = self.prefix_template.format(title=title)
            # Store original text, prepend prefix for embedding
            node.metadata["original_text"] = node.text
            node.text = prefix + node.text
        return nodes
```

**New file:** `catalog/transform/splitter.py` (enhance existing)

```python
"""Resilient text splitter with fallback."""
from llama_index.core.node_parser import TokenTextSplitter, SentenceSplitter
from llama_index.core.schema import BaseNode, TransformComponent
from loguru import logger


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

---

### `catalog.store` — LLM Cache

**New file:** `catalog/store/llm_cache.py`

```python
"""LLM result caching for query expansion and reranking."""
import hashlib
import json
from datetime import datetime, timedelta
from typing import TypeVar, Generic

from sqlalchemy import Column, String, Text, DateTime, create_engine
from sqlalchemy.orm import Session

from catalog.store.database import Base

T = TypeVar("T")


class LLMCacheEntry(Base):
    """SQLAlchemy model for LLM cache entries."""
    __tablename__ = "llm_cache_v2"

    cache_key = Column(String, primary_key=True)
    cache_type = Column(String, nullable=False)  # 'expansion' | 'rerank'
    result_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class LLMCache:
    """Hash-keyed cache for LLM operations."""

    def __init__(self, session: Session, ttl_hours: int = 168):
        self.session = session
        self.ttl = timedelta(hours=ttl_hours)

    def _make_key(self, cache_type: str, *parts: str) -> str:
        content = f"{cache_type}:" + ":".join(parts)
        return hashlib.sha256(content.encode()).hexdigest()

    def _is_expired(self, entry: LLMCacheEntry) -> bool:
        return datetime.utcnow() - entry.created_at > self.ttl

    # Query expansion cache
    def get_expansion(self, query: str, model: str) -> dict | None:
        key = self._make_key("expansion", query, model)
        entry = self.session.get(LLMCacheEntry, key)
        if entry and not self._is_expired(entry):
            return json.loads(entry.result_json)
        return None

    def set_expansion(self, query: str, model: str, result: dict) -> None:
        key = self._make_key("expansion", query, model)
        entry = LLMCacheEntry(
            cache_key=key,
            cache_type="expansion",
            result_json=json.dumps(result),
        )
        self.session.merge(entry)
        self.session.commit()

    # Rerank cache
    def get_rerank(self, query: str, doc_hash: str, model: str) -> float | None:
        key = self._make_key("rerank", query, doc_hash, model)
        entry = self.session.get(LLMCacheEntry, key)
        if entry and not self._is_expired(entry):
            return json.loads(entry.result_json)["score"]
        return None

    def set_rerank(self, query: str, doc_hash: str, model: str, score: float) -> None:
        key = self._make_key("rerank", query, doc_hash, model)
        entry = LLMCacheEntry(
            cache_key=key,
            cache_type="rerank",
            result_json=json.dumps({"score": score}),
        )
        self.session.merge(entry)
        self.session.commit()
```

---

### `catalog.search` — Query Expansion

**New file:** `catalog/search/query_expansion.py`

```python
"""Query expansion using LLM with structured output."""
from dataclasses import dataclass
from llama_index.core.indices.query.query_transform.base import QueryTransform
from llama_index.core.schema import QueryBundle

from catalog.llm.provider import get_llm_provider
from catalog.llm.prompts import QUERY_EXPANSION_PROMPT
from catalog.store.llm_cache import LLMCache


@dataclass
class QueryExpansionResult:
    """Structured query expansion result."""
    original: str
    lex_expansions: list[str]  # BM25 keyword variants
    vec_expansions: list[str]  # Semantic reformulations
    hyde_passage: str | None   # Hypothetical document


class QueryExpansionTransform(QueryTransform):
    """Generate lex/vec/hyde expansions from a query."""

    def __init__(
        self,
        cache: LLMCache | None = None,
        max_lex: int = 3,
        max_vec: int = 3,
        include_hyde: bool = True,
    ):
        self.cache = cache
        self.max_lex = max_lex
        self.max_vec = max_vec
        self.include_hyde = include_hyde
        self._llm = None

    def _get_llm(self):
        if self._llm is None:
            self._llm = get_llm_provider()
        return self._llm

    def _run(self, query_bundle: QueryBundle, metadata: dict) -> QueryBundle:
        result = self.expand(query_bundle.query_str)
        # Build expanded query list for fusion retriever
        queries = self._build_weighted_queries(result)
        return QueryBundle(query_str=result.original, custom_embedding_strs=queries)

    def expand(self, query: str) -> QueryExpansionResult:
        """Expand query with caching and fallback."""
        # Check cache
        if self.cache:
            cached = self.cache.get_expansion(query, "default")
            if cached:
                return QueryExpansionResult(**cached)

        # Generate expansion
        try:
            result = self._generate_expansion(query)
            result = self._filter_expansions(query, result)
        except Exception:
            result = self._fallback_expansion(query)

        # Cache result
        if self.cache:
            self.cache.set_expansion(query, "default", result.__dict__)

        return result

    def _generate_expansion(self, query: str) -> QueryExpansionResult:
        """Call LLM to generate expansions."""
        llm = self._get_llm()
        response = llm.generate(QUERY_EXPANSION_PROMPT.format(query=query))
        return self._parse_expansion(query, response)

    def _parse_expansion(self, query: str, response: str) -> QueryExpansionResult:
        """Parse tagged lines from LLM response."""
        lex, vec, hyde = [], [], None
        for line in response.strip().split("\n"):
            if line.startswith("lex:"):
                lex.append(line[4:].strip())
            elif line.startswith("vec:"):
                vec.append(line[4:].strip())
            elif line.startswith("hyde:"):
                hyde = line[5:].strip()
        return QueryExpansionResult(
            original=query,
            lex_expansions=lex[:self.max_lex],
            vec_expansions=vec[:self.max_vec],
            hyde_passage=hyde if self.include_hyde else None,
        )

    def _filter_expansions(self, query: str, result: QueryExpansionResult) -> QueryExpansionResult:
        """Filter expansions lacking original query terms."""
        terms = set(t.lower() for t in query.split() if len(t) > 2)

        def has_term(exp: str) -> bool:
            return any(term in exp.lower() for term in terms)

        return QueryExpansionResult(
            original=result.original,
            lex_expansions=[e for e in result.lex_expansions if has_term(e)] or [query],
            vec_expansions=[e for e in result.vec_expansions if has_term(e)] or [query],
            hyde_passage=result.hyde_passage,
        )

    def _fallback_expansion(self, query: str) -> QueryExpansionResult:
        """Return original query as fallback."""
        return QueryExpansionResult(
            original=query,
            lex_expansions=[query],
            vec_expansions=[query],
            hyde_passage=None,
        )

    def _build_weighted_queries(self, result: QueryExpansionResult) -> list[str]:
        """Build query list with original query duplicated for 2x weight."""
        queries = [result.original, result.original]  # 2x weight
        queries.extend(result.lex_expansions)
        queries.extend(result.vec_expansions)
        if result.hyde_passage:
            queries.append(result.hyde_passage)
        return queries
```

---

### `catalog.search` — Postprocessors

**New file:** `catalog/search/postprocessors.py`

```python
"""LlamaIndex node postprocessors for v2 retrieval pipeline."""
from llama_index.core.postprocessor import BaseNodePostprocessor
from llama_index.core.schema import NodeWithScore, QueryBundle


class TopRankBonusPostprocessor(BaseNodePostprocessor):
    """Add bonus scores to top-ranked results after RRF fusion."""

    def __init__(self, rank_1_bonus: float = 0.05, rank_2_3_bonus: float = 0.02):
        self.rank_1_bonus = rank_1_bonus
        self.rank_2_3_bonus = rank_2_3_bonus

    def _postprocess_nodes(
        self, nodes: list[NodeWithScore], query_bundle: QueryBundle | None = None
    ) -> list[NodeWithScore]:
        for i, node in enumerate(nodes):
            if i == 0:
                node.score = (node.score or 0) + self.rank_1_bonus
            elif i <= 2:
                node.score = (node.score or 0) + self.rank_2_3_bonus
        return sorted(nodes, key=lambda n: n.score or 0, reverse=True)


class KeywordChunkSelector(BaseNodePostprocessor):
    """Select best chunk per document based on keyword hits."""

    def __init__(self, min_term_length: int = 3):
        self.min_term_length = min_term_length

    def _postprocess_nodes(
        self, nodes: list[NodeWithScore], query_bundle: QueryBundle | None = None
    ) -> list[NodeWithScore]:
        if not query_bundle:
            return nodes

        query_terms = set(
            t.lower() for t in query_bundle.query_str.split()
            if len(t) >= self.min_term_length
        )

        # Group by source_doc_id
        doc_chunks: dict[str, list[NodeWithScore]] = {}
        for node in nodes:
            doc_id = node.node.metadata.get("source_doc_id", node.node.node_id)
            doc_chunks.setdefault(doc_id, []).append(node)

        # Select best chunk per doc
        selected = []
        for chunks in doc_chunks.values():
            best = max(chunks, key=lambda n: self._keyword_score(n, query_terms))
            selected.append(best)

        return selected

    def _keyword_score(self, node: NodeWithScore, terms: set[str]) -> int:
        text = node.node.get_content().lower()
        return sum(1 for term in terms if term in text)


class PerDocDedupePostprocessor(BaseNodePostprocessor):
    """Collapse multiple chunks per document to best-scoring chunk."""

    def _postprocess_nodes(
        self, nodes: list[NodeWithScore], query_bundle: QueryBundle | None = None
    ) -> list[NodeWithScore]:
        best_per_doc: dict[str, NodeWithScore] = {}
        for node in nodes:
            doc_id = node.node.metadata.get("source_doc_id", node.node.node_id)
            if doc_id not in best_per_doc or (node.score or 0) > (best_per_doc[doc_id].score or 0):
                best_per_doc[doc_id] = node
        return list(best_per_doc.values())


class ScoreNormalizerPostprocessor(BaseNodePostprocessor):
    """Normalize scores to 0-1 range for fair fusion."""

    def __init__(self, retriever_type: str = "bm25"):
        self.retriever_type = retriever_type

    def _postprocess_nodes(
        self, nodes: list[NodeWithScore], query_bundle: QueryBundle | None = None
    ) -> list[NodeWithScore]:
        if not nodes:
            return nodes

        if self.retriever_type == "bm25":
            max_score = max((n.score or 0) for n in nodes) or 1.0
            for node in nodes:
                node.score = (node.score or 0) / max_score
        elif self.retriever_type == "vector":
            for node in nodes:
                node.score = max(0.0, min(1.0, node.score or 0))

        return nodes
```

---

### `catalog.search` — Snippet Formatting

**New file:** `catalog/search/formatting.py`

```python
"""Snippet extraction and result formatting."""
from dataclasses import dataclass


@dataclass
class Snippet:
    """Line-anchored snippet with diff-style header."""
    text: str
    start_line: int
    end_line: int
    header: str


def extract_snippet(
    chunk_text: str,
    chunk_pos: int,
    doc_content: str,
    doc_path: str,
    max_lines: int = 10,
) -> Snippet:
    """Extract snippet with line numbers from chunk."""
    # Calculate line number from character position
    lines_before = doc_content[:chunk_pos].count("\n")
    start_line = lines_before + 1

    # Extract chunk lines
    chunk_lines = chunk_text.split("\n")[:max_lines]
    end_line = start_line + len(chunk_lines) - 1

    # Build diff-style header
    header = f"@@ -{start_line},{len(chunk_lines)} +{start_line},{len(chunk_lines)} @@ {doc_path}"

    return Snippet(
        text="\n".join(chunk_lines),
        start_line=start_line,
        end_line=end_line,
        header=header,
    )
```

---

### `catalog.search` — Hybrid Retriever V2

**New file:** `catalog/search/hybrid_v2.py`

```python
"""Enhanced hybrid retriever with weighted RRF and query expansion."""
from llama_index.core.retrievers import QueryFusionRetriever, BaseRetriever
from llama_index.core.schema import NodeWithScore, QueryBundle

from catalog.core.settings import get_settings
from catalog.search.fts_chunk import FTSChunkRetriever
from catalog.search.query_expansion import QueryExpansionTransform
from catalog.search.postprocessors import TopRankBonusPostprocessor
from catalog.store.vector import VectorStoreManager


class WeightedRRFRetriever(BaseRetriever):
    """Custom RRF retriever with per-query weighting."""

    def __init__(
        self,
        retrievers: list[BaseRetriever],
        weights: list[float],
        k: int = 60,
        top_n: int = 30,
    ):
        self.retrievers = retrievers
        self.weights = weights
        self.k = k
        self.top_n = top_n

    def _retrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
        all_results = [r.retrieve(query_bundle) for r in self.retrievers]
        return self._weighted_rrf(all_results)

    def _weighted_rrf(self, result_lists: list[list[NodeWithScore]]) -> list[NodeWithScore]:
        scores: dict[str, tuple[float, NodeWithScore]] = {}

        for results, weight in zip(result_lists, self.weights):
            for rank, node in enumerate(results):
                node_id = node.node.node_id
                rrf_score = weight / (self.k + rank + 1)
                if node_id in scores:
                    scores[node_id] = (scores[node_id][0] + rrf_score, node)
                else:
                    scores[node_id] = (rrf_score, node)

        # Sort by score and return top_n
        sorted_items = sorted(scores.values(), key=lambda x: x[0], reverse=True)
        return [
            NodeWithScore(node=item[1].node, score=item[0])
            for item in sorted_items[:self.top_n]
        ]


class HybridRetrieverV2:
    """Factory for building v2 hybrid retrieval pipeline."""

    def __init__(
        self,
        vector_manager: VectorStoreManager,
        fts_retriever: FTSChunkRetriever,
        query_expansion: QueryExpansionTransform | None = None,
    ):
        self.vector_manager = vector_manager
        self.fts_retriever = fts_retriever
        self.query_expansion = query_expansion
        self._settings = get_settings().rag_v2

    def build(
        self,
        dataset_name: str | None = None,
        k_lex: int | None = None,
        k_dense: int | None = None,
        k_fused: int | None = None,
    ) -> BaseRetriever:
        """Build configured hybrid retriever."""
        k_lex = k_lex or self._settings.fts_top_k
        k_dense = k_dense or self._settings.vector_top_k
        k_fused = k_fused or self._settings.fusion_top_k

        # Get vector retriever
        vector_retriever = self.vector_manager.get_retriever(
            similarity_top_k=k_dense,
            dataset_name=dataset_name,
        )

        # Configure FTS retriever
        fts_retriever = self.fts_retriever
        fts_retriever.top_k = k_lex
        if dataset_name:
            fts_retriever.dataset_name = dataset_name

        # Build weighted retrievers list
        # Original query gets 2x weight (via duplication or weights)
        retrievers = [fts_retriever, vector_retriever]
        weights = [
            self._settings.rrf_original_weight,
            self._settings.rrf_original_weight,
        ]

        return WeightedRRFRetriever(
            retrievers=retrievers,
            weights=weights,
            k=self._settings.rrf_k,
            top_n=k_fused,
        )
```

---

### `catalog.search` — Search Service V2

**New file:** `catalog/search/service_v2.py`

```python
"""V2 search service with query expansion, weighted RRF, and caching."""
from catalog.core.settings import get_settings
from catalog.search.models import SearchCriteria, SearchResults, SearchResult
from catalog.search.hybrid_v2 import HybridRetrieverV2
from catalog.search.query_expansion import QueryExpansionTransform
from catalog.search.postprocessors import (
    TopRankBonusPostprocessor,
    KeywordChunkSelector,
    PerDocDedupePostprocessor,
)
from catalog.search.formatting import extract_snippet
from catalog.llm.reranker import CachedReranker
from catalog.store.llm_cache import LLMCache
from catalog.store.vector import VectorStoreManager
from catalog.search.fts_chunk import FTSChunkRetriever


class SearchServiceV2:
    """V2 search orchestrator with full QMD feature parity."""

    def __init__(self, session):
        self.session = session
        self._settings = get_settings().rag_v2
        self._cache = None
        self._hybrid_retriever = None
        self._reranker = None

    @property
    def cache(self) -> LLMCache:
        if self._cache is None:
            self._cache = LLMCache(self.session, ttl_hours=self._settings.cache_ttl_hours)
        return self._cache

    def search(self, criteria: SearchCriteria) -> SearchResults:
        """Execute v2 search with full pipeline."""
        # Build query expansion
        expansion = None
        if self._settings.expansion_enabled:
            expander = QueryExpansionTransform(
                cache=self.cache,
                max_lex=self._settings.expansion_max_lex,
                max_vec=self._settings.expansion_max_vec,
                include_hyde=self._settings.expansion_include_hyde,
            )
            expansion = expander.expand(criteria.query)

        # Build hybrid retriever
        retriever = self._get_hybrid_retriever(criteria.dataset_name)

        # Retrieve with expansion
        if expansion:
            queries = expander._build_weighted_queries(expansion)
            # Run retrieval for each query variant
            all_nodes = []
            for q in queries:
                nodes = retriever.retrieve(q)
                all_nodes.extend(nodes)
            # Dedupe across queries
            nodes = PerDocDedupePostprocessor()._postprocess_nodes(all_nodes)
        else:
            nodes = retriever.retrieve(criteria.query)

        # Apply top-rank bonus
        bonus_pp = TopRankBonusPostprocessor(
            rank_1_bonus=self._settings.rrf_rank1_bonus,
            rank_2_3_bonus=self._settings.rrf_rank23_bonus,
        )
        nodes = bonus_pp._postprocess_nodes(nodes)

        # Apply keyword chunk selection before reranking
        if criteria.rerank:
            chunk_selector = KeywordChunkSelector()
            nodes = chunk_selector._postprocess_nodes(nodes, criteria.query)
            nodes = nodes[:self._settings.rerank_candidates]

            # Rerank
            reranker = self._get_reranker()
            nodes = reranker.rerank(criteria.query, nodes, self._settings.rerank_top_n)

        # Convert to SearchResults
        results = [self._node_to_result(node) for node in nodes[:criteria.limit]]
        return SearchResults(query=criteria.query, results=results)

    def _get_hybrid_retriever(self, dataset_name: str | None) -> HybridRetrieverV2:
        # Lazy initialization
        vector_manager = VectorStoreManager()
        fts_retriever = FTSChunkRetriever(self.session)
        return HybridRetrieverV2(vector_manager, fts_retriever).build(dataset_name)

    def _get_reranker(self) -> CachedReranker:
        if self._reranker is None:
            from catalog.llm.reranker import Reranker
            self._reranker = CachedReranker(Reranker(), self.cache)
        return self._reranker

    def _node_to_result(self, node) -> SearchResult:
        return SearchResult(
            path=node.node.metadata.get("file_path", ""),
            dataset_name=node.node.metadata.get("dataset_name", ""),
            chunk_text=node.node.get_content(),
            chunk_seq=node.node.metadata.get("chunk_seq", 0),
            chunk_pos=node.node.metadata.get("chunk_pos", 0),
            scores={"hybrid": node.score or 0},
        )
```

---

### `catalog.llm` — Cached Reranker

**Update:** `catalog/llm/reranker.py`

```python
"""Enhanced reranker with caching support."""
from llama_index.core.schema import NodeWithScore, QueryBundle

from catalog.store.llm_cache import LLMCache


class CachedReranker:
    """Wrapper around Reranker with LLM cache integration."""

    def __init__(self, reranker, cache: LLMCache, model_name: str = "default"):
        self.reranker = reranker
        self.cache = cache
        self.model_name = model_name

    def rerank(
        self, query: str, nodes: list[NodeWithScore], top_n: int
    ) -> list[NodeWithScore]:
        results = []
        uncached_nodes = []

        for node in nodes:
            doc_hash = node.node.metadata.get("content_hash", node.node.node_id)
            cached_score = self.cache.get_rerank(query, doc_hash, self.model_name)
            if cached_score is not None:
                results.append(NodeWithScore(node=node.node, score=cached_score))
            else:
                uncached_nodes.append(node)

        if uncached_nodes:
            reranked = self.reranker.rerank(query, uncached_nodes)
            for node in reranked:
                doc_hash = node.node.metadata.get("content_hash", node.node.node_id)
                self.cache.set_rerank(query, doc_hash, self.model_name, node.score)
                results.append(node)

        return sorted(results, key=lambda n: n.score or 0, reverse=True)[:top_n]
```

**Update:** `catalog/llm/prompts.py`

```python
"""LLM prompts for query expansion and reranking."""

QUERY_EXPANSION_PROMPT = """Generate search query expansions for: {query}

Output format (one per line):
- lex: keyword variant for BM25 search (1-3 lines)
- vec: semantic reformulation for vector search (1-3 lines)
- hyde: hypothetical document passage that would answer the query (0-1 line)

Example output:
lex: authentication config
lex: auth settings
vec: how to configure user authentication
vec: authentication setup guide
hyde: Authentication can be configured by setting AUTH_SECRET in your environment.

Query: {query}
"""
```

---

### `catalog.ingest` — Ingestion Pipeline V2

**New file:** `catalog/ingest/pipelines_v2.py`

```python
"""V2 ingestion pipeline with resilient transforms."""
from llama_index.core.ingestion import IngestionPipeline, DocstoreStrategy
from llama_index.core.storage.docstore import SimpleDocumentStore

from catalog.core.settings import get_settings
from catalog.embedding import get_embed_model
from catalog.transform.embedding import EmbeddingPrefixTransform
from catalog.transform.splitter import ResilientSplitter
from catalog.transform.llama import PersistenceTransform, ChunkPersistenceTransform
from catalog.ingest.cache import load_pipeline, persist_pipeline


class DatasetIngestPipelineV2:
    """V2 ingestion with resilient chunking and embedding prefixes."""

    def __init__(self, session):
        self.session = session
        self._settings = get_settings().rag_v2

    def build_pipeline(
        self,
        dataset_id: int,
        dataset_name: str,
    ) -> IngestionPipeline:
        """Build v2 ingestion pipeline."""
        # Load existing docstore for deduplication
        docstore = load_pipeline(dataset_name) or SimpleDocumentStore()

        # Get resilient embedding model
        embed_model = get_embed_model(resilient=True)

        pipeline = IngestionPipeline(
            transformations=[
                PersistenceTransform(dataset_id=dataset_id, session=self.session),
                ResilientSplitter(
                    chunk_size_tokens=self._settings.chunk_size,
                    chunk_overlap_tokens=self._settings.chunk_overlap,
                    chars_per_token=self._settings.chunk_chars_per_token,
                    fallback_enabled=self._settings.chunk_fallback_enabled,
                ),
                ChunkPersistenceTransform(
                    dataset_name=dataset_name,
                    session=self.session,
                ),
                EmbeddingPrefixTransform(
                    prefix_template=self._settings.embed_prefix_doc,
                ),
            ],
            docstore=docstore,
            docstore_strategy=DocstoreStrategy.UPSERTS_AND_DELETE,
        )
        return pipeline

    def persist_state(self, dataset_name: str, pipeline: IngestionPipeline) -> None:
        """Persist pipeline state for future deduplication."""
        persist_pipeline(dataset_name, pipeline)
```

---

### `catalog.api.mcp` — MCP Tools

**New directory:** `catalog/api/mcp/`

**New file:** `catalog/api/mcp/__init__.py`

```python
"""MCP server and tools for catalog search."""
from catalog.api.mcp.tools import create_mcp_tools
from catalog.api.mcp.server import run_mcp_server

__all__ = ["create_mcp_tools", "run_mcp_server"]
```

**New file:** `catalog/api/mcp/tools.py`

```python
"""MCP tool definitions for catalog search."""
from llama_index.core.tools import FunctionTool

from catalog.search.service_v2 import SearchServiceV2


def create_mcp_tools(search_service: SearchServiceV2) -> list[FunctionTool]:
    """Create MCP-compatible tools for catalog search."""
    return [
        FunctionTool.from_defaults(
            fn=lambda query, dataset=None, limit=20: _search_fts(search_service, query, dataset, limit),
            name="catalog_search",
            description="BM25 keyword search over indexed documents",
        ),
        FunctionTool.from_defaults(
            fn=lambda query, dataset=None, limit=20: _search_vector(search_service, query, dataset, limit),
            name="catalog_vsearch",
            description="Semantic vector search over indexed documents",
        ),
        FunctionTool.from_defaults(
            fn=lambda query, dataset=None, limit=20, rerank=True: _search_hybrid(search_service, query, dataset, limit, rerank),
            name="catalog_query",
            description="Hybrid search with RRF fusion and optional reranking (best quality)",
        ),
        FunctionTool.from_defaults(
            fn=lambda path_or_docid: _get_document(search_service, path_or_docid),
            name="catalog_get",
            description="Retrieve document by path or docid",
        ),
        FunctionTool.from_defaults(
            fn=lambda pattern: _get_documents(search_service, pattern),
            name="catalog_multi_get",
            description="Retrieve multiple documents by glob pattern",
        ),
        FunctionTool.from_defaults(
            fn=lambda: _get_status(search_service),
            name="catalog_status",
            description="Get index health and collection info",
        ),
    ]


def _search_fts(service, query, dataset, limit):
    from catalog.search.models import SearchCriteria
    criteria = SearchCriteria(query=query, mode="fts", dataset_name=dataset, limit=limit)
    return service.search(criteria)


def _search_vector(service, query, dataset, limit):
    from catalog.search.models import SearchCriteria
    criteria = SearchCriteria(query=query, mode="vector", dataset_name=dataset, limit=limit)
    return service.search(criteria)


def _search_hybrid(service, query, dataset, limit, rerank):
    from catalog.search.models import SearchCriteria
    criteria = SearchCriteria(query=query, mode="hybrid", dataset_name=dataset, limit=limit, rerank=rerank)
    return service.search(criteria)


def _get_document(service, path_or_docid):
    # Implementation depends on existing document retrieval
    pass


def _get_documents(service, pattern):
    # Implementation depends on existing document retrieval
    pass


def _get_status(service):
    from catalog.core.health import check_health
    return check_health()
```

**New file:** `catalog/api/mcp/server.py`

```python
"""MCP server implementation for catalog."""
import json
import sys

from catalog.store.database import get_session
from catalog.search.service_v2 import SearchServiceV2
from catalog.api.mcp.tools import create_mcp_tools


def run_mcp_server():
    """Run catalog as MCP server over stdio."""
    with get_session() as session:
        service = SearchServiceV2(session)
        tools = create_mcp_tools(service)

        # MCP protocol handler
        for line in sys.stdin:
            request = json.loads(line)
            # Process MCP request and dispatch to appropriate tool
            # ... MCP protocol implementation ...
            response = handle_mcp_request(request, tools)
            print(json.dumps(response), flush=True)


def handle_mcp_request(request: dict, tools: list) -> dict:
    """Handle MCP protocol request."""
    # Implementation follows MCP specification
    pass


if __name__ == "__main__":
    run_mcp_server()
```

---

## Evaluation System

### Test Location
Tests live in `tests/rag_v2/` with the following structure:

```
tests/rag_v2/
├── conftest.py              # Fixtures and thresholds
├── fixtures/
│   └── golden_queries.json  # Query-document pairs
├── test_query_expansion.py  # Expansion tests
├── test_postprocessors.py   # Postprocessor tests
├── test_hybrid_retrieval.py # Integration tests
├── test_rerank.py           # Reranking tests
└── test_eval.py             # Golden query evaluation
```

### Golden Query Evaluation

**File:** `tests/rag_v2/conftest.py`

```python
"""Fixtures and thresholds for RAG v2 tests."""

EVAL_THRESHOLDS = {
    "bm25": {
        "easy": {"hit_at_3": 0.80},
        "medium": {"hit_at_3": 0.15},
        "hard": {"hit_at_5": 0.15},
    },
    "vector": {
        "easy": {"hit_at_3": 0.60},
        "medium": {"hit_at_3": 0.40},
        "hard": {"hit_at_5": 0.30},
    },
    "hybrid": {
        "easy": {"hit_at_3": 0.85},
        "medium": {"hit_at_3": 0.50},
        "hard": {"hit_at_5": 0.40},
        "fusion": {"hit_at_3": 0.60},
    },
}
```

---

## Phased Implementation Plan

### Phase 1: Infrastructure & Core Pipeline
**Scope:** Configuration, caching, resilient transforms, basic v2 service.

**Files to create/modify:**
| File | Module | Purpose |
|------|--------|---------|
| `catalog/core/settings.py` | `catalog.core` | Add `RAGv2Settings` |
| `catalog/store/llm_cache.py` | `catalog.store` | LLM result caching |
| `catalog/embedding/resilient.py` | `catalog.embedding` | Batch fallback |
| `catalog/transform/splitter.py` | `catalog.transform` | Resilient chunking |
| `catalog/transform/embedding.py` | `catalog.transform` | Prefix transform |
| `catalog/ingest/pipelines_v2.py` | `catalog.ingest` | V2 ingestion pipeline |

**Tests:** `tests/rag_v2/test_transforms.py`, `tests/rag_v2/test_cache.py`

### Phase 2: Search Pipeline
**Scope:** Query expansion, postprocessors, hybrid retriever v2, service v2.

**Files to create/modify:**
| File | Module | Purpose |
|------|--------|---------|
| `catalog/search/query_expansion.py` | `catalog.search` | Query expansion |
| `catalog/search/postprocessors.py` | `catalog.search` | Node postprocessors |
| `catalog/search/hybrid_v2.py` | `catalog.search` | Weighted RRF retriever |
| `catalog/search/service_v2.py` | `catalog.search` | V2 orchestrator |
| `catalog/search/formatting.py` | `catalog.search` | Snippet extraction |
| `catalog/llm/reranker.py` | `catalog.llm` | Add `CachedReranker` |
| `catalog/llm/prompts.py` | `catalog.llm` | Expansion prompts |

**Tests:** `tests/rag_v2/test_query_expansion.py`, `tests/rag_v2/test_postprocessors.py`, `tests/rag_v2/test_hybrid_retrieval.py`

### Phase 3: MCP & API
**Scope:** MCP tools, server, API integration.

**Files to create:**
| File | Module | Purpose |
|------|--------|---------|
| `catalog/api/mcp/__init__.py` | `catalog.api.mcp` | Package init |
| `catalog/api/mcp/tools.py` | `catalog.api.mcp` | Tool definitions |
| `catalog/api/mcp/server.py` | `catalog.api.mcp` | MCP server |

**Tests:** `tests/rag_v2/test_mcp_tools.py`

### Phase 4: Evaluation & Rollout
**Scope:** Golden queries, metrics, side-by-side comparison.

**Files to create:**
| File | Location | Purpose |
|------|----------|---------|
| `conftest.py` | `tests/rag_v2/` | Thresholds |
| `golden_queries.json` | `tests/rag_v2/fixtures/` | Test data |
| `test_eval.py` | `tests/rag_v2/` | Evaluation suite |

---

## Change Boundaries

- **Do not modify:** `catalog.search.service.SearchService`, `catalog.search.search()`, existing v1 retrievers
- **Extend only:** `catalog.core.settings.Settings` (add `rag_v2` nested settings)
- **New modules:** `catalog.store.llm_cache`, `catalog.search.postprocessors`, `catalog.search.query_expansion`, `catalog.search.hybrid_v2`, `catalog.search.service_v2`, `catalog.search.formatting`, `catalog.api.mcp`
- **Enhanced modules:** `catalog.embedding` (add resilient wrapper), `catalog.transform` (add prefix/splitter), `catalog.llm.reranker` (add cached wrapper), `catalog.ingest.pipelines` (add v2 builder)

---

## Configuration Summary

| Config Key | Type | Default | Module |
|------------|------|---------|--------|
| `SUBSTRATE_RAG_V2__CHUNK_SIZE` | int | 800 | `catalog.core.settings` |
| `SUBSTRATE_RAG_V2__CHUNK_OVERLAP` | int | 120 | `catalog.core.settings` |
| `SUBSTRATE_RAG_V2__CHUNK_FALLBACK_ENABLED` | bool | True | `catalog.core.settings` |
| `SUBSTRATE_RAG_V2__CHUNK_CHARS_PER_TOKEN` | int | 4 | `catalog.core.settings` |
| `SUBSTRATE_RAG_V2__EMBED_BATCH_SIZE` | int | 32 | `catalog.core.settings` |
| `SUBSTRATE_RAG_V2__EMBED_FALLBACK_ENABLED` | bool | True | `catalog.core.settings` |
| `SUBSTRATE_RAG_V2__EMBED_PREFIX_QUERY` | str | "task: search result \| query: " | `catalog.core.settings` |
| `SUBSTRATE_RAG_V2__EMBED_PREFIX_DOC` | str | "title: {title} \| text: " | `catalog.core.settings` |
| `SUBSTRATE_RAG_V2__EXPANSION_ENABLED` | bool | True | `catalog.core.settings` |
| `SUBSTRATE_RAG_V2__EXPANSION_MAX_LEX` | int | 3 | `catalog.core.settings` |
| `SUBSTRATE_RAG_V2__EXPANSION_MAX_VEC` | int | 3 | `catalog.core.settings` |
| `SUBSTRATE_RAG_V2__EXPANSION_INCLUDE_HYDE` | bool | True | `catalog.core.settings` |
| `SUBSTRATE_RAG_V2__RRF_K` | int | 60 | `catalog.core.settings` |
| `SUBSTRATE_RAG_V2__RRF_ORIGINAL_WEIGHT` | float | 2.0 | `catalog.core.settings` |
| `SUBSTRATE_RAG_V2__RRF_EXPANSION_WEIGHT` | float | 1.0 | `catalog.core.settings` |
| `SUBSTRATE_RAG_V2__RRF_RANK1_BONUS` | float | 0.05 | `catalog.core.settings` |
| `SUBSTRATE_RAG_V2__RRF_RANK23_BONUS` | float | 0.02 | `catalog.core.settings` |
| `SUBSTRATE_RAG_V2__RERANK_TOP_N` | int | 10 | `catalog.core.settings` |
| `SUBSTRATE_RAG_V2__RERANK_CANDIDATES` | int | 40 | `catalog.core.settings` |
| `SUBSTRATE_RAG_V2__RERANK_CACHE_ENABLED` | bool | True | `catalog.core.settings` |
| `SUBSTRATE_RAG_V2__CACHE_TTL_HOURS` | int | 168 | `catalog.core.settings` |
| `SUBSTRATE_RAG_V2__SNIPPET_MAX_LINES` | int | 10 | `catalog.core.settings` |
| `SUBSTRATE_RAG_V2__VECTOR_TOP_K` | int | 20 | `catalog.core.settings` |
| `SUBSTRATE_RAG_V2__FTS_TOP_K` | int | 20 | `catalog.core.settings` |
| `SUBSTRATE_RAG_V2__FUSION_TOP_K` | int | 30 | `catalog.core.settings` |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Chunking parity | Provide token-based splitter with char fallback |
| Embedding prefix mismatch | Configurable prefix templates |
| Score comparability | Focus on ranking parity, not score parity |
| Query expansion quality | Caching + fallback to original query |
| RRF weight tuning | Start with TS defaults, tune via evaluation |
| Cache invalidation | TTL-based expiration, manual clear API |
