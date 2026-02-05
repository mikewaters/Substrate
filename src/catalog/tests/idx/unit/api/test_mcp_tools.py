"""Tests for catalog.api.mcp.tools module."""

from unittest.mock import MagicMock, patch

import pytest
from llama_index.core.tools import FunctionTool

from catalog.api.mcp.tools import create_mcp_tools
from catalog.search.models import SearchCriteria, SearchResult, SearchResults
from catalog.search.service_v2 import SearchServiceV2


class TestCreateMcpTools:
    """Tests for create_mcp_tools factory function."""

    @pytest.fixture
    def mock_service(self) -> SearchServiceV2:
        """Create mock SearchServiceV2."""
        mock_session = MagicMock()
        service = SearchServiceV2(mock_session)
        return service

    def test_creates_six_tools(self, mock_service: SearchServiceV2) -> None:
        """create_mcp_tools returns six tools."""
        tools = create_mcp_tools(mock_service)
        assert len(tools) == 6

    def test_all_tools_are_function_tools(self, mock_service: SearchServiceV2) -> None:
        """All returned tools are FunctionTool instances."""
        tools = create_mcp_tools(mock_service)
        for tool in tools:
            assert isinstance(tool, FunctionTool)

    def test_tool_names(self, mock_service: SearchServiceV2) -> None:
        """Tools have expected names."""
        tools = create_mcp_tools(mock_service)
        names = {t.metadata.name for t in tools}

        expected = {
            "catalog_search",
            "catalog_vsearch",
            "catalog_query",
            "catalog_get",
            "catalog_multi_get",
            "catalog_status",
        }
        assert names == expected

    def test_tools_have_descriptions(self, mock_service: SearchServiceV2) -> None:
        """All tools have descriptions."""
        tools = create_mcp_tools(mock_service)
        for tool in tools:
            assert tool.metadata.description
            assert len(tool.metadata.description) > 10


class TestCatalogSearchTool:
    """Tests for catalog_search tool."""

    @pytest.fixture
    def mock_service(self) -> SearchServiceV2:
        """Create mock SearchServiceV2 with stubbed search."""
        mock_session = MagicMock()
        service = SearchServiceV2(mock_session)
        return service

    def test_catalog_search_calls_service(self, mock_service: SearchServiceV2) -> None:
        """catalog_search calls service.search with fts mode."""
        mock_results = SearchResults(
            results=[
                SearchResult(
                    path="test.md",
                    dataset_name="vault",
                    score=1.0,
                    chunk_text="test content",
                    scores={"retrieval": 1.0},
                )
            ],
            query="test query",
            mode="fts",
            total_candidates=1,
            timing_ms=10.0,
        )

        with patch.object(mock_service, "search", return_value=mock_results):
            tools = create_mcp_tools(mock_service)
            tool_map = {t.metadata.name: t for t in tools}
            search_tool = tool_map["catalog_search"]

            tool_output = search_tool.call(query="test query", limit=10)
            result = tool_output.raw_output

            assert result["mode"] == "fts"
            assert result["query"] == "test query"
            assert len(result["results"]) == 1

    def test_catalog_search_clamps_limit(self, mock_service: SearchServiceV2) -> None:
        """catalog_search clamps limit to 1-100 range."""
        mock_results = SearchResults(
            results=[],
            query="test",
            mode="fts",
            total_candidates=0,
            timing_ms=0,
        )

        with patch.object(mock_service, "search", return_value=mock_results) as mock_search:
            tools = create_mcp_tools(mock_service)
            tool_map = {t.metadata.name: t for t in tools}
            search_tool = tool_map["catalog_search"]

            # Test limit > 100
            search_tool.call(query="test", limit=500)
            call_args = mock_search.call_args[0][0]
            assert call_args.limit == 100

            # Test limit < 1
            search_tool.call(query="test", limit=0)
            call_args = mock_search.call_args[0][0]
            assert call_args.limit == 1

    def test_catalog_search_handles_error(self, mock_service: SearchServiceV2) -> None:
        """catalog_search returns error dict on exception."""
        with patch.object(mock_service, "search", side_effect=Exception("DB error")):
            tools = create_mcp_tools(mock_service)
            tool_map = {t.metadata.name: t for t in tools}
            search_tool = tool_map["catalog_search"]

            tool_output = search_tool.call(query="test")
            result = tool_output.raw_output

            assert "error" in result
            assert result["results"] == []


