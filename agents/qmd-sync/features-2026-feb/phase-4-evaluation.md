# Phase 4: Evaluation & Rollout

## Overview
Phase 4 establishes the evaluation framework for measuring v2 search quality and provides mechanisms for safe rollout. This phase ensures v2 meets or exceeds v1 quality before becoming the default.

**Business Value:** Provides confidence in v2 quality through rigorous testing against golden queries, and enables data-driven decisions about rollout timing through side-by-side comparison.

---

## Feature 4.1: Golden Query Evaluation Suite

### Business Value
Establishes a repeatable benchmark for search quality. Enables automated regression testing to catch quality degradations before they reach users. Provides objective metrics for comparing v1 and v2.

### Technical Specification

**Location:** `tests/rag_v2/test_eval.py`

**Golden Query Schema:**
```python
@dataclass
class GoldenQuery:
    query: str
    expected_docs: list[str]  # paths or docids
    difficulty: Literal["easy", "medium", "hard", "fusion"]
    retriever_types: list[Literal["bm25", "vector", "hybrid"]]
    notes: str | None = None
```

**Evaluation Result:**
```python
@dataclass
class EvalResult:
    query: str
    difficulty: str
    retriever_type: str
    hit_at_1: bool
    hit_at_3: bool
    hit_at_5: bool
    hit_at_10: bool
    retrieved_docs: list[str]
    scores: list[float]
```

**Evaluation Function:**
```python
def evaluate_golden_queries(
    search_service: SearchServiceV2,
    golden_queries: list[GoldenQuery],
    k_values: list[int] = [1, 3, 5, 10],
) -> dict[str, dict[str, float]]:
    """
    Evaluate search quality against golden queries.

    Returns metrics grouped by difficulty and retriever_type:
    {
        "bm25": {
            "easy": {"hit_at_3": 0.85, "hit_at_5": 0.90},
            "medium": {"hit_at_3": 0.45, "hit_at_5": 0.60},
        },
        ...
    }
    """
    results = []

    for gq in golden_queries:
        for retriever_type in gq.retriever_types:
            result = _evaluate_single(search_service, gq, retriever_type, k_values)
            results.append(result)

    return _aggregate_metrics(results)
```

**Thresholds:** `tests/rag_v2/conftest.py`
```python
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

### Golden Query Categories

**Easy (exact keyword matches):**
- Query contains distinctive keywords that appear in target document
- BM25 should excel, vector should also work
- Example: "authentication configuration" → docs/auth-config.md

**Medium (semantic/conceptual):**
- Query uses different terminology than document
- Vector should excel, BM25 may struggle
- Example: "how to set up user login" → docs/auth-config.md

**Hard (vague/partial memory):**
- Query is incomplete or uses common words
- Both retrievers may struggle; tests recall improvement
- Example: "that document about settings" → docs/auth-config.md

**Fusion (requires both signals):**
- Query needs both keyword match AND semantic understanding
- Hybrid should excel; tests RRF effectiveness
- Example: "REST API error handling best practices" → docs/api-design.md

### Acceptance Criteria
- [ ] GoldenQuery and EvalResult dataclasses
- [ ] evaluate_golden_queries function
- [ ] Hit@K metric calculation
- [ ] Difficulty-stratified reporting
- [ ] Threshold configuration
- [ ] Pytest integration for CI
- [ ] At least 24 golden queries across categories

### Dependencies
- Feature 2.6 (SearchServiceV2)

### Estimated Effort
Medium (4-5 hours)

---

## Feature 4.2: Golden Query Dataset

### Business Value
Curated test data that represents real-world search scenarios. Enables consistent evaluation across development cycles and provides a baseline for quality improvements.

### Technical Specification

**Location:** `tests/rag_v2/fixtures/golden_queries.json`

**Schema:**
```json
{
  "version": "1.0",
  "description": "Golden queries for RAG v2 evaluation",
  "queries": [
    {
      "query": "authentication configuration",
      "expected_docs": ["docs/auth-config.md"],
      "difficulty": "easy",
      "retriever_types": ["bm25", "vector", "hybrid"],
      "notes": "Direct keyword match"
    },
    {
      "query": "how to set up user login",
      "expected_docs": ["docs/auth-config.md"],
      "difficulty": "medium",
      "retriever_types": ["vector", "hybrid"],
      "notes": "Semantic match, no direct keywords"
    }
  ]
}
```

**Sample Queries (24 total):**

| Difficulty | Count | Example |
|------------|-------|---------|
| Easy | 6 | "authentication configuration" |
| Medium | 6 | "how to set up user login" |
| Hard | 6 | "that document about settings" |
| Fusion | 6 | "REST API error handling" |

### Acceptance Criteria
- [ ] JSON file with 24+ golden queries
- [ ] Even distribution across difficulty levels
- [ ] Realistic query patterns
- [ ] Clear expected document mappings
- [ ] Notes explaining each query's purpose

### Dependencies
- Test corpus documents

### Estimated Effort
Small (2-3 hours)

---

## Feature 4.3: Side-by-Side Comparison Mode

### Business Value
Enables direct comparison of v1 and v2 results on the same queries. Supports data-driven rollout decisions and helps identify regressions before they affect users.

### Technical Specification

**Location:** `src/catalog/catalog/search/comparison.py`

**Implementation:**
```python
@dataclass
class ComparisonResult:
    query: str
    v1_results: list[SearchResult]
    v2_results: list[SearchResult]
    v1_time_ms: float
    v2_time_ms: float
    overlap_at_5: float  # Jaccard similarity of top 5
    overlap_at_10: float
    rank_correlation: float  # Spearman correlation


