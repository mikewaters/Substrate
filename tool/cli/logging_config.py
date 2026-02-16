"""Logging configuration helpers for CLI entrypoints."""

from __future__ import annotations

from typing import Final

from agentlayer.logging import configure_logging

VALID_LOG_LEVELS: Final[set[str]] = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
DEFAULT_USER_LOG_LEVEL: Final[str] = "CRITICAL"
DEFAULT_ADMIN_LOG_LEVEL: Final[str] = "INFO"


def normalize_log_level(value: str) -> str:
    """Normalize and validate a log level string."""
    normalized = value.upper()
    if normalized not in VALID_LOG_LEVELS:
        accepted = ", ".join(sorted(VALID_LOG_LEVELS))
        msg = f"invalid log level '{value}'. Accepted values: {accepted}"
        raise ValueError(msg)
    return normalized


def configure_cli_logging(level: str) -> None:
    """Configure CLI logging using the shared project logger setup."""
    configure_logging(level=normalize_log_level(level))
