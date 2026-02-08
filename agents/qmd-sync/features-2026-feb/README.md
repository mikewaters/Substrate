# RAG v2 Implementation Plan

## Overview

This directory contains detailed implementation plans for the LlamaIndex Hybrid RAG v2 migration. The v2 system provides feature parity with the TypeScript QMD system while leveraging LlamaIndex abstractions.

## Phases

| Phase | Focus | Features | Estimated Effort |
|-------|-------|----------|------------------|
| [Phase 1](phase-1-infrastructure.md) | Infrastructure & Core Pipeline | 6 | 12-17 hours |
| [Phase 2](phase-2-search-pipeline.md) | Search Pipeline | 6 | 18-24 hours |
| [Phase 3](phase-3-mcp-api.md) | MCP & API | 3 | 9-12 hours |
| [Phase 4](phase-4-evaluation.md) | Evaluation & Rollout | 4 | 11-15 hours |

**Total:** 19 features, ~50-68 hours estimated

## Feature Summary

### Phase 1: Infrastructure & Core Pipeline
| Feature | Business Value | Module |
|---------|---------------|--------|
| 1.1 RAG v2 Configuration | Environment-driven tuning | `catalog.core.settings` |
| 1.2 LLM Result Caching | 10-100x latency reduction | `catalog.store.llm_cache` |
| 1.3 Resilient Embedding | Batch failure recovery | `catalog.embedding.resilient` |
| 1.4 Resilient Chunking | Tokenizer failure recovery | `catalog.transform.splitter` |
| 1.5 Embedding Prefix | Improved embedding quality | `catalog.transform.embedding` |
| 1.6 V2 Ingestion Pipeline | Production-ready ingestion | `catalog.ingest.pipelines_v2` |

### Phase 2: Search Pipeline
| Feature | Business Value | Module |
|---------|---------------|--------|
| 2.1 Query Expansion | 20-40% recall improvement | `catalog.search.query_expansion` |
| 2.2 RRF Postprocessors | Fine-tuned ranking | `catalog.search.postprocessors` |
| 2.3 Weighted RRF Retriever | Best-of-both-worlds retrieval | `catalog.search.hybrid_v2` |
| 2.4 Cached Reranker | Fast repeated queries | `catalog.llm.reranker` |
| 2.5 Snippet Formatting | Contextual citations | `catalog.search.formatting` |
| 2.6 Search Service V2 | Unified search interface | `catalog.search.service_v2` |

### Phase 3: MCP & API
| Feature | Business Value | Module |
|---------|---------------|--------|
| 3.1 MCP Tool Definitions | Agent-friendly search | `catalog.api.mcp.tools` |
| 3.2 MCP Server | Claude integration | `catalog.api.mcp.server` |
| 3.3 MCP Resources | Navigable knowledge | `catalog.api.mcp.resources` |

### Phase 4: Evaluation & Rollout
| Feature | Business Value | Module |
|---------|---------------|--------|
| 4.1 Golden Query Evaluation | Automated quality testing | `tests/rag_v2/test_eval.py` |
| 4.2 Golden Query Dataset | Consistent benchmarks | `tests/rag_v2/fixtures/` |
| 4.3 Side-by-Side Comparison | Data-driven rollout | `catalog.search.comparison` |
| 4.4 Evaluation CLI | CI integration | `catalog.cli.eval` |

## Dependencies

```
Phase 1 ─────────────────────────────────────────────────────►
         ├─ 1.1 Settings (foundational)
         │     ├─ 1.2 LLM Cache
         │     ├─ 1.3 Resilient Embedding
         │     ├─ 1.4 Resilient Chunking
         │     └─ 1.5 Embedding Prefix
         │           └─ 1.6 V2 Ingestion Pipeline
         │
Phase 2 ─────────────────────────────────────────────────────►
         ├─ 2.1 Query Expansion (needs 1.2)
         ├─ 2.2 Postprocessors (standalone)
         ├─ 2.3 Weighted RRF (needs 1.1)
         ├─ 2.4 Cached Reranker (needs 1.2)
         ├─ 2.5 Snippet Formatting (standalone)
         │     └─ 2.6 Search Service V2 (needs 2.1-2.5)
         │
Phase 3 ─────────────────────────────────────────────────────►
         ├─ 3.1 MCP Tools (needs 2.6)
         │     └─ 3.2 MCP Server (needs 3.1)
         │           └─ 3.3 MCP Resources (needs 3.2)
         │
Phase 4 ─────────────────────────────────────────────────────►
         ├─ 4.1 Golden Query Eval (needs 2.6)
         ├─ 4.2 Golden Query Dataset (standalone)
         ├─ 4.3 Comparison Mode (needs 2.6)
         └─ 4.4 Evaluation CLI (needs 4.1, 4.3)
```

## Related Documents

- [High-level Design](../llamaindex-hybrid-rag-v2.md) - Architecture and abstractions
- [Original Analysis](../llamaindex-improvements.md) - TypeScript capability inventory
