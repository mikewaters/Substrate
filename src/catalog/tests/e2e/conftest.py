"""E2E test fixtures for Catalog.

Provisions real, persistent infrastructure (SQLite + file-based Qdrant)
uniquely per test. Databases are NOT deleted after runs so they can be
inspected manually.

The approach: override Settings via environment variables and clear
singleton caches, letting the entire stack initialize through production
code paths. Only the embedding model is mocked (for speed).
"""

import shutil
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from llama_index.core.embeddings import BaseEmbedding

from catalog.core.settings import get_settings
from catalog.store.database import get_registry, get_session, get_session_factory
from catalog.store.vector import VectorStoreManager

from ..backends import SUPPORTED_BACKENDS, configure_backend

E2E_OUTPUT = Path(__file__).parent / ".output"


class MockEmbedding(BaseEmbedding):
    """Deterministic mock embedding model.

    Returns hash-based 384-dim vectors without loading any ML model.
    Compatible with LlamaIndex IngestionPipeline and Qdrant.
    """

    embed_dim: int = 384

    def __init__(self, embed_dim: int = 384, **kwargs: Any):
        """Initialize with embedding dimension."""
        super().__init__(
            model_name="mock-embedding",
            embed_batch_size=32,
            **kwargs,
        )
        self.embed_dim = embed_dim

    def _get_text_embedding(self, text: str) -> list[float]:
        """Get embedding for a single text."""
        hash_val = hash(text) % 1000
        return [0.1 + (hash_val / 10000.0)] * self.embed_dim

    def _get_query_embedding(self, query: str) -> list[float]:
        """Get embedding for a query."""
        return self._get_text_embedding(query)

    async def _aget_text_embedding(self, text: str) -> list[float]:
        """Async version of get_text_embedding."""
        return self._get_text_embedding(text)

    async def _aget_query_embedding(self, query: str) -> list[float]:
        """Async version of get_query_embedding."""
        return self._get_query_embedding(query)


@dataclass
class E2EInfra:
    """Handle to the real, persistent infrastructure provisioned for a test.

    Attributes:
        output_dir: Directory containing catalog.db, qdrant/, cache/.
        embed_model: Mock embedding model used for this test.
    """

    output_dir: Path
    embed_model: MockEmbedding

    @contextmanager
    def session(self) -> Generator:
        """Convenience session using production get_session() code path."""
        with get_session() as session:
            yield session

    def vector_manager(self) -> VectorStoreManager:
        """Get a real VectorStoreManager with mock embedding for search.

        The VectorStoreManager reads paths from settings (which point to
        the test output directory). Mock embedding is injected to bypass
        real model loading in load_or_create().
        """
        vm = VectorStoreManager()
        vm._embed_model = self.embed_model
        return vm


@pytest.fixture
def e2e(request, monkeypatch) -> Generator[E2EInfra, None, None]:
    """Provision real, persistent infrastructure for a single e2e test.

    Creates a unique output directory per test containing:
    - catalog.db (SQLite with FTS5 virtual tables)
    - content.db (SQLite for document bodies)
    - qdrant/ (file-based Qdrant vector store)
    - cache/ (LlamaIndex pipeline docstore cache)

    Databases are cleaned at the START of each run (not after),
    so results from the last run are always available for inspection.
    """
    test_name = request.node.name
    output_dir = E2E_OUTPUT / test_name

    # Clean before (not after) -- results persist for inspection
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    # Clear singleton caches for a fresh start
    get_settings.cache_clear()
    get_registry.cache_clear()
    get_session_factory.cache_clear()

    # Override settings via env vars
    monkeypatch.setenv("SUBSTRATE_DATABASES__CATALOG_PATH", str(output_dir / "catalog.db"))
    monkeypatch.setenv("SUBSTRATE_DATABASES__CONTENT_PATH", str(output_dir / "content.db"))
    monkeypatch.setenv("SUBSTRATE_VECTOR_STORE_PATH", str(output_dir / "qdrant"))
    monkeypatch.setenv("SUBSTRATE_CACHE_PATH", str(output_dir / "cache"))

    embed_model = MockEmbedding(embed_dim=384)

    with patch("catalog.embedding.get_embed_model", return_value=embed_model):
        # Trigger full DB initialization (engine, tables, FTS, content ATTACH)
        get_registry()

        yield E2EInfra(output_dir=output_dir, embed_model=embed_model)

    # Teardown: clear caches so non-e2e tests get fresh singletons
    get_settings.cache_clear()
    get_registry.cache_clear()
    get_session_factory.cache_clear()


@pytest.fixture(params=SUPPORTED_BACKENDS)
def vector_backend(request, e2e, monkeypatch):
    """Configure active vector backend per test invocation."""
    backend = request.param
    configure_backend(monkeypatch, backend, e2e.output_dir)
    yield backend