class TestCatalogVsearchTool:
    """Tests for catalog_vsearch tool."""

    @pytest.fixture
    def mock_service(self) -> SearchServiceV2:
        """Create mock SearchServiceV2."""
        mock_session = MagicMock()
        return SearchServiceV2(mock_session)

    def test_catalog_vsearch_uses_vector_mode(self, mock_service: SearchServiceV2) -> None:
        """catalog_vsearch calls service.search with vector mode."""
        mock_results = SearchResults(
            results=[],
            query="semantic query",
            mode="vector",
            total_candidates=0,
            timing_ms=5.0,
        )

        with patch.object(mock_service, "search", return_value=mock_results) as mock_search:
            tools = create_mcp_tools(mock_service)
            tool_map = {t.metadata.name: t for t in tools}
            vsearch_tool = tool_map["catalog_vsearch"]

            tool_output = vsearch_tool.call(query="semantic query")
            result = tool_output.raw_output

            call_args = mock_search.call_args[0][0]
            assert call_args.mode == "vector"
            assert result["mode"] == "vector"


class TestCatalogQueryTool:
    """Tests for catalog_query tool."""

    @pytest.fixture
    def mock_service(self) -> SearchServiceV2:
        """Create mock SearchServiceV2."""
        mock_session = MagicMock()
        return SearchServiceV2(mock_session)

    def test_catalog_query_uses_hybrid_mode(self, mock_service: SearchServiceV2) -> None:
        """catalog_query calls service.search with hybrid mode."""
        mock_results = SearchResults(
            results=[],
            query="hybrid query",
            mode="hybrid",
            total_candidates=0,
            timing_ms=15.0,
        )

        with patch.object(mock_service, "search", return_value=mock_results) as mock_search:
            tools = create_mcp_tools(mock_service)
            tool_map = {t.metadata.name: t for t in tools}
            query_tool = tool_map["catalog_query"]

            tool_output = query_tool.call(query="hybrid query", rerank=True)
            result = tool_output.raw_output

            call_args = mock_search.call_args[0][0]
            assert call_args.mode == "hybrid"
            assert call_args.rerank is True
            assert result["mode"] == "hybrid"
            assert result["reranked"] is True

    def test_catalog_query_rerank_false(self, mock_service: SearchServiceV2) -> None:
        """catalog_query respects rerank=False."""
        mock_results = SearchResults(
            results=[],
            query="test",
            mode="hybrid",
            total_candidates=0,
            timing_ms=10.0,
        )

        with patch.object(mock_service, "search", return_value=mock_results) as mock_search:
            tools = create_mcp_tools(mock_service)
            tool_map = {t.metadata.name: t for t in tools}
            query_tool = tool_map["catalog_query"]

            tool_output = query_tool.call(query="test", rerank=False)
            result = tool_output.raw_output

            call_args = mock_search.call_args[0][0]
            assert call_args.rerank is False
            assert result["reranked"] is False


class TestCatalogGetTool:
    """Tests for catalog_get tool."""

    @pytest.fixture
    def mock_service(self) -> SearchServiceV2:
        """Create mock SearchServiceV2."""
        mock_session = MagicMock()
        return SearchServiceV2(mock_session)

    def test_catalog_get_with_dataset_prefix(self, mock_service: SearchServiceV2) -> None:
        """catalog_get parses dataset:path format."""
        mock_doc = MagicMock()
        mock_doc.path = "notes/todo.md"
        mock_doc.body = "# Todo\n- Task 1"
        mock_doc.title = "Todo"
        mock_doc.metadata = {"tags": ["task"]}

        mock_dataset = MagicMock()
        mock_dataset.id = 1

        with patch("catalog.api.mcp.tools.DatasetService") as mock_ds_cls:
            mock_ds = MagicMock()
            mock_ds.get_dataset_by_name.return_value = mock_dataset
            mock_ds.get_document_by_path.return_value = mock_doc
            mock_ds_cls.return_value = mock_ds

            tools = create_mcp_tools(mock_service)
            tool_map = {t.metadata.name: t for t in tools}
            get_tool = tool_map["catalog_get"]

            tool_output = get_tool.call(path_or_docid="vault:notes/todo.md")
            result = tool_output.raw_output

            assert result["path"] == "notes/todo.md"
            assert result["dataset_name"] == "vault"
            assert "# Todo" in result["body"]

    def test_catalog_get_not_found(self, mock_service: SearchServiceV2) -> None:
        """catalog_get returns error for missing document."""
        with patch("catalog.api.mcp.tools.DatasetService") as mock_ds_cls:
            mock_ds = MagicMock()
            mock_ds.list_datasets.return_value = []
            mock_ds_cls.return_value = mock_ds

            tools = create_mcp_tools(mock_service)
            tool_map = {t.metadata.name: t for t in tools}
            get_tool = tool_map["catalog_get"]

            tool_output = get_tool.call(path_or_docid="nonexistent.md")
            result = tool_output.raw_output

            assert "error" in result


