"""Tests for structured logging utilities."""

from __future__ import annotations

import io
import json
import logging

from ontologizer.utils.logging import configure_json_logging


def test_configure_json_logging_outputs_json() -> None:
    stream = io.StringIO()
    configure_json_logging(level="INFO", stream=stream)

    root_logger = logging.getLogger()

    logger = logging.getLogger("ontology.tests")
    logger.info("structured logging ready", extra={"component": "test"})

    contents = stream.getvalue().strip()
    assert contents, "Expected log output"

    payload = json.loads(contents)
    assert payload["message"] == "structured logging ready"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "ontology.tests"
    assert payload["component"] == "test"
    assert "timestamp" in payload

    root_logger.handlers.clear()
