"""Utilities for configuring structured JSON logging."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, UTC
from typing import IO

DEFAULT_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


class JsonFormatter(logging.Formatter):
    """Format log records as JSON."""

    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=UTC
            ).strftime(DEFAULT_TIME_FORMAT),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            data["exc_info"] = self.formatException(record.exc_info)

        extra = {
            key: value
            for key, value in record.__dict__.items()
            if key not in logging.LogRecord.__dict__
            and key
            not in {
                "args",
                "asctime",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "thread",
                "threadName",
            }
        }
        if extra:
            data.update(extra)

        return json.dumps(data, ensure_ascii=False)


def configure_json_logging(
    *,
    level: str = "INFO",
    stream: IO[str] | None = None,
) -> None:
    """Configure root logger to emit JSON formatted logs.

    Args:
        level: Logging level name (e.g., "INFO", "DEBUG").
        stream: Optional stream handler target (defaults to stderr).
    """
    stream = stream or sys.stderr

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicate logs.
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(stream)
    handler.setLevel(root_logger.level)
    handler.setFormatter(JsonFormatter())

    root_logger.addHandler(handler)
