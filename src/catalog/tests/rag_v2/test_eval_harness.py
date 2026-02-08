"""Tests for search eval harness utilities."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import sys
import types

agentlayer_module = types.ModuleType("agentlayer")
logging_module = types.ModuleType("agentlayer.logging")
logging_module.get_logger = lambda _name: None
agentlayer_module.logging = logging_module
sys.modules.setdefault("agentlayer", agentlayer_module)
sys.modules.setdefault("agentlayer.logging", logging_module)

from catalog.eval import harness


class _RagV2Settings:
    def __init__(self) -> None:
        self.chunk_size = 800
        self.chunk_overlap = 120
        self.rrf_k = 60
        self.rerank_enabled = True
        self.expansion_enabled = True


class _Settings:
    def __init__(self) -> None:
        self.rag_v2 = _RagV2Settings()


def test_compute_corpus_hash_stable_for_same_content(tmp_path: Path) -> None:
    """Corpus hash remains stable for deterministic corpus content."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "note1.md").write_text("alpha")
    (corpus / "nested").mkdir()
    (corpus / "nested" / "note2.md").write_text("beta")

    first_hash = harness.compute_corpus_hash(corpus)
    second_hash = harness.compute_corpus_hash(corpus)

    assert first_hash == second_hash


def test_read_queries_version_returns_declared_version(tmp_path: Path) -> None:
    """Version metadata is read when golden query file provides one."""
    queries_file = tmp_path / "queries.json"
    queries_file.write_text(json.dumps({"version": "2.1", "queries": []}))

    assert harness.read_queries_version(queries_file) == "2.1"


def test_read_eval_metrics_parses_json_after_preface() -> None:
    """Eval metrics parser handles human-readable preface output."""
    payload = "Loaded 3 queries\n{\"hybrid\": {\"easy\": {\"hit_at_1\": 1.0}}}"

    assert harness.read_eval_metrics(payload) == {"hybrid": {"easy": {"hit_at_1": 1.0}}}


def test_build_run_record_includes_expected_sections(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Run record captures metadata, settings, and metrics envelope."""
    corpus = tmp_path / "vault"
    corpus.mkdir()
    (corpus / "doc.md").write_text("content")

    queries_file = tmp_path / "queries.json"
    queries_file.write_text(json.dumps({"version": "1.0", "queries": []}))

    monkeypatch.setattr(harness, "collect_git_metadata", lambda _: harness.GitMetadata("abc", "branch", False))
    monkeypatch.setattr(harness, "get_settings", lambda: _Settings())

    run_record = harness.build_run_record(
        corpus_path=corpus,
        queries_file=queries_file,
        embedding_model="test-model",
        metrics={"hybrid": {"easy": {"hit_at_1": 1.0}}},
        run_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        repo_root=tmp_path,
    )

    assert run_record["run_id"] == "2026-01-01T00:00:00+00:00"
    assert run_record["git"]["commit"] == "abc"
    assert run_record["queries"]["version"] == "1.0"
    assert run_record["settings"]["embedding_model"] == "test-model"
    assert run_record["metrics"]["hybrid"]["easy"]["hit_at_1"] == 1.0


def test_baseline_key_is_deterministic() -> None:
    """Baseline key remains stable for identical metadata content."""
    run_record = {
        "corpus": {"hash": "sha256:abc"},
        "queries": {"version": "1.0"},
        "settings": {
            "embedding_model": "model",
            "fts_impl": "sqlite_fts5",
            "rag_v2": {
                "chunk_size": 800,
                "chunk_overlap": 120,
                "rrf_k": 60,
                "rerank_enabled": True,
                "expansion_enabled": True,
            },
        },
    }

    assert harness.baseline_key(run_record) == harness.baseline_key(run_record)
