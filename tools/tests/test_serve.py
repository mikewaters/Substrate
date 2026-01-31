"""Unit tests for serve tool."""

from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

# Import the main function from the tools.serve module
import sys
from pathlib import Path

# Add tools directory to path so we can import serve
tools_dir = Path(__file__).parent.parent
sys.path.insert(0, str(tools_dir))

from serve import main

# Create a Typer app for testing
app = typer.Typer()
app.command()(main)

runner = CliRunner()


class TestServeStart:
    """Tests for the serve start command."""

    @patch("serve.uvicorn.run")
    def test_start_with_defaults(self, mock_uvicorn_run: MagicMock) -> None:
        """Test start command with default parameters."""
        result = runner.invoke(app, [])

        assert result.exit_code == 0
        mock_uvicorn_run.assert_called_once_with(
            "ontology.api.app:app",
            host="127.0.0.1",
            port=8000,
            reload=True,
            log_level="info",
            access_log=True,
        )

    @patch("serve.uvicorn.run")
    def test_start_with_custom_host(self, mock_uvicorn_run: MagicMock) -> None:
        """Test start command with custom host."""
        result = runner.invoke(app, ["--host", "0.0.0.0"])

        assert result.exit_code == 0
        mock_uvicorn_run.assert_called_once_with(
            "ontology.api.app:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info",
            access_log=True,
        )

    @patch("serve.uvicorn.run")
    def test_start_with_custom_port(self, mock_uvicorn_run: MagicMock) -> None:
        """Test start command with custom port."""
        result = runner.invoke(app, ["--port", "8080"])

        assert result.exit_code == 0
        mock_uvicorn_run.assert_called_once_with(
            "ontology.api.app:app",
            host="127.0.0.1",
            port=8080,
            reload=True,
            log_level="info",
            access_log=True,
        )

    @patch("serve.uvicorn.run")
    def test_start_with_short_flags(self, mock_uvicorn_run: MagicMock) -> None:
        """Test start command with short flags."""
        result = runner.invoke(app, ["-h", "0.0.0.0", "-p", "8080"])

        assert result.exit_code == 0
        mock_uvicorn_run.assert_called_once_with(
            "ontology.api.app:app",
            host="0.0.0.0",
            port=8080,
            reload=True,
            log_level="info",
            access_log=True,
        )

    @patch("serve.uvicorn.run")
    def test_start_with_reload_disabled(self, mock_uvicorn_run: MagicMock) -> None:
        """Test start command with reload disabled."""
        result = runner.invoke(app, ["--no-reload"])

        assert result.exit_code == 0
        mock_uvicorn_run.assert_called_once_with(
            "ontology.api.app:app",
            host="127.0.0.1",
            port=8000,
            reload=False,
            log_level="info",
            access_log=True,
        )

    @patch("serve.uvicorn.run")
    def test_start_with_custom_log_level(self, mock_uvicorn_run: MagicMock) -> None:
        """Test start command with custom log level."""
        result = runner.invoke(app, ["--log-level", "debug"])

        assert result.exit_code == 0
        mock_uvicorn_run.assert_called_once_with(
            "ontology.api.app:app",
            host="127.0.0.1",
            port=8000,
            reload=True,
            log_level="debug",
            access_log=True,
        )

    @patch("serve.uvicorn.run")
    def test_start_with_all_options(self, mock_uvicorn_run: MagicMock) -> None:
        """Test start command with all options specified."""
        result = runner.invoke(
            app,
            [
                "--host",
                "0.0.0.0",
                "--port",
                "8080",
                "--no-reload",
                "--log-level",
                "warning",
            ],
        )

        assert result.exit_code == 0
        mock_uvicorn_run.assert_called_once_with(
            "ontology.api.app:app",
            host="0.0.0.0",
            port=8080,
            reload=False,
            log_level="warning",
            access_log=True,
        )

    @patch("serve.uvicorn.run")
    def test_start_output_messages(self, mock_uvicorn_run: MagicMock) -> None:
        """Test that start command outputs expected messages."""
        result = runner.invoke(app, ["--host", "0.0.0.0", "--port", "8080"])

        assert "Starting FastAPI server at http://0.0.0.0:8080" in result.stdout
        assert "Auto-reload: enabled" in result.stdout
        assert "Log level: info" in result.stdout
        assert "Press CTRL+C to quit" in result.stdout

    @patch("serve.uvicorn.run")
    def test_start_handles_keyboard_interrupt(
        self, mock_uvicorn_run: MagicMock
    ) -> None:
        """Test that KeyboardInterrupt is handled gracefully."""
        mock_uvicorn_run.side_effect = KeyboardInterrupt()

        result = runner.invoke(app, [])

        assert result.exit_code == 0
        assert "Shutting down server..." in result.stdout

    @patch("serve.uvicorn.run")
    def test_start_handles_exception(self, mock_uvicorn_run: MagicMock) -> None:
        """Test that exceptions are handled and reported."""
        mock_uvicorn_run.side_effect = Exception("Test error")

        result = runner.invoke(app, [])

        # Should exit with error code when exception occurs
        assert result.exit_code == 1

    @patch("serve.uvicorn.run")
    def test_log_level_case_insensitive(self, mock_uvicorn_run: MagicMock) -> None:
        """Test that log level is case insensitive."""
        result = runner.invoke(app, ["--log-level", "DEBUG"])

        assert result.exit_code == 0
        mock_uvicorn_run.assert_called_once_with(
            "ontology.api.app:app",
            host="127.0.0.1",
            port=8000,
            reload=True,
            log_level="debug",
            access_log=True,
        )
