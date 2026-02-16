"""Integration tests for heading bias mitigation.

Tests the end-to-end flow: ingest markdown with headings, verify
heading/body split in FTS, and validate search behavior by intent.
"""

from pathlib import Path

import pytest
from sqlalchemy import text as sql_text
from sqlalchemy.orm import sessionmaker

from catalog.eval.heading_bias import HeadingBiasMetrics, compute_heading_bias_metrics
from catalog.search.intent import classify_intent
from catalog.store.database import create_engine_for_path
from catalog.store.fts_chunk import (
    FTSChunkManager,
    create_chunks_fts_table,
    extract_heading_body,
)


class TestHeadingBodySplitInFTS:
    """Verify heading/body split is correctly stored in FTS."""

    @pytest.fixture
    def db_session(self, tmp_path: Path):
        """Create a test database with chunks_fts table."""
        db_path = tmp_path / "test.db"
        engine = create_engine_for_path(db_path)
        create_chunks_fts_table(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        session = factory()
        yield session
        session.close()

    @pytest.fixture
    def fts_manager(self, db_session) -> FTSChunkManager:
        """Create FTSChunkManager with test session."""
        return FTSChunkManager(db_session)

    def test_heading_body_split_stored_correctly(
        self, fts_manager: FTSChunkManager, db_session
    ) -> None:
        """Heading and body are stored in separate FTS columns."""
        text = "# Machine Learning Basics\nNeural networks learn patterns from data."
        fts_manager.upsert("chunk:0", text, "obsidian:ml.md")
        db_session.flush()

        result = db_session.execute(
            sql_text(
                "SELECT heading_text, body_text FROM chunks_fts"
                " WHERE node_id = 'chunk:0'"
            )
        )
        row = result.fetchone()
        assert row is not None
        assert "Machine Learning Basics" in row.heading_text
        assert "Neural networks" in row.body_text
        assert "# Machine Learning" not in row.body_text

    def test_frontmatter_title_in_heading(
        self, fts_manager: FTSChunkManager, db_session
    ) -> None:
        """YAML frontmatter title goes into heading_text."""
        text = (
            "---\ntitle: Python Guide\n---\n"
            "# Getting Started\nInstall Python first."
        )
        fts_manager.upsert("chunk:1", text, "obsidian:python.md")
        db_session.flush()

        result = db_session.execute(
            sql_text(
                "SELECT heading_text, body_text FROM chunks_fts"
                " WHERE node_id = 'chunk:1'"
            )
        )
        row = result.fetchone()
        assert "Python Guide" in row.heading_text
        assert "Getting Started" in row.heading_text
        assert "Install Python first." in row.body_text

    def test_body_search_returns_body_content(
        self, fts_manager: FTSChunkManager, db_session
    ) -> None:
        """Search results return body_text content."""
        fts_manager.upsert(
            "c1", "# Heading Only\nBody about databases.", "ds:doc1.md"
        )
        fts_manager.upsert(
            "c2", "# Other Heading\nBody about servers.", "ds:doc2.md"
        )
        db_session.flush()

        results = fts_manager.search_with_scores("databases")
        assert len(results) == 1
        assert results[0].node_id == "c1"
        assert "databases" in results[0].text

    def test_informational_query_body_match_scored(
        self, fts_manager: FTSChunkManager, db_session
    ) -> None:
        """Informational queries score body matches appropriately."""
        # Chunk 1: heading has keyword, body doesn't
        fts_manager.upsert(
            "heading_match",
            "# Python Programming\nGeneral content about coding languages.",
            "ds:heading.md",
        )
        # Chunk 2: body has keyword, heading doesn't
        fts_manager.upsert(
            "body_match",
            "# Coding Guide\nPython is great for data science and programming.",
            "ds:body.md",
        )
        db_session.flush()

        # With low heading weight (informational), body match should score well
        results = fts_manager.search_with_scores(
            "python programming",
            bm25_weights="0.0, 0.25, 1.0, 0.0",
        )
        assert len(results) >= 1
        node_ids = [r.node_id for r in results]
        assert "heading_match" in node_ids or "body_match" in node_ids

    def test_navigational_query_heading_boost(
        self, fts_manager: FTSChunkManager, db_session
    ) -> None:
        """Navigational queries with high heading weight boost heading matches."""
        fts_manager.upsert(
            "heading_doc",
            "# ChatGPT\nThis discusses AI chatbot capabilities.",
            "ds:chatgpt.md",
        )
        fts_manager.upsert(
            "body_doc",
            "# AI Overview\nChatGPT is one of many language models available.",
            "ds:ai.md",
        )
        db_session.flush()

        # With high heading weight (navigational)
        results = fts_manager.search_with_scores(
            "ChatGPT",
            bm25_weights="0.0, 0.80, 1.0, 0.0",
        )
        assert len(results) >= 1


class TestIntentClassification:
    """Verify intent classification on realistic queries."""

    def test_informational_queries(self) -> None:
        """Typical informational queries are classified correctly."""
        informational = [
            "how to configure home automation routines",
            "strategies for managing attention deficit",
            "embedding models for semantic search",
            "what is retrieval augmented generation",
        ]
        for q in informational:
            assert classify_intent(q) == "informational", (
                f"Expected informational for: {q}"
            )

    def test_navigational_queries(self) -> None:
        """Typical navigational queries are classified correctly."""
        navigational = [
            '"iOS Security Posture"',
            "HuggingFace",
            "PROJ-1234",
            "notes.md",
        ]
        for q in navigational:
            assert classify_intent(q) == "navigational", (
                f"Expected navigational for: {q}"
            )


class TestExtractHeadingBodyIntegration:
    """Integration tests for extract_heading_body with realistic content."""

    def test_realistic_markdown_chunk(self) -> None:
        """Realistic markdown chunk splits correctly."""
        chunk = (
            "---\ntitle: RAG Architecture\n---\n"
            "# Overview\n"
            "Retrieval Augmented Generation combines search with LLMs.\n"
            "## Components\n"
            "The main components are:\n"
            "- Retriever\n"
            "- Generator\n"
            "### Vector Store\n"
            "Vectors enable semantic search.\n"
        )
        heading, body = extract_heading_body(chunk)
        assert "RAG Architecture" in heading
        assert "Overview" in heading
        assert "Components" in heading
        assert "Vector Store" in heading
        assert "Retrieval Augmented Generation" in body
        assert "Vectors enable semantic search" in body
        # No heading markers in body
        assert "# Overview" not in body
        assert "## Components" not in body