class SearchComparison:
    """Compare v1 and v2 search results."""

    def __init__(self, session):
        self.v1_service = SearchService(session)
        self.v2_service = SearchServiceV2(session)

    def compare(self, criteria: SearchCriteria) -> ComparisonResult:
        """Run same query on v1 and v2, compare results."""
        # Time v1
        start = time.perf_counter()
        v1_results = self.v1_service.search(criteria)
        v1_time = (time.perf_counter() - start) * 1000

        # Time v2
        start = time.perf_counter()
        v2_results = self.v2_service.search(criteria)
        v2_time = (time.perf_counter() - start) * 1000

        return ComparisonResult(
            query=criteria.query,
            v1_results=v1_results.results,
            v2_results=v2_results.results,
            v1_time_ms=v1_time,
            v2_time_ms=v2_time,
            overlap_at_5=self._jaccard(v1_results, v2_results, 5),
            overlap_at_10=self._jaccard(v1_results, v2_results, 10),
            rank_correlation=self._spearman(v1_results, v2_results),
        )

    def compare_batch(self, queries: list[str]) -> list[ComparisonResult]:
        """Compare multiple queries."""
        return [self.compare(SearchCriteria(query=q)) for q in queries]

    def summary_report(self, results: list[ComparisonResult]) -> dict:
        """Generate summary statistics."""
        return {
            "total_queries": len(results),
            "avg_v1_time_ms": sum(r.v1_time_ms for r in results) / len(results),
            "avg_v2_time_ms": sum(r.v2_time_ms for r in results) / len(results),
            "avg_overlap_at_5": sum(r.overlap_at_5 for r in results) / len(results),
            "avg_overlap_at_10": sum(r.overlap_at_10 for r in results) / len(results),
            "avg_rank_correlation": sum(r.rank_correlation for r in results) / len(results),
        }
```

### Metrics Explained

**Overlap@K (Jaccard Similarity):**
- Measures how similar the top K results are between v1 and v2
- 1.0 = identical results, 0.0 = completely different
- Target: > 0.7 for top 10 (some improvement expected, not radical change)

**Rank Correlation (Spearman):**
- Measures if documents are ranked in similar order
- 1.0 = identical ranking, -1.0 = reversed ranking
- Target: > 0.5 (moderate correlation, allowing for improvements)

### Acceptance Criteria
- [ ] ComparisonResult dataclass
- [ ] SearchComparison class
- [ ] Jaccard similarity calculation
- [ ] Spearman rank correlation
- [ ] Batch comparison support
- [ ] Summary report generation
- [ ] Unit tests for comparison logic

### Dependencies
- catalog.search.service (existing v1)
- Feature 2.6 (SearchServiceV2)

### Estimated Effort
Medium (3-4 hours)

---

## Feature 4.4: Evaluation CLI Commands

### Business Value
Enables developers and operators to run evaluations from the command line, supporting CI integration and manual quality checks during development.

### Technical Specification

**Location:** `src/catalog/catalog/cli/eval.py`

**Commands:**
```python
import typer
from catalog.search.comparison import SearchComparison
from catalog.eval.golden import evaluate_golden_queries, load_golden_queries

