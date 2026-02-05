"""Tests for RAG v2 fixture validation."""

import json
from pathlib import Path

import pytest


FIXTURES_DIR = Path(__file__).parent / "fixtures"
GOLDEN_QUERIES_PATH = FIXTURES_DIR / "golden_queries.json"

VALID_DIFFICULTIES = {"easy", "medium", "hard", "fusion"}
VALID_RETRIEVER_TYPES = {"bm25", "vector", "hybrid"}


class TestGoldenQueriesFixture:
    """Validate the structure and content of golden_queries.json."""

    @pytest.fixture
    def golden_queries(self) -> dict:
        """Load the golden queries fixture."""
        with open(GOLDEN_QUERIES_PATH) as f:
            return json.load(f)

    def test_fixture_file_exists(self):
        """Verify the golden queries fixture file exists."""
        assert GOLDEN_QUERIES_PATH.exists(), f"Missing fixture: {GOLDEN_QUERIES_PATH}"

    def test_valid_json_structure(self, golden_queries: dict):
        """Verify the top-level JSON structure."""
        assert "version" in golden_queries, "Missing 'version' field"
        assert "description" in golden_queries, "Missing 'description' field"
        assert "queries" in golden_queries, "Missing 'queries' field"
        assert isinstance(golden_queries["queries"], list), "'queries' must be a list"

    def test_minimum_query_count(self, golden_queries: dict):
        """Verify we have at least 24 golden queries."""
        query_count = len(golden_queries["queries"])
        assert query_count >= 24, f"Expected at least 24 queries, got {query_count}"

    def test_query_structure(self, golden_queries: dict):
        """Verify each query has the required fields."""
        required_fields = {"query", "expected_docs", "difficulty", "retriever_types", "notes"}

        for i, query in enumerate(golden_queries["queries"]):
            missing = required_fields - set(query.keys())
            assert not missing, f"Query {i} missing fields: {missing}"

    def test_query_field_types(self, golden_queries: dict):
        """Verify each query field has the correct type."""
        for i, query in enumerate(golden_queries["queries"]):
            assert isinstance(query["query"], str), f"Query {i}: 'query' must be a string"
            assert isinstance(query["expected_docs"], list), f"Query {i}: 'expected_docs' must be a list"
            assert isinstance(query["difficulty"], str), f"Query {i}: 'difficulty' must be a string"
            assert isinstance(query["retriever_types"], list), f"Query {i}: 'retriever_types' must be a list"
            assert isinstance(query["notes"], str), f"Query {i}: 'notes' must be a string"

    def test_valid_difficulty_values(self, golden_queries: dict):
        """Verify all difficulty values are valid."""
        for i, query in enumerate(golden_queries["queries"]):
            difficulty = query["difficulty"]
            assert difficulty in VALID_DIFFICULTIES, (
                f"Query {i}: invalid difficulty '{difficulty}', must be one of {VALID_DIFFICULTIES}"
            )

    def test_valid_retriever_types(self, golden_queries: dict):
        """Verify all retriever types are valid."""
        for i, query in enumerate(golden_queries["queries"]):
            for retriever in query["retriever_types"]:
                assert retriever in VALID_RETRIEVER_TYPES, (
                    f"Query {i}: invalid retriever type '{retriever}', must be one of {VALID_RETRIEVER_TYPES}"
                )

    def test_non_empty_fields(self, golden_queries: dict):
        """Verify no fields are empty."""
        for i, query in enumerate(golden_queries["queries"]):
            assert query["query"].strip(), f"Query {i}: 'query' cannot be empty"
            assert query["expected_docs"], f"Query {i}: 'expected_docs' cannot be empty"
            assert query["retriever_types"], f"Query {i}: 'retriever_types' cannot be empty"
            assert query["notes"].strip(), f"Query {i}: 'notes' cannot be empty"

    def test_difficulty_distribution(self, golden_queries: dict):
        """Verify we have queries across all difficulty categories."""
        difficulties = [q["difficulty"] for q in golden_queries["queries"]]
        difficulty_counts = {d: difficulties.count(d) for d in VALID_DIFFICULTIES}

        for difficulty, count in difficulty_counts.items():
            assert count >= 6, f"Expected at least 6 '{difficulty}' queries, got {count}"

    def test_expected_docs_format(self, golden_queries: dict):
        """Verify expected_docs paths look reasonable."""
        for i, query in enumerate(golden_queries["queries"]):
            for doc in query["expected_docs"]:
                assert isinstance(doc, str), f"Query {i}: expected_docs must contain strings"
                assert doc.endswith(".md"), f"Query {i}: expected doc '{doc}' should be a markdown file"

    def test_retriever_types_match_difficulty(self, golden_queries: dict):
        """Verify retriever types align with difficulty expectations."""
        for i, query in enumerate(golden_queries["queries"]):
            difficulty = query["difficulty"]
            retrievers = set(query["retriever_types"])

            if difficulty == "easy":
                assert "bm25" in retrievers, f"Query {i}: easy queries should include 'bm25' retriever"

            if difficulty in ("medium", "hard"):
                assert "vector" in retrievers or "hybrid" in retrievers, (
                    f"Query {i}: {difficulty} queries should include 'vector' or 'hybrid' retriever"
                )

            if difficulty == "fusion":
                assert "hybrid" in retrievers, f"Query {i}: fusion queries should include 'hybrid' retriever"
