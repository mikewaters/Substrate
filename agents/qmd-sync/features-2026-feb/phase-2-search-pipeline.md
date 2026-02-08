# Phase 2: Search Pipeline

## Overview
Phase 2 implements the core search functionality for RAG v2, including query expansion, weighted RRF fusion, and cached reranking. This phase delivers the primary user-facing improvements in search quality.

**Business Value:** Significantly improves search relevance through multi-query expansion and sophisticated ranking algorithms, while maintaining low latency through intelligent caching.

---

## Feature 2.1: Query Expansion System

### Business Value
Increases recall by 20-40% by generating multiple query variants. Users find relevant documents even when their query doesn't exactly match document terminology. Reduces "no results" scenarios.

### Technical Specification

**Location:** `src/catalog/catalog/search/query_expansion.py`

**Data Model:**
```python
@dataclass
class QueryExpansionResult:
    original: str
    lex_expansions: list[str]  # BM25 keyword variants (1-3)
    vec_expansions: list[str]  # Semantic reformulations (1-3)
    hyde_passage: str | None   # Hypothetical document (0-1)
```

**Implementation:**
```python
class QueryExpansionTransform(QueryTransform):
    def __init__(
        self,
        cache: LLMCache | None = None,
        max_lex: int = 3,
        max_vec: int = 3,
        include_hyde: bool = True,
    ): ...

    def expand(self, query: str) -> QueryExpansionResult:
        # 1. Check cache
        # 2. Generate expansion via LLM
        # 3. Parse structured output (lex:/vec:/hyde: tags)
        # 4. Filter expansions lacking query terms
        # 5. Cache and return

    def _filter_expansions(self, query: str, result: QueryExpansionResult) -> QueryExpansionResult:
        # Ensure expansions maintain query intent
        terms = set(t.lower() for t in query.split() if len(t) > 2)
        # Filter expansions not containing any original terms

    def _fallback_expansion(self, query: str) -> QueryExpansionResult:
        # Return original query when expansion fails
```

**LLM Prompt:** `src/catalog/catalog/llm/prompts.py`
```python
QUERY_EXPANSION_PROMPT = """Generate search query expansions for: {query}

Output format (one per line):
- lex: keyword variant for BM25 search (1-3 lines)
- vec: semantic reformulation for vector search (1-3 lines)
- hyde: hypothetical document passage (0-1 line)

Query: {query}
"""
```

### Acceptance Criteria
- [ ] QueryExpansionResult dataclass
- [ ] QueryExpansionTransform with LlamaIndex QueryTransform interface
- [ ] Structured output parsing (lex:/vec:/hyde: tags)
- [ ] Quality filtering (require original query terms)
- [ ] Graceful fallback on LLM failure
- [ ] Cache integration
- [ ] Unit tests for expansion logic
- [ ] Integration test with actual LLM

### Dependencies
- Feature 1.2 (LLM cache)
- catalog.llm.provider (existing)

### Estimated Effort
Medium (4-5 hours)

---

## Feature 2.2: RRF Postprocessors

### Business Value
Fine-tunes ranking quality by protecting high-confidence matches and normalizing scores across retrieval modes. Ensures top results are truly relevant, improving user trust in search.

### Technical Specification

**Location:** `src/catalog/catalog/search/postprocessors.py`

**TopRankBonusPostprocessor:**
```python
class TopRankBonusPostprocessor(BaseNodePostprocessor):
    """Add bonus scores to top-ranked results after RRF fusion."""

    def __init__(self, rank_1_bonus: float = 0.05, rank_2_3_bonus: float = 0.02):
        self.rank_1_bonus = rank_1_bonus
        self.rank_2_3_bonus = rank_2_3_bonus

    def _postprocess_nodes(self, nodes, query_bundle):
        for i, node in enumerate(nodes):
            if i == 0:
                node.score += self.rank_1_bonus
            elif i <= 2:
                node.score += self.rank_2_3_bonus
        return sorted(nodes, key=lambda n: n.score, reverse=True)
```

**KeywordChunkSelector:**
```python
class KeywordChunkSelector(BaseNodePostprocessor):
    """Select best chunk per document based on keyword hits."""

    def _postprocess_nodes(self, nodes, query_bundle):
        # Group by source_doc_id
        # Select chunk with most query term matches per doc
        # Return one chunk per document
```

**PerDocDedupePostprocessor:**
```python
class PerDocDedupePostprocessor(BaseNodePostprocessor):
    """Collapse multiple chunks per document to best-scoring chunk."""

    def _postprocess_nodes(self, nodes, query_bundle):
        best_per_doc = {}
        for node in nodes:
            doc_id = node.node.metadata.get("source_doc_id")
            if doc_id not in best_per_doc or node.score > best_per_doc[doc_id].score:
                best_per_doc[doc_id] = node
        return list(best_per_doc.values())
```

