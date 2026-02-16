"""Tests for catalog.cli.eval module."""

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from catalog.cli import app
from catalog.cli.eval import (
    _check_against_thresholds,
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

    def test_golden_command_exists(self) -> None:
        """golden command exists in eval app."""
        runner = CliRunner()
        result = runner.invoke(eval_app, ["--help"])
        assert result.exit_code == 0
        assert "golden queries" in result.stdout.lower()


class TestGoldenCommand:
    """Tests for golden command."""

    def test_golden_uses_default_queries_path_when_option_omitted(self) -> None:
        """golden command uses package-relative default path when --queries-file is omitted."""
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
                with patch("catalog.search.service.SearchService"):
                    with patch(
                        "catalog.eval.golden.evaluate_golden_queries",
                        return_value=mock_results,
                    ):
                        with patch(
                            "catalog.eval.golden.load_golden_queries",
                            return_value=[],
                        ) as load_mock:
                            runner = CliRunner()
                            result = runner.invoke(
                                eval_app,
                                ["--output", "json"],
                            )
                            assert result.exit_code == 0, result.output
                            assert "hit_at_1" in result.output
                            load_mock.assert_called_once()
                            (call_path,) = load_mock.call_args[0]
                            assert "rag_v2" in call_path
                            assert call_path.endswith("golden_queries.json")

    def test_golden_file_not_found_exits_with_error(self) -> None:
        """golden command exits with error when file not found."""
        runner = CliRunner()
        result = runner.invoke(
            eval_app, ["--queries-file", "/nonexistent/file.json"]
        )
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_golden_invalid_json_exits_with_error(self, tmp_path: Path) -> None:
        """golden command exits with error on invalid JSON."""
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("{ not valid json")

        runner = CliRunner()
        result = runner.invoke(
            eval_app, ["--queries-file", str(invalid_file)]
        )
        assert result.exit_code == 1
        assert "invalid" in result.output.lower() or "error" in result.output.lower()

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
                with patch("catalog.search.service.SearchService"):
                    with patch(
                        "catalog.eval.golden.evaluate_golden_queries",
                        return_value=mock_results,
                    ):
                        runner = CliRunner()
                        result = runner.invoke(
                            eval_app,
                            [
                                "--queries-file",
                                str(golden_file),
                                "--output",
                                "json",
                            ],
                        )
                        assert result.exit_code == 0
                        # Should contain JSON output
                        assert "hit_at_1" in result.output

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
                with patch("catalog.search.service.SearchService"):
                    with patch(
                        "catalog.eval.golden.evaluate_golden_queries",
                        return_value=mock_results,
                    ):
                        runner = CliRunner()
                        result = runner.invoke(
                            eval_app,
                            [
                                "--queries-file",
                                str(golden_file),
                                "--output",
                                "table",
                            ],
                        )
                        assert result.exit_code == 0
                        # Should contain table format
                        assert "BM25" in result.output
                        assert "easy" in result.output


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
