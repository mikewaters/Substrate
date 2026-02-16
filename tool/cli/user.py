"""Agent-first `substrate` command entrypoint."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from tool.cli.help_contract import (
    build_substrate_root_payload,
    payload_to_json,
    render_text,
)
from tool.cli.logging_config import (
    DEFAULT_USER_LOG_LEVEL,
    configure_cli_logging,
    normalize_log_level,
)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the `substrate` CLI.

    In v0 this command exposes only contract help surfaces:
    - `--help` (default when no args are provided)
    - `--help-json`
    """
    args = list(sys.argv[1:] if argv is None else argv)
    payload = build_substrate_root_payload()

    try:
        parsed_log_level, remaining = _extract_log_level_arg(args)
        configure_cli_logging(parsed_log_level)

        if not remaining or remaining in (["--help"], ["-h"]):
            print(render_text(payload))
            return 0

        if remaining == ["--help-json"]:
            print(payload_to_json(payload))
            return 0

        unsupported = " ".join(remaining)
        print(
            f"Error: unsupported arguments for substrate v0: {unsupported}",
            file=sys.stderr,
        )
        print(
            "Run `substrate --help` for supported usage or "
            "`substrate-admin --help` for operational commands.",
            file=sys.stderr,
        )
        return 2
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


def _extract_log_level_arg(args: list[str]) -> tuple[str, list[str]]:
    """Extract global log-level option and return remaining args."""
    level = DEFAULT_USER_LOG_LEVEL
    remaining: list[str] = []
    i = 0
    while i < len(args):
        token = args[i]
        if token in {"--log-level", "--debug-level"}:
            if i + 1 >= len(args):
                raise ValueError(f"{token} requires a value")
            level = normalize_log_level(args[i + 1])
            i += 2
            continue
        if token.startswith("--log-level="):
            level = normalize_log_level(token.split("=", 1)[1])
            i += 1
            continue
        if token.startswith("--debug-level="):
            level = normalize_log_level(token.split("=", 1)[1])
            i += 1
            continue
        remaining.append(token)
        i += 1
    return level, remaining


if __name__ == "__main__":
    raise SystemExit(main())
