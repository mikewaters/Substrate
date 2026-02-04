## Prompt for Coding Agent: TypeScript → Python Rewrite Using LlamaIndex (No Duplication)

### Role & Objective

You are a senior engineer tasked with producing a **detailed high-level design** to rewrite an existing **TypeScript** project implementing **RAG + Hybrid Search** into **Python**, using **LlamaIndex** as the core framework.

**Non-negotiable constraint:**

> We must rely on LlamaIndex abstractions for RAG/LLM/hybrid retrieval capabilities and **must not create new modules that duplicate LlamaIndex functionality**. Custom code is allowed only for: *domain-specific glue, configuration, orchestration, integration points, and non-LLM utilities already present in the target Python repo.*

Your final output is a **design document** that will be handed to a second agent who will implement it inside an existing Python codebase that already provides utilities (DB/logging/config/session/etc.).

---

### Inputs You Have Access To

1. The full TypeScript repository (source, tests, configs, docs, examples).
2. Ability to run static analysis and repo-wide searches.
3. Web Search.
4. MCP (Model Context Protocol) tools/servers available in the environment (use them to inspect code, run searches, and consult docs efficiently).

---

### Required Research (Web + Primary Docs)

You must use Web Search to confirm **current** LlamaIndex APIs/patterns (don’t rely on memory). Prefer official LlamaIndex documentation and the run-llama GitHub org.

At minimum, confirm and cite:

* LlamaIndex conceptual RAG pipeline components: querying stage, retrievers, postprocessors, response synthesis, query engines. ([LlamaIndex][1])
* Response synthesis abstractions. ([LlamaIndex][2])
* Ingestion pipeline and transformations concept. ([LlamaIndex][3])
* Hybrid retrieval approaches (BM25 + vector) via fusion / reciprocal rerank / retriever packs or examples. ([LlamaIndex][4])
* Any agent/workflow/tooling abstractions if the TS repo uses “tools”, “function calling”, “agents”, or workflow orchestration. ([LlamaIndex][5])

---

### Step 1 — Analyze the TypeScript Codebase (RAG/LLM/ML Core Only)

Perform a structured analysis of the TS repo and produce an **inventory of ML/RAG/LLM capabilities**. Focus only on “meaningful abstractions” related to:

* **Ingestion**: loaders, parsing, chunking, transformations, metadata enrichment, dedup, caching, embedding.
* **Indexing / Storage**: vector index, hybrid index, lexical index (BM25), docstore, metadata store, multi-index routing.
* **Retrieval**: vector retrieval, BM25 retrieval, hybrid retrieval, fusion strategies, query rewriting, multi-query, reranking, filtering, metadata constraints, time decay.
* **Post-processing**: rerankers, filters, node postprocessors, citation selection, context compression, PII removal.
* **Prompting & Response Synthesis**: summarization strategies, refine/tree/compact modes, response formatting, citations, structured outputs.
* **Chat / Conversational RAG**: memory, condensation, context window management, conversation summarization.
* **Agents / Tools**: tool calling, function calling, planner/executor patterns, workflow steps, tool schemas.
* **Evaluation/Telemetry (only if it affects ML behavior)**: automatic eval loops, retrieval metrics, feedback loops (but ignore generic logging).

**Explicitly ignore** utility abstractions that are not core to ML/RAG/LLM (DB mgmt, session mgmt, config plumbing, auth, generic logging, HTTP routing, deployment scaffolding).

**Deliverable for Step 1:** A sectioned inventory listing each capability with:

* Where it lives in the repo (file paths)
* Key interfaces/classes/functions
* Data flow in/out (inputs, outputs)
* Runtime dependencies (LLMs, embedding providers, vector DBs, rerankers)
* Any “hidden” logic (prompt templates, heuristics, thresholds)

---

### Step 2 — Derive the “Core Abstractions” (Conceptual Model)

From the inventory, derive a **conceptual architecture** of the TS system in terms of ML/RAG primitives, e.g.:

* Document → nodes/chunks → embeddings
* Index construction & persistence
* Query → retrieval → postprocess → synthesis → response
* Optional branches: hybrid retrieval, routing, agents/tools

Represent this as:

* A concise narrative, and
* A simple component diagram (ASCII is fine)

---

### Step 3 — Map Each TS Capability to LlamaIndex Abstractions (No Duplication)

For each capability, identify the **closest LlamaIndex abstraction(s)** that provides the same function. Use Web Search to confirm official names and recommended patterns.

Examples of the types of LlamaIndex building blocks you should consider (verify actual module/class names during research):

* **IngestionPipeline / Transformations** for ingestion flows and node transformations. ([LlamaIndex][3])
* **Node parsers** for chunking/hierarchical chunking strategies. ([LlamaIndex][6])
* **Retrievers** + **RetrieverQueryEngine** (or equivalent) for retrieval orchestration. ([LlamaIndex][7])
* **Response Synthesizer** for synthesis strategies. ([LlamaIndex][2])
* **Hybrid fusion retrievers / reciprocal rerank fusion / packs** for BM25+vector hybrid retrieval. ([LlamaIndex][4])
* **Tools / Workflows / function-calling agent patterns** if the TS system uses tool invocation. ([LlamaIndex][5])

**Deliverable for Step 3: A mapping table** with columns:

1. TS capability / abstraction name
2. Evidence in TS repo (paths + brief description)
3. LlamaIndex abstraction(s) to use (exact names; cite docs)
4. Configuration knobs to match behavior (top_k, chunk_size, filters, rerank settings, fusion weights, etc.)
5. Gaps / behavior differences
6. Required custom glue code (ONLY orchestration/integration; must not re-implement LlamaIndex features)

---

### Step 4 — Produce the High-Level Python Design (Target Architecture)

Write a design that a second agent can implement in an existing Python + LlamaIndex codebase.

#### 4A. Design Principles (must include)

* “Prefer LlamaIndex-native constructs; don’t wrap them unless necessary.”
* “If a TS component maps to a LlamaIndex component, we use the LlamaIndex one.”
* “Custom code is limited to configuration, composition, integration, and domain logic.”
* “Build for testability: deterministic retrieval configs, injectable LLM/embedding providers, snapshot tests for prompts.”

#### 4B. Proposed Module Boundaries (Python)

Define proposed Python modules *at a high level* (names are placeholders), emphasizing LlamaIndex as the center:

* `ingestion/` (pipeline composition using IngestionPipeline + Transformations) ([LlamaIndex][3])
* `indexing/` (index construction + storage bindings)
* `retrieval/` (retrievers, hybrid fusion, rerank/postprocessors) ([LlamaIndex][7])
* `querying/` (query engines, response synthesis configuration) ([LlamaIndex][1])
* `agents/` (only if needed: tools/workflows integration) ([LlamaIndex][5])
* `domain/` (domain-specific adapters that call into LlamaIndex components; no duplication)

**Important:** If the target Python repo already has a folder structure, adapt to it and explain the integration points rather than inventing a new architecture.

#### 4C. End-to-End Dataflows (must include)

Provide step-by-step flows for:

1. **Ingestion flow** (raw docs → nodes → embeddings → index persistence) ([LlamaIndex][3])
2. **Query flow (RAG)** (query → retriever(s) → postprocess → synthesizer → response) ([LlamaIndex][1])
3. **Hybrid flow** (BM25 + vector → fusion → rerank → response) ([LlamaIndex][4])
4. **Agent/tool flow** (if applicable) ([LlamaIndex][5])

#### 4D. Configuration Specification

Define a config schema (conceptually) for the ML/RAG parts only:

* chunking parameters
* embedding model/provider
* vector store connection bindings
* BM25/lexical retrieval options
* hybrid fusion settings
* reranker settings
* prompt templates / synthesis modes
* safety filters or redaction stages (if present)
* evaluation toggles (if present)

Do not include general app config (ports, db pools, logging).

#### 4E. Compatibility Targets

