"""Behave step definitions for ingest-and-search BDD scenarios."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator
from unittest.mock import patch

from behave import given, then, when
from sqlalchemy.orm import Session, sessionmaker

from catalog.ingest.directory import SourceDirectoryConfig
from catalog.ingest.pipelines import DatasetIngestPipeline
from catalog.search.fts import FTSSearch
from catalog.search.models import SearchCriteria


@contextmanager
def create_session(factory: sessionmaker) -> Generator[Session, None, None]:
    """Create a database session that auto-commits on exit."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def corpus_root() -> Path:
    """Return the root directory for named test corpora."""
    return Path(__file__).resolve().parents[2] / "corpus"


def resolve_corpus_path(corpus_name: str) -> Path:
    """Resolve a named corpus directory to an absolute path."""
    return corpus_root() / corpus_name


def default_dataset_name(corpus_path: Path) -> str:
    """Derive a deterministic dataset name for a corpus."""
    return corpus_path.name


@given('the "{corpus_name}" corpus')
def step_corpus(context: Any, corpus_name: str) -> None:
    """Load a named corpus for ingestion."""
    corpus_path = resolve_corpus_path(corpus_name)
    if not corpus_path.exists():
        raise AssertionError(f"Corpus '{corpus_name}' not found at {corpus_path}")
    context.vault = corpus_path
    context.dataset_name = default_dataset_name(corpus_path)


@when("I ingest the corpus")
def step_ingest_corpus(context: Any) -> None:
    """Ingest the selected corpus into the temporary database."""
    pipeline = DatasetIngestPipeline()
    dataset_name = getattr(context, "dataset_name", "test-corpus")
    config = SourceDirectoryConfig(
        source_path=context.vault,
        dataset_name=dataset_name,
        patterns=["**/*.md"],
    )

    @contextmanager
    def get_test_session() -> Generator[Session, None, None]:
        with create_session(context.session_factory) as session:
            yield session

    with patch("catalog.ingest.pipelines.get_session", get_test_session):
        context.ingest_result = pipeline.ingest_dataset(config)


@then("the ingest result reports 4 documents created and 0 failures")
def step_verify_ingest_result(context: Any) -> None:
    """Assert the ingest result matches the expected counts."""
    assert context.ingest_result.documents_created == 4
    assert context.ingest_result.documents_failed == 0


@when('I search for "{query}" with limit {limit:d}')
def step_search(context: Any, query: str, limit: int) -> None:
    """Run a search against the ingested content."""
    with create_session(context.session_factory) as session:
        search = FTSSearch(session)
        context.search_results = search.search(
            SearchCriteria(query=query, limit=limit)
        )


@then("I should see at least 2 results")
def step_verify_result_count(context: Any) -> None:
    """Ensure at least two search results are returned."""
    assert len(context.search_results.results) >= 2


@then('the result paths should include "note1.md" or "projects/project1.md"')
def step_verify_result_paths(context: Any) -> None:
    """Validate that expected paths appear in the search results."""
    paths = {result.path for result in context.search_results.results}
    assert "note1.md" in paths or "projects/project1.md" in paths
