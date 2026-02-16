# Corpus Artifact Format

## corpus.jsonl

One document per line. Each line is a JSON object with these fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| doc_id | string | yes | Unique identifier, typically filename or vault-relative path |
| title | string | yes | Document title extracted from first heading, or filename if no heading |
| body | string | yes | Full document body text in markdown |
| frontmatter | object | no | Parsed YAML frontmatter as key-value pairs |

Example line:

```json
{"doc_id": "notes/retrieval-augmented-generation.md", "title": "Retrieval-Augmented Generation", "body": "# Retrieval-Augmented Generation\n\nRAG combines ...", "frontmatter": {"tags": ["search", "llm"], "created": "2025-11-03"}}
```

## queries.json

Top-level JSON object:

| Field | Type | Description |
|-------|------|-------------|
| version | string | Schema version, currently `"1.0"` |
| description | string | What this query set tests |
| queries | array | List of query objects (see below) |

Each query object:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| query | string | yes | The search query text |
| expected_docs | array of string | yes | `doc_id` values that should appear in results |
| difficulty | string | yes | One of `"easy"`, `"medium"`, `"hard"`, `"fusion"` |
| retriever_types | array of string | yes | Subset of `["bm25", "vector", "hybrid"]` indicating which retrievers to evaluate |
| notes | string | no | Explanation of why this query tests what it tests |

Difficulty levels:

- **easy** -- Query terms appear verbatim in expected documents.
- **medium** -- Requires synonym matching or moderate semantic similarity.
- **hard** -- Requires deep semantic understanding; no lexical overlap with target.
- **fusion** -- Designed to test hybrid fusion; one channel finds it, the other does not.

## Corpus Modes

### Curated

Real documents sampled from the vault. Maximum 80 documents. Used for realistic
relevance evaluation. Select documents that cover the failure modes under investigation
plus a representative set of distractors.

### Synthetic

Generated trap documents engineered to expose specific failure modes. Examples:
documents with high BM25 overlap but wrong semantics, or semantically similar
documents that differ by a single critical detail. Always paired with curated docs
so metrics reflect real-world conditions.

### Fixture

A stable, version-controlled corpus checked into the repository under
`tests/fixtures/eval/`. Used for CI regression gates. Must not change between
experiment rounds unless the change is itself the subject of the experiment.