State how you will ensure behavior parity with TS:

* Retrieval quality parity: same filters, top_k, scoring fusion logic
* Prompt parity: prompt templates migrated and versioned
* Response format parity: citations, JSON schemas, tool outputs
* Performance parity: batching embeddings, caching, async where appropriate (but avoid re-implementing caching if LlamaIndex provides it)

---

### Step 5 — Implementation Plan for the Second Agent

Write a phased plan that assumes an existing Python codebase already exists with utilities:

* Phase 1: Minimal vertical slice (one corpus → one hybrid query path)
* Phase 2: Add reranking/postprocessing + response synthesis tuning
* Phase 3: Add agents/tools/workflows if required
* Phase 4: Backfill remaining TS capabilities and edge cases
* Phase 5: Evaluation + regression suite + load/perf checks

Include clear “Definition of Done” criteria for each phase.

---

### Step 6 — Tests & Evaluation (RAG-Specific)

Propose tests that validate ML/RAG correctness rather than utilities:

* Golden query set comparisons (expected citations / sources)
* Retrieval unit tests (filters, metadata constraints, hybrid fusion ordering)
* Prompt snapshot tests
* Safety/redaction tests (if applicable)
* Offline evaluation harness (only if TS had one; otherwise keep minimal)

---

### Step 7 — Deliverable Format (Your Final Output)

Your response must be a single, structured **design document** with:

1. Executive summary
2. TS capability inventory (core only)
3. Conceptual architecture (TS)
4. Capability → LlamaIndex mapping table (with citations from official docs)
5. Proposed Python architecture & module boundaries
6. Dataflows (ingestion/query/hybrid/agent)
7. Config spec (ML/RAG only)
8. Implementation plan for the integrating agent
9. Testing & evaluation strategy
10. Risks, gaps, and explicit “won’t build” items (because LlamaIndex provides it)

---

### Hard Rules (Enforce Throughout)

* **Do not design or propose custom implementations** of retrieval, fusion, reranking, ingestion transforms, query engines, response synthesis, or agent tool orchestration **if LlamaIndex already provides an abstraction** for it.
* If LlamaIndex provides 80% of a capability, use it and document the remaining 20% as minimal glue/config.
* Prefer LlamaIndex idioms: retrievers, query engines, node postprocessors, ingestion pipeline/transformations, response synthesizers, and official hybrid retrieval patterns. ([LlamaIndex][7])

### Non-goals
* Do not propose building new vector stores, embedding models, LLM integrations, or caching layers if LlamaIndex already supports them.
* Do not investigate external interfaces (APIs, UIs, DBs) except to the extent they affect ML/RAG behavior. We will not be providing a CLI, or APIs, or database schemas. We only care about core ML/RAG architecture.

[1]: https://developers.llamaindex.ai/python/framework/understanding/rag/querying/?utm_source=chatgpt.com "Querying | LlamaIndex Python Documentation"
[2]: https://developers.llamaindex.ai/python/framework/module_guides/querying/response_synthesizers/?utm_source=chatgpt.com "Response Synthesizer | LlamaIndex Python Documentation"
[3]: https://developers.llamaindex.ai/python/framework/module_guides/loading/ingestion_pipeline/?utm_source=chatgpt.com "Ingestion Pipeline | LlamaIndex Python Documentation"
[4]: https://developers.llamaindex.ai/python/examples/retrievers/reciprocal_rerank_fusion/?utm_source=chatgpt.com "Reciprocal Rerank Fusion Retriever"
[5]: https://developers.llamaindex.ai/python/examples/workflow/function_calling_agent/?utm_source=chatgpt.com "Workflow for a Function Calling Agent"
[6]: https://developers.llamaindex.ai/python/framework/module_guides/loading/node_parsers/modules/?utm_source=chatgpt.com "Node Parser Modules | LlamaIndex Python Documentation"
[7]: https://developers.llamaindex.ai/python/framework/module_guides/querying/retriever/?utm_source=chatgpt.com "Retriever | LlamaIndex Python Documentation"
