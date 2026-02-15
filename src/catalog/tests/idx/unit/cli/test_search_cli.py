"""Tests for catalog.cli.search module."""

import contextlib
import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from catalog.cli import app
from catalog.cli.search import _print_methods_table, search_app
from catalog.search.models import SearchResult, SearchResults, SnippetResult


class TestSearchAppStructure:
    """Tests for search CLI app structure."""

    def test_search_app_registered_on_main_app(self) -> None:
        """search subcommand is registered on main app."""
        runner = CliRunner()
        result = runner.invoke(app, ["search", "--help"])
        assert result.exit_code == 0
        assert "methods" in result.stdout

    def test_methods_command_exists(self) -> None:
        """methods command exists in search app."""
        runner = CliRunner()
        result = runner.invoke(search_app, ["--help"])
        assert result.exit_code == 0
        assert "documented search methods" in result.stdout.lower()


class TestMethodsCommand:
    """Tests for methods command."""

    def _build_mock_result(self, query: str, mode: str, score: float) -> SearchResults:
        return SearchResults(
            query=query,
            mode=mode,
            total_candidates=1,
            timing_ms=12.3,
            results=[
                SearchResult(
                    path=f"{mode}/doc.md",
                    dataset_name="test-dataset",
                    score=score,
                    snippet=SnippetResult(text="chunk", start_line=1, end_line=1, header="@@ -1,1 +1,1 @@ test"),
                    chunk_seq=0,
                    chunk_pos=0,
                    metadata={},
                    scores={mode: score},
                )
            ],
        )

    def test_methods_invalid_output_exits_with_error(self) -> None:
        """methods exits with error on invalid output format."""
        runner = CliRunner()
        result = runner.invoke(search_app, ["python", "--output", "xml"])
        assert result.exit_code == 1
        assert "invalid output format" in result.output.lower()

    def test_methods_json_output(self) -> None:
        """methods command outputs JSON for all documented methods."""
        query = "python async"
        mock_service = MagicMock()
        mock_service.search.side_effect = [
            self._build_mock_result(query, "fts", 0.91),
            self._build_mock_result(query, "vector", 0.82),
            self._build_mock_result(query, "hybrid", 0.88),
            self._build_mock_result(query, "hybrid", 0.93),
        ]

        with patch(
            "catalog.store.database.get_session",
            return_value=contextlib.nullcontext(object()),
        ):
            with patch(
                "catalog.store.session_context.use_session",
                return_value=contextlib.nullcontext(),
            ):
                with patch("catalog.search.service.SearchService", return_value=mock_service):
                    runner = CliRunner()
                    result = runner.invoke(
                        search_app,
                        [query, "--output", "json"],
                    )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["query"] == query
        assert set(payload["methods"].keys()) == {
            "fts",
            "vector",
            "hybrid",
            "hybrid_rerank",
        }
        assert mock_service.search.call_count == 4

    def test_methods_table_output(self) -> None:
        """methods command outputs table format."""
        query = "python async"
        mock_service = MagicMock()
        mock_service.search.side_effect = [
            self._build_mock_result(query, "fts", 0.91),
            self._build_mock_result(query, "vector", 0.82),
            self._build_mock_result(query, "hybrid", 0.88),
            self._build_mock_result(query, "hybrid", 0.93),
        ]

        with patch(
            "catalog.store.database.get_session",
            return_value=contextlib.nullcontext(object()),
        ):
            with patch(
                "catalog.store.session_context.use_session",
                return_value=contextlib.nullcontext(),
            ):
                with patch("catalog.search.service.SearchService", return_value=mock_service):
                    runner = CliRunner()
                    result = runner.invoke(
                        search_app,
                        [query, "--output", "table"],
                    )

        assert result.exit_code == 0
        assert "Search Method Comparison" in result.output
        assert "hybrid_rerank" in result.output


class TestPrintMethodsTable:
    """Tests for _print_methods_table helper."""

    def test_print_methods_table_outputs_sections(self, capsys) -> None:
        """_print_methods_table outputs summary and top results sections."""
        results = {
            "query": "python",
            "dataset": "obsidian",
            "methods": {
                "fts": {
                    "mode": "fts",
                    "rerank": False,
                    "timing_ms": 10.0,
                    "results": [
                        {
                            "path": "a.md",
                            "dataset_name": "obsidian",
                            "score": 0.9,
                        }
                    ],
                }
            },
        }

        _print_methods_table(results)
        captured = capsys.readouterr()
        assert "Search Method Comparison" in captured.out
        assert "Top results by method" in captured.out
        assert "FTS" in captured.out