class TestCatalogMultiGetTool:
    """Tests for catalog_multi_get tool."""

    @pytest.fixture
    def mock_service(self) -> SearchServiceV2:
        """Create mock SearchServiceV2."""
        mock_session = MagicMock()
        return SearchServiceV2(mock_session)

    def test_catalog_multi_get_requires_dataset_prefix(
        self, mock_service: SearchServiceV2
    ) -> None:
        """catalog_multi_get requires dataset:pattern format."""
        tools = create_mcp_tools(mock_service)
        tool_map = {t.metadata.name: t for t in tools}
        multi_get_tool = tool_map["catalog_multi_get"]

        tool_output = multi_get_tool.call(pattern="*.md")
        result = tool_output.raw_output

        assert "error" in result
        assert "dataset prefix" in result["error"]

    def test_catalog_multi_get_filters_by_glob(self, mock_service: SearchServiceV2) -> None:
        """catalog_multi_get filters documents by glob pattern."""
        mock_doc1 = MagicMock()
        mock_doc1.path = "notes/a.md"
        mock_doc1.body = "A"
        mock_doc1.title = "A"
        mock_doc1.metadata = {}

        mock_doc2 = MagicMock()
        mock_doc2.path = "notes/b.md"
        mock_doc2.body = "B"
        mock_doc2.title = "B"
        mock_doc2.metadata = {}

        mock_doc3 = MagicMock()
        mock_doc3.path = "archive/c.md"
        mock_doc3.body = "C"
        mock_doc3.title = "C"
        mock_doc3.metadata = {}

        mock_docs = [mock_doc1, mock_doc2, mock_doc3]

        mock_dataset = MagicMock()
        mock_dataset.id = 1

        with patch("catalog.api.mcp.tools.DatasetService") as mock_ds_cls:
            mock_ds = MagicMock()
            mock_ds.get_dataset_by_name.return_value = mock_dataset
            mock_ds.list_documents.return_value = mock_docs
            mock_ds_cls.return_value = mock_ds

            tools = create_mcp_tools(mock_service)
            tool_map = {t.metadata.name: t for t in tools}
            multi_get_tool = tool_map["catalog_multi_get"]

            tool_output = multi_get_tool.call(pattern="vault:notes/*.md")
            result = tool_output.raw_output

            assert result["count"] == 2
            paths = {d["path"] for d in result["documents"]}
            assert "notes/a.md" in paths
            assert "notes/b.md" in paths
            assert "archive/c.md" not in paths


class TestCatalogStatusTool:
    """Tests for catalog_status tool."""

    @pytest.fixture
    def mock_service(self) -> SearchServiceV2:
        """Create mock SearchServiceV2."""
        mock_session = MagicMock()
        return SearchServiceV2(mock_session)

    def test_catalog_status_returns_health_info(self, mock_service: SearchServiceV2) -> None:
        """catalog_status returns health status information."""
        mock_health = MagicMock()
        mock_health.is_healthy = True
        mock_health.components = []
        mock_health.issues = []

        mock_datasets = []

        with patch("catalog.api.mcp.tools.check_health", return_value=mock_health):
            with patch("catalog.api.mcp.tools.DatasetService") as mock_ds_cls:
                mock_ds = MagicMock()
                mock_ds.list_datasets.return_value = mock_datasets
                mock_ds_cls.return_value = mock_ds

                tools = create_mcp_tools(mock_service)
                tool_map = {t.metadata.name: t for t in tools}
                status_tool = tool_map["catalog_status"]

                tool_output = status_tool.call()
                result = tool_output.raw_output

                assert result["healthy"] is True
                assert "components" in result
                assert "datasets" in result

    def test_catalog_status_handles_error(self, mock_service: SearchServiceV2) -> None:
        """catalog_status returns error info on exception."""
        with patch("catalog.api.mcp.tools.check_health", side_effect=Exception("Check failed")):
            tools = create_mcp_tools(mock_service)
            tool_map = {t.metadata.name: t for t in tools}
            status_tool = tool_map["catalog_status"]

            tool_output = status_tool.call()
            result = tool_output.raw_output

            assert result["healthy"] is False
            assert "error" in result