**ScoreNormalizerPostprocessor:**
```python
class ScoreNormalizerPostprocessor(BaseNodePostprocessor):
    """Normalize scores to 0-1 range for fair fusion."""

    def __init__(self, retriever_type: str = "bm25"):
        self.retriever_type = retriever_type

    def _postprocess_nodes(self, nodes, query_bundle):
        if self.retriever_type == "bm25":
            max_score = max(n.score for n in nodes) or 1.0
            for node in nodes:
                node.score = node.score / max_score
        return nodes
```

### Acceptance Criteria
- [ ] TopRankBonusPostprocessor with configurable bonuses
- [ ] KeywordChunkSelector with term matching logic
- [ ] PerDocDedupePostprocessor with source_doc_id grouping
- [ ] ScoreNormalizerPostprocessor for BM25/vector normalization
- [ ] All implement BaseNodePostprocessor interface
- [ ] Unit tests for each postprocessor

### Dependencies
- llama_index.core.postprocessor

### Estimated Effort
Medium (3-4 hours)

---

## Feature 2.3: Weighted RRF Hybrid Retriever

### Business Value
Combines lexical and semantic search with intelligent weighting. Original query results get 2x weight, protecting exact matches while still benefiting from query expansion. Achieves best-of-both-worlds retrieval.

### Technical Specification

**Location:** `src/catalog/catalog/search/hybrid_v2.py`

**WeightedRRFRetriever:**
```python
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

    def _weighted_rrf(self, result_lists):
        scores = {}
        for results, weight in zip(result_lists, self.weights):
            for rank, node in enumerate(results):
                rrf_score = weight / (self.k + rank + 1)
                scores[node.node.node_id] = scores.get(node.node.node_id, 0) + rrf_score
        # Sort and return top_n
```

**HybridRetrieverV2 Factory:**
```python
class HybridRetrieverV2:
    """Factory for building v2 hybrid retrieval pipeline."""

    def build(self, dataset_name: str | None = None, ...) -> BaseRetriever:
        # Get vector and FTS retrievers
        # Configure with settings
        # Return WeightedRRFRetriever
```

### Acceptance Criteria
- [ ] WeightedRRFRetriever with configurable weights
- [ ] RRF formula: weight / (k + rank + 1)
- [ ] HybridRetrieverV2 factory class
- [ ] Integration with existing FTSChunkRetriever and VectorStoreManager
- [ ] Dataset filtering support
- [ ] Unit tests for RRF calculation
- [ ] Integration test with both retrievers

### Dependencies
- catalog.search.fts_chunk (existing)
- catalog.store.vector (existing)
- Feature 1.1 (settings)

### Estimated Effort
Medium (4-5 hours)

---

## Feature 2.4: Cached Reranker

### Business Value
Reduces reranking latency by 10-100x for repeated queries through intelligent caching. Maintains ranking quality while dramatically improving response times for common searches.

### Technical Specification

**Location:** `src/catalog/catalog/llm/reranker.py` (update existing)

**Implementation:**
```python
class CachedReranker:
    """Wrapper around Reranker with LLM cache integration."""

    def __init__(self, reranker, cache: LLMCache, model_name: str = "default"):
        self.reranker = reranker
        self.cache = cache
        self.model_name = model_name

    def rerank(self, query: str, nodes: list[NodeWithScore], top_n: int) -> list[NodeWithScore]:
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

        return sorted(results, key=lambda n: n.score, reverse=True)[:top_n]
```

### Acceptance Criteria
- [ ] CachedReranker wrapper class
- [ ] Per-document cache lookup by content_hash
- [ ] Partial cache hits (mix cached and uncached)
- [ ] Cache population on rerank
- [ ] Unit tests with mocked cache
- [ ] Integration test with actual reranker

### Dependencies
- Feature 1.2 (LLM cache)
- catalog.llm.reranker (existing)

### Estimated Effort
Small (2-3 hours)

---

## Feature 2.5: Snippet Formatting

### Business Value
Provides contextual citations with line numbers, enabling users to quickly navigate to relevant content. Improves trust and usability by showing exactly where information comes from.

### Technical Specification

**Location:** `src/catalog/catalog/search/formatting.py`

