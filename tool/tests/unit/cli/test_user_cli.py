"""Unit tests for the `substrate` user CLI entrypoint."""

from __future__ import annotations

import json

from tool.cli import user


REQUIRED_HELP_SECTIONS = [
    "NAME",
    "SUMMARY",
    "WHEN TO USE",
    "WHEN NOT TO USE",
    "SAFETY",
    "PRECONDITIONS",
    "USAGE",
    "ARGUMENTS",
    "OPTIONS",
    "OUTPUT",
    "EXIT CODES",
    "EXAMPLES",
    "SEE ALSO",
]

REQUIRED_HELP_JSON_KEYS = {
    "name",
    "summary",
    "when_to_use",
    "when_not_to_use",
    "safety",
    "preconditions",
    "usage",
    "arguments",
    "options",
    "output",
    "exit_codes",
    "examples",
    "see_also",
}


def test_substrate_help_sections_follow_required_order(capsys) -> None:
    """`substrate --help` should print all sections in stable order."""
    exit_code = user.main(["--help"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""

    section_positions = [captured.out.index(f"{section}\n") for section in REQUIRED_HELP_SECTIONS]
    assert section_positions == sorted(section_positions)


def test_substrate_help_json_contains_required_contract_fields(capsys) -> None:
    """`substrate --help-json` should include required contract keys."""
    exit_code = user.main(["--help-json"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""

    payload = json.loads(captured.out)
    assert REQUIRED_HELP_JSON_KEYS.issubset(payload.keys())
    assert payload["safety"]["side_effect_class"] == "read-only"


def test_substrate_help_shows_log_level_option(capsys) -> None:
    """`substrate --help` should expose global log-level option."""
    exit_code = user.main(["--help"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "--log-level, --debug-level" in captured.out


def test_substrate_rejects_operational_arguments_in_v0(capsys) -> None:
    """Operational commands should fail on `substrate` in v0."""
    exit_code = user.main(["search", "methods"])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "unsupported arguments for substrate v0" in captured.err


def test_substrate_rejects_invalid_log_level(capsys) -> None:
    """Invalid log levels should return usage error."""
    exit_code = user.main(["--log-level", "LOUD", "--help"])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "invalid log level" in captured.err


def test_substrate_defaults_to_critical_logging(monkeypatch, capsys) -> None:
    """Default substrate log level should be CRITICAL (quiet by default)."""
    configured_levels: list[str] = []

    def _fake_configure(level: str) -> None:
        configured_levels.append(level)

    monkeypatch.setattr(user, "configure_cli_logging", _fake_configure)
    exit_code = user.main(["--help"])
    _ = capsys.readouterr()

    assert exit_code == 0
    assert configured_levels == ["CRITICAL"]
