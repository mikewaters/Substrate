"""Unit tests for the `substrate-admin` operator CLI entrypoint."""

from __future__ import annotations

import inspect

from typer.testing import CliRunner

from tool.cli import operator


runner = CliRunner()


def test_operator_help_exposes_eval_and_search_groups() -> None:
    """Root help should include delegated eval and search groups."""
    result = runner.invoke(operator.app, ["--help"])

    assert result.exit_code == 0
    assert "eval" in result.stdout
    assert "search" in result.stdout


def test_operator_eval_golden_help_is_delegated() -> None:
    """Delegated `eval golden` help should be available from substrate-admin."""
    result = runner.invoke(operator.app, ["eval", "golden", "--help"])

    assert result.exit_code == 0
    assert "--queries-file" in result.stdout
    assert "--output" in result.stdout


def test_operator_help_includes_global_log_level_option() -> None:
    """Root help should include the global log-level option."""
    result = runner.invoke(operator.app, ["--help"])

    assert result.exit_code == 0
    assert "--log-level" in result.stdout
    assert "--debug-level" in result.stdout


def test_operator_main_normalizes_missing_queries_file_to_exit_code_five() -> None:
    """Delegated execution failures should normalize to exit code 5."""
    exit_code = operator.main(
        [
            "eval",
            "golden",
            "--queries-file",
            "/tmp/__substrate_missing_golden_queries__.json",
        ]
    )

    assert exit_code == 5


def test_operator_default_log_level_is_info() -> None:
    """Global operator log-level default should be INFO."""
    parameter = inspect.signature(operator._global_options).parameters["log_level"]
    assert parameter.default == "INFO"