# ---------------------------------------------------------------------------
# Vault fixtures (same content as integration tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_vault(tmp_path: Path) -> Path:
    """Create a sample Obsidian vault with markdown files."""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".obsidian").mkdir()

    (vault / "note1.md").write_text("""\
---
title: Python Tutorial
tags: [python, tutorial]
---

# Python Tutorial

This is a tutorial about Python programming.
Learn about functions, classes, and modules.
""")

    (vault / "note2.md").write_text("""\
---
title: JavaScript Guide
tags: [javascript, web]
---

# JavaScript Guide

This guide covers JavaScript basics.
Learn about async/await and promises.
""")

    (vault / "note3.md").write_text("""\
---
title: Database Design
tags: [sql, database]
---

# Database Design

Learn about SQL and database normalization.
Covers relational databases and indexes.
""")

    subdir = vault / "projects"
    subdir.mkdir()

    (subdir / "project1.md").write_text("""\
---
title: My Python Project
---

# My Python Project

Building a CLI tool with Python.
Uses argparse and pathlib.
""")

    return vault


@pytest.fixture
def hybrid_vault(tmp_path: Path) -> Path:
    """Create a vault optimized for hybrid search testing.

    Contains documents with distinct keyword and semantic content.
    """
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".obsidian").mkdir()

    (vault / "auth.md").write_text("""\
---
title: Authentication Guide
tags: [security, auth]
---

# Authentication Guide

How to implement user authentication in your application.
OAuth2 is the recommended protocol for secure token-based authentication.
JWT tokens provide stateless session management.
""")

    (vault / "database.md").write_text("""\
---
title: Database Design
tags: [sql, database]
---

# Database Design

SQL databases and schema design patterns.
Indexing strategies for query optimization.
PostgreSQL and SQLite are popular choices.
""")

    (vault / "api.md").write_text("""\
---
title: API Design Patterns
tags: [api, web]
---

# API Design Patterns

RESTful API patterns and best practices.
Rate limiting protects your endpoints.
Authentication endpoints should use HTTPS.
""")

    (vault / "ml.md").write_text("""\
---
title: Machine Learning Basics
tags: [ml, ai]
---

# Machine Learning Basics

Neural networks learn patterns from data.
Training involves optimizing loss functions.
Deep learning requires large datasets.
""")

    (vault / "security.md").write_text("""\
---
title: Security Best Practices
tags: [security]
---

# Security Best Practices

Protect your systems from unauthorized access.
Encryption safeguards sensitive data.
Identity verification prevents impersonation.
""")

    return vault


@pytest.fixture
def sample_docs(tmp_path: Path) -> Path:
    """Create sample documents for directory-based ingest tests."""
    docs = tmp_path / "docs"
    docs.mkdir()

    (docs / "auth.md").write_text("""\
# Authentication

How to implement user authentication.
OAuth2, JWT tokens, and session management.
""")

    (docs / "database.md").write_text("""\
# Database Design

SQL databases and schema design.
Indexing strategies and query optimization.
""")

    (docs / "api.md").write_text("""\
# API Design

RESTful API patterns.
Authentication endpoints and rate limiting.
""")

    return docs


@pytest.fixture
def linked_vault(tmp_path: Path) -> Path:
    """Create an Obsidian vault with cross-linking notes."""
    vault = tmp_path / "linked-vault"
    vault.mkdir()
    (vault / ".obsidian").mkdir()

    (vault / "A.md").write_text("""\
---
title: Note A
tags: [test]
---

# Note A

This note links to [[B]] and [[C]].
Also links to [[B#Section]] (should dedup to just B).
""")

    (vault / "B.md").write_text("""\
---
title: Note B
---

# Note B

Links back to [[A]].
""")

    (vault / "C.md").write_text("""\
---
title: Note C
---

# Note C

Standalone note with no outgoing links.
""")

    (vault / "D.md").write_text("""\
---
title: Note D
---

# Note D

Links to [[NonExistent]] and [[A]].
""")

    return vault


@pytest.fixture
def ontology_vault(tmp_path: Path) -> Path:
    """Create an Obsidian vault with diverse frontmatter for ontology tests."""
    vault = tmp_path / "ontology-vault"
    vault.mkdir()
    (vault / ".obsidian").mkdir()

    (vault / "full_meta.md").write_text("""\
---
title: Full Metadata Note
tags: [python, testing]
note_type: tutorial
author: Mike
description: A note with every ontology field populated.
aliases: [FMN, Full Note]
cssclass: wide
---

# Full Metadata Note

This note exercises all mapped and unmapped frontmatter fields.
""")

    (vault / "alias_title.md").write_text("""\
---
aliases: [Alias-Derived Title]
tags: [experiment]
---

# Some heading

Content that should get the alias as its title.
""")

    (vault / "bare_note.md").write_text("""\
This note has no YAML frontmatter.

It should derive its title from the filename.
""")

    (vault / "extra_keys.md").write_text("""\
---
title: Extra Keys Note
tags: [misc]
custom_field: 42
project: lifeos
---

# Extra Keys Note

Has frontmatter keys not in the ontology.
""")

    (vault / "desc_only.md").write_text("""\
---
title: Description Only
description: Explicit frontmatter description.
---

Body text here.
""")

    return vault
