"""Tests for dataset selection utilities."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from ontology.loader.selection import (
    DEFAULT_DATA_DIRECTORY,
    DatasetLoadStatus,
    list_dataset_files,
    load_selected_datasets,
)


def test_list_dataset_files_filters_and_sorts(tmp_path: Path) -> None:
    """The selector should return only YAML files sorted by name."""
    files = [
        tmp_path / "b.yml",
        tmp_path / "a.yaml",
        tmp_path / "notes.txt",
    ]
    files[0].write_text("foo")
    files[1].write_text("bar")
    files[2].write_text("baz")

    discovered = list_dataset_files(tmp_path)

    assert discovered == [files[1], files[0]]


@pytest.mark.asyncio
async def test_load_selected_datasets_success(db_session) -> None:
    """Loading a known dataset file should succeed and include a summary."""
    sample_file = DEFAULT_DATA_DIRECTORY / "sample_taxonomies.yaml"
    factory = async_sessionmaker(bind=db_session.bind, expire_on_commit=False)

    results = await load_selected_datasets([sample_file], session_factory=factory)

    assert len(results) == 1
    result = results[0]
    assert isinstance(result, DatasetLoadStatus)
    assert result.success is True
    assert result.summary is not None
    assert "taxonomies" in result.summary


@pytest.mark.asyncio
async def test_load_selected_datasets_handles_failures(
    tmp_path: Path, db_session
) -> None:
    """Invalid dataset files should report failures without raising."""
    invalid_file = tmp_path / "broken.yaml"
    invalid_file.write_text("not-a-valid-dataset: []")
    factory = async_sessionmaker(bind=db_session.bind, expire_on_commit=False)

    results = await load_selected_datasets([invalid_file], session_factory=factory)

    assert len(results) == 1
    result = results[0]
    assert result.success is False
    assert result.summary is None
    assert result.error is not None
    assert "Could not detect dataset kind" in result.error