eval_app = typer.Typer()


@eval_app.command()
def golden(
    queries_file: str = "tests/rag_v2/fixtures/golden_queries.json",
    output: str = "json",
):
    """Run golden query evaluation."""
    queries = load_golden_queries(queries_file)
    results = evaluate_golden_queries(queries)

    if output == "json":
        print(json.dumps(results, indent=2))
    else:
        _print_table(results)


@eval_app.command()
def compare(
    query: str,
    dataset: str | None = None,
):
    """Compare v1 and v2 results for a single query."""
    with get_session() as session:
        comparison = SearchComparison(session)
        result = comparison.compare(SearchCriteria(query=query, dataset_name=dataset))
        _print_comparison(result)


@eval_app.command()
def compare_batch(
    queries_file: str,
    output: str = "summary",
):
    """Compare v1 and v2 on multiple queries."""
    queries = _load_queries(queries_file)
    with get_session() as session:
        comparison = SearchComparison(session)
        results = comparison.compare_batch(queries)

        if output == "summary":
            print(json.dumps(comparison.summary_report(results), indent=2))
        else:
            for r in results:
                _print_comparison(r)
```

**Usage:**
```bash
# Run golden query evaluation
uv run catalog eval golden

# Compare single query
uv run catalog eval compare "authentication configuration"

# Batch comparison
uv run catalog eval compare-batch queries.txt --output summary
```

### Acceptance Criteria
- [ ] golden command for evaluation
- [ ] compare command for single query
- [ ] compare-batch command for multiple queries
- [ ] JSON and table output formats
- [ ] Integration with existing CLI

### Dependencies
- Feature 4.1 (evaluation suite)
- Feature 4.3 (comparison mode)
- catalog.cli (existing)

### Estimated Effort
Small (2-3 hours)

---

## Phase 4 Test Plan

**Unit Tests:** `tests/rag_v2/test_evaluation.py`
- Hit@K calculation
- Metric aggregation
- Threshold comparison

**Unit Tests:** `tests/rag_v2/test_comparison.py`
- Jaccard similarity
- Spearman correlation
- Comparison result structure

**Integration Tests:** `tests/rag_v2/test_eval_integration.py`
- Full golden query evaluation
- CLI command execution

---

## Phase 4 Deliverables

| Deliverable | Location |
|-------------|----------|
| Golden query evaluation | `tests/rag_v2/test_eval.py` |
| Golden query dataset | `tests/rag_v2/fixtures/golden_queries.json` |
| Evaluation thresholds | `tests/rag_v2/conftest.py` |
| Comparison mode | `catalog/search/comparison.py` |
| CLI commands | `catalog/cli/eval.py` |
| Unit tests | `tests/rag_v2/test_*.py` |

---

## Rollout Checklist

Before making v2 the default:

1. **Quality Gates:**
   - [ ] All golden queries pass thresholds
   - [ ] Side-by-side overlap@10 > 0.7
   - [ ] No P0 bugs in v2 path

2. **Performance Gates:**
   - [ ] v2 latency within 2x of v1 (without cache)
   - [ ] v2 latency < v1 latency (with cache, after warmup)

3. **Stability Gates:**
   - [ ] 1 week of shadow traffic without errors
   - [ ] Memory usage stable under load

4. **Rollback Plan:**
   - [ ] Feature flag to switch between v1/v2
   - [ ] Monitoring for quality degradation
   - [ ] Automated rollback on error rate spike