**Implementation:**
```python
@dataclass
class Snippet:
    text: str
    start_line: int
    end_line: int
    header: str  # e.g., "@@ -15,10 +15,10 @@ path/to/file.md"

def extract_snippet(
    chunk_text: str,
    chunk_pos: int,
    doc_content: str,
    doc_path: str,
    max_lines: int = 10,
) -> Snippet:
    # Calculate line number from character position
    lines_before = doc_content[:chunk_pos].count("\n")
    start_line = lines_before + 1

    # Extract chunk lines
    chunk_lines = chunk_text.split("\n")[:max_lines]
    end_line = start_line + len(chunk_lines) - 1

    # Build diff-style header
    header = f"@@ -{start_line},{len(chunk_lines)} +{start_line},{len(chunk_lines)} @@ {doc_path}"

    return Snippet(text="\n".join(chunk_lines), start_line=start_line, end_line=end_line, header=header)
```

### Acceptance Criteria
- [ ] Snippet dataclass with line numbers
- [ ] extract_snippet function
- [ ] Diff-style header generation
- [ ] Configurable max lines
- [ ] Unit tests with various chunk positions

### Dependencies
None (pure utility)

### Estimated Effort
Small (1-2 hours)

---

## Feature 2.6: Search Service V2

### Business Value
Unified orchestrator that combines all Phase 2 components into a production-ready search service. Provides the primary interface for v2 search, delivering measurably better results than v1.

### Technical Specification

**Location:** `src/catalog/catalog/search/service_v2.py`

**Implementation:**
```python
class SearchServiceV2:
    """V2 search orchestrator with full QMD feature parity."""

    def __init__(self, session):
        self.session = session
        self._settings = get_settings().rag_v2
        self._cache = None
        self._reranker = None

    @property
    def cache(self) -> LLMCache:
        if self._cache is None:
            self._cache = LLMCache(self.session, ttl_hours=self._settings.cache_ttl_hours)
        return self._cache

    def search(self, criteria: SearchCriteria) -> SearchResults:
        # 1. Query expansion (if enabled)
        # 2. Build hybrid retriever
        # 3. Retrieve with expansion
        # 4. Apply top-rank bonus
        # 5. Keyword chunk selection (if reranking)
        # 6. Rerank (if enabled)
        # 7. Convert to SearchResults

    def search_fts(self, query: str, dataset: str | None, limit: int) -> SearchResults: ...
    def search_vector(self, query: str, dataset: str | None, limit: int) -> SearchResults: ...
    def search_hybrid(self, query: str, dataset: str | None, limit: int, rerank: bool) -> SearchResults: ...
```

**Convenience Function:** `src/catalog/catalog/search/__init__.py`
```python
def search_v2(criteria: SearchCriteria) -> SearchResults:
    """V2 search with query expansion, weighted RRF, and caching."""
    with get_session() as session:
        service = SearchServiceV2(session)
        return service.search(criteria)
```

### Acceptance Criteria
- [ ] SearchServiceV2 class with lazy initialization
- [ ] Integration with all Phase 2 components
- [ ] search(), search_fts(), search_vector(), search_hybrid() methods
- [ ] Convenience function search_v2()
- [ ] Unit tests for orchestration logic
- [ ] Integration test with full pipeline

### Dependencies
- Feature 2.1 (query expansion)
- Feature 2.2 (postprocessors)
- Feature 2.3 (hybrid retriever)
- Feature 2.4 (cached reranker)
- Feature 2.5 (snippet formatting)
- Feature 1.1 (settings)
- Feature 1.2 (LLM cache)

### Estimated Effort
Medium (4-5 hours)

---

## Phase 2 Test Plan

**Unit Tests:** `tests/rag_v2/test_query_expansion.py`
- Expansion parsing
- Quality filtering
- Fallback behavior
- Cache integration

**Unit Tests:** `tests/rag_v2/test_postprocessors.py`
- TopRankBonusPostprocessor scoring
- KeywordChunkSelector selection logic
- PerDocDedupePostprocessor deduplication
- ScoreNormalizerPostprocessor normalization

**Integration Tests:** `tests/rag_v2/test_hybrid_retrieval.py`
- Full search pipeline execution
- FTS + vector combination
- Reranking integration
- Result ordering

---

## Phase 2 Deliverables

| Deliverable | Location |
|-------------|----------|
| QueryExpansionTransform | `catalog/search/query_expansion.py` |
| Postprocessors | `catalog/search/postprocessors.py` |
| WeightedRRFRetriever | `catalog/search/hybrid_v2.py` |
| CachedReranker | `catalog/llm/reranker.py` |
| Snippet utilities | `catalog/search/formatting.py` |
| SearchServiceV2 | `catalog/search/service_v2.py` |
| QUERY_EXPANSION_PROMPT | `catalog/llm/prompts.py` |
| Unit tests | `tests/rag_v2/test_*.py` |
