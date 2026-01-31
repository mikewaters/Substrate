"""Tests for the feature completion workflow script."""

from __future__ import annotations

from pathlib import Path

import pytest
from rich.console import Console

from tools.complete_feature import (
    FeatureOption,
    build_move_plan,
    discover_incomplete_features,
    execute_move_plan,
    normalize_feature_id,
)


def _make_feature(directory: Path, feature_id: str, title: str = "Sample Feature") -> Path:
    feature_dir = directory / feature_id
    feature_dir.mkdir(parents=True, exist_ok=True)
    prd_path = feature_dir / "PRD.md"
    prd_path.write_text(f"# {title}\n\nDetails...\n", encoding="utf-8")
    return feature_dir


def test_normalize_feature_id_accepts_common_formats() -> None:
    assert normalize_feature_id("FEAT-007") == "FEAT-007"
    assert normalize_feature_id("7") == "FEAT-007"
    assert normalize_feature_id("007") == "FEAT-007"

    with pytest.raises(ValueError):
        normalize_feature_id("feature-seven")


def test_discover_incomplete_features_filters_and_sorts(tmp_path: Path) -> None:
    features_dir = tmp_path / "docs" / "features"
    completed_dir = features_dir / "completed"
    completed_dir.mkdir(parents=True, exist_ok=True)

    _make_feature(features_dir, "FEAT-002", title="Second Feature")
    _make_feature(features_dir, "FEAT-001", title="First Feature")
    _make_feature(completed_dir, "FEAT-099", title="Completed")

    (features_dir / "README.md").write_text("docs", encoding="utf-8")

    discovered = discover_incomplete_features(features_dir)

    assert [option.feature_id for option in discovered] == ["FEAT-001", "FEAT-002"]
    assert discovered[0].prd_title == "First Feature"


def test_build_move_plan_validates_missing_and_completed(tmp_path: Path) -> None:
    features_dir = tmp_path / "docs" / "features"
    completed_dir = features_dir / "completed"
    completed_dir.mkdir(parents=True, exist_ok=True)

    _make_feature(features_dir, "FEAT-003")
    _make_feature(features_dir, "FEAT-004")
    _make_feature(completed_dir, "FEAT-005")

    selections, errors = build_move_plan(["FEAT-003", "4", "005"], features_dir, completed_dir)

    assert [option.feature_id for option in selections] == ["FEAT-003", "FEAT-004"]
    assert any("Feature 'FEAT-005'" in message for message in errors)


def test_execute_move_plan_moves_directories(tmp_path: Path) -> None:
    features_dir = tmp_path / "docs" / "features"
    completed_dir = features_dir / "completed"
    completed_dir.mkdir(parents=True, exist_ok=True)

    source_dir = _make_feature(features_dir, "FEAT-010")
    option = FeatureOption("FEAT-010", source_dir, "A Feature")

    console = Console(width=80, record=True)
    exit_code = execute_move_plan(console, [option], completed_dir)

    assert exit_code == 0
    assert not source_dir.exists()
    assert (completed_dir / "FEAT-010").exists()

