"""Tests for catalog.cli.eval module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from catalog.cli import app
from catalog.cli.eval import (
    _check_against_thresholds,
    _load_queries,
    _print_table,
    eval_app,
)


class TestEvalAppStructure:
    """Tests for eval CLI app structure."""

    def test_eval_app_registered_on_main_app(self) -> None:
        """eval subcommand is registered on main app."""
        runner = CliRunner()
        result = runner.invoke(app, ["eval", "--help"])
        assert result.exit_code == 0
        assert "golden" in result.stdout
        assert "compare" in result.stdout

    def test_golden_command_exists(self) -> None:
        """golden command exists in eval app."""
        runner = CliRunner()
        result = runner.invoke(eval_app, ["golden", "--help"])
        assert result.exit_code == 0
        assert "golden queries" in result.stdout.lower()

    def test_compare_command_exists(self) -> None:
        """compare command exists in eval app."""
        runner = CliRunner()
        result = runner.invoke(eval_app, ["compare", "--help"])
        assert result.exit_code == 0
        assert "v1" in result.stdout.lower() or "v2" in result.stdout.lower()

    def test_compare_batch_command_exists(self) -> None:
        """compare-batch command exists in eval app."""
        runner = CliRunner()
        result = runner.invoke(eval_app, ["compare-batch", "--help"])
        assert result.exit_code == 0


class TestGoldenCommand:
    """Tests for golden command."""

    def test_golden_file_not_found_exits_with_error(self) -> None:
        """golden command exits with error when file not found."""
        runner = CliRunner()
        result = runner.invoke(
            eval_app, ["golden", "--queries-file", "/nonexistent/file.json"]
        )
        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_golden_invalid_json_exits_with_error(self, tmp_path: Path) -> None:
        """golden command exits with error on invalid JSON."""
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("{ not valid json")

        runner = CliRunner()
        result = runner.invoke(
            eval_app, ["golden", "--queries-file", str(invalid_file)]
        )
        assert result.exit_code == 1
        assert "invalid" in result.stdout.lower() or "error" in result.stdout.lower()

    def test_golden_json_output(self, tmp_path: Path) -> None:
        """golden command outputs JSON format."""
        golden_file = tmp_path / "golden.json"
        golden_file.write_text(
            json.dumps(
                [
                    {
                        "query": "test query",
                        "expected_docs": ["doc.md"],
                        "difficulty": "easy",
                        "retriever_types": ["bm25"],
                    }
                ]
            )
        )

        mock_results = {
            "bm25": {
                "easy": {
                    "hit_at_1": 0.8,
                    "hit_at_3": 0.9,
                    "hit_at_5": 0.95,
                    "hit_at_10": 1.0,
                    "count": 1.0,
                }
            }
        }

        with patch("catalog.store.database.get_session"):
            with patch("catalog.store.session_context.use_session"):
                with patch("catalog.search.service_v2.SearchServiceV2"):
                    with patch(
                        "catalog.eval.golden.evaluate_golden_queries",
                        return_value=mock_results,
                    ):
                        runner = CliRunner()
                        result = runner.invoke(
                            eval_app,
                            [
                                "golden",
                                "--queries-file",
                                str(golden_file),
                                "--output",
                                "json",
                            ],
                        )
                        assert result.exit_code == 0
                        # Should contain JSON output
                        assert "hit_at_1" in result.stdout

    def test_golden_table_output(self, tmp_path: Path) -> None:
        """golden command outputs table format."""
        golden_file = tmp_path / "golden.json"
        golden_file.write_text(
            json.dumps(
                [
                    {
                        "query": "test query",
                        "expected_docs": ["doc.md"],
                        "difficulty": "easy",
                        "retriever_types": ["bm25"],
                    }
                ]
            )
        )

        mock_results = {
            "bm25": {
                "easy": {
                    "hit_at_1": 0.8,
                    "hit_at_3": 0.9,
                    "hit_at_5": 0.95,
                    "hit_at_10": 1.0,
                    "count": 1.0,
                }
            }
        }

        with patch("catalog.store.database.get_session"):
            with patch("catalog.store.session_context.use_session"):
                with patch("catalog.search.service_v2.SearchServiceV2"):
                    with patch(
                        "catalog.eval.golden.evaluate_golden_queries",
                        return_value=mock_results,
                    ):
                        runner = CliRunner()
                        result = runner.invoke(
                            eval_app,
                            [
                                "golden",
                                "--queries-file",
                                str(golden_file),
                                "--output",
                                "table",
                            ],
                        )
                        assert result.exit_code == 0
                        # Should contain table format
                        assert "BM25" in result.stdout
                        assert "easy" in result.stdout


class TestCompareCommand:
    """Tests for compare command."""

    def test_compare_requires_query(self) -> None:
        """compare command requires query argument."""
        runner = CliRunner()
        result = runner.invoke(eval_app, ["compare"])
        assert result.exit_code != 0
        # Missing argument

    def test_compare_executes_comparison(self) -> None:
        """compare command executes comparison."""
        mock_result = MagicMock()
        mock_result.query = "test query"
        mock_result.v1_time_ms = 10.0
        mock_result.v2_time_ms = 15.0
        mock_result.overlap_at_5 = 0.8
        mock_result.overlap_at_10 = 0.9
        mock_result.rank_correlation = 0.75
        mock_result.v1_results = []
        mock_result.v2_results = []

        with patch("catalog.store.database.get_session"):
            with patch("catalog.store.session_context.use_session"):
                with patch("catalog.search.comparison.SearchComparison") as mock_comparison:
                    mock_comparison.return_value.compare.return_value = mock_result

                    runner = CliRunner()
                    result = runner.invoke(eval_app, ["compare", "test query"])
                    assert result.exit_code == 0
                    assert "test query" in result.stdout
                    assert "V1 time" in result.stdout
                    assert "V2 time" in result.stdout


class TestCompareBatchCommand:
    """Tests for compare-batch command."""

    def test_compare_batch_file_not_found_exits_with_error(self) -> None:
        """compare-batch exits with error when file not found."""
        runner = CliRunner()
        result = runner.invoke(
            eval_app, ["compare-batch", "/nonexistent/queries.txt"]
        )
        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_compare_batch_empty_file_exits_with_error(self, tmp_path: Path) -> None:
        """compare-batch exits with error when file is empty."""
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("")

        runner = CliRunner()
        result = runner.invoke(eval_app, ["compare-batch", str(empty_file)])
        assert result.exit_code == 1
        assert "no queries" in result.stdout.lower()

    def test_compare_batch_summary_output(self, tmp_path: Path) -> None:
        """compare-batch outputs summary report."""
        queries_file = tmp_path / "queries.txt"
        queries_file.write_text("query 1\nquery 2\n")

        mock_summary = {
            "count": 2,
            "v1_mean_time_ms": 10.0,
            "v2_mean_time_ms": 15.0,
            "mean_overlap_at_5": 0.8,
            "mean_overlap_at_10": 0.9,
            "mean_rank_correlation": 0.75,
            "queries_with_no_overlap": 0,
        }

        with patch("catalog.store.database.get_session"):
            with patch("catalog.store.session_context.use_session"):
                with patch("catalog.search.comparison.SearchComparison") as mock_comparison:
                    mock_comparison.return_value.compare_batch.return_value = []
                    mock_comparison.return_value.summary_report.return_value = mock_summary

                    runner = CliRunner()
                    result = runner.invoke(
                        eval_app,
                        [
                            "compare-batch",
                            str(queries_file),
                            "--output",
                            "summary",
                        ],
                    )
                    assert result.exit_code == 0
                    assert "count" in result.stdout


class TestLoadQueries:
    """Tests for _load_queries helper function."""

    def test_load_queries_plain_text(self, tmp_path: Path) -> None:
        """_load_queries loads plain text file with one query per line."""
        queries_file = tmp_path / "queries.txt"
        queries_file.write_text("query 1\nquery 2\nquery 3\n")

        queries = _load_queries(str(queries_file))
        assert queries == ["query 1", "query 2", "query 3"]

    def test_load_queries_json_array(self, tmp_path: Path) -> None:
        """_load_queries loads JSON array file."""
        queries_file = tmp_path / "queries.json"
        queries_file.write_text('["query 1", "query 2", "query 3"]')

        queries = _load_queries(str(queries_file))
        assert queries == ["query 1", "query 2", "query 3"]

    def test_load_queries_skips_empty_lines(self, tmp_path: Path) -> None:
        """_load_queries skips empty lines."""
        queries_file = tmp_path / "queries.txt"
        queries_file.write_text("query 1\n\nquery 2\n  \nquery 3\n")

        queries = _load_queries(str(queries_file))
        assert queries == ["query 1", "query 2", "query 3"]

    def test_load_queries_file_not_found(self) -> None:
        """_load_queries raises typer.Exit when file not found."""
        import click.exceptions

        with pytest.raises(click.exceptions.Exit):
            _load_queries("/nonexistent/file.txt")


class TestCheckAgainstThresholds:
    """Tests for _check_against_thresholds helper function."""

    def test_passes_when_above_threshold(self) -> None:
        """_check_against_thresholds returns empty list when passing."""
        results = {
            "bm25": {"easy": {"hit_at_3": 0.90}},
        }
        thresholds = {
            "bm25": {"easy": {"hit_at_3": 0.80}},
        }

        failures = _check_against_thresholds(results, thresholds)
        assert failures == []

    def test_fails_when_below_threshold(self) -> None:
        """_check_against_thresholds returns failures when below threshold."""
        results = {
            "bm25": {"easy": {"hit_at_3": 0.70}},
        }
        thresholds = {
            "bm25": {"easy": {"hit_at_3": 0.80}},
        }

        failures = _check_against_thresholds(results, thresholds)
        assert len(failures) == 1
        assert "bm25/easy/hit_at_3" in failures[0]

    def test_handles_missing_retriever(self) -> None:
        """_check_against_thresholds handles missing retriever types."""
        results = {
            "bm25": {"easy": {"hit_at_3": 0.90}},
        }
        thresholds = {
            "bm25": {"easy": {"hit_at_3": 0.80}},
            "vector": {"easy": {"hit_at_3": 0.60}},  # Not in results
        }

        failures = _check_against_thresholds(results, thresholds)
        assert failures == []

    def test_handles_missing_difficulty(self) -> None:
        """_check_against_thresholds handles missing difficulty levels."""
        results = {
            "bm25": {"easy": {"hit_at_3": 0.90}},
        }
        thresholds = {
            "bm25": {
                "easy": {"hit_at_3": 0.80},
                "hard": {"hit_at_3": 0.40},  # Not in results
            },
        }

        failures = _check_against_thresholds(results, thresholds)
        assert failures == []


class TestPrintTable:
    """Tests for _print_table helper function."""

    def test_print_table_outputs_header(self, capsys) -> None:
        """_print_table outputs table header."""
        results = {
            "bm25": {
                "easy": {
                    "hit_at_1": 0.8,
                    "hit_at_3": 0.9,
                    "hit_at_5": 0.95,
                    "hit_at_10": 1.0,
                    "count": 1.0,
                }
            }
        }

        _print_table(results)
        captured = capsys.readouterr()
        assert "Evaluation Results" in captured.out
        assert "BM25" in captured.out
        assert "easy" in captured.out

    def test_print_table_formats_percentages(self, capsys) -> None:
        """_print_table formats numbers as percentages."""
        results = {
            "hybrid": {
                "medium": {
                    "hit_at_1": 0.5,
                    "hit_at_3": 0.75,
                    "hit_at_5": 0.85,
                    "hit_at_10": 0.95,
                    "count": 10.0,
                }
            }
        }

        _print_table(results)
        captured = capsys.readouterr()
        # Should show percentages
        assert "%" in captured.out
