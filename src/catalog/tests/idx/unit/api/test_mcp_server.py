"""Tests for catalog.api.mcp.server module."""

import json
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from catalog.api.mcp.server import MCPServer


class TestMCPServerInit:
    """Tests for MCPServer initialization."""

    def test_init_sets_defaults(self) -> None:
        """MCPServer initializes with None values."""
        server = MCPServer()

        assert server._session is None
        assert server._service is None
        assert server._tools is None
        assert server._tool_map is None
        assert server._running is False


class TestMCPServerEnsureInitialized:
    """Tests for lazy initialization."""

    def test_ensure_initialized_creates_service(self) -> None:
        """_ensure_initialized creates SearchServiceV2."""
        server = MCPServer()

        with patch("catalog.api.mcp.server.get_session") as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)

            with patch("catalog.api.mcp.server.use_session"):
                with patch("catalog.api.mcp.server.SearchServiceV2") as mock_service_cls:
                    mock_service = MagicMock()
                    mock_service_cls.return_value = mock_service

                    with patch("catalog.api.mcp.server.create_mcp_tools") as mock_create_tools:
                        mock_tools = [MagicMock()]
                        mock_tools[0].metadata.name = "test_tool"
                        mock_create_tools.return_value = mock_tools

                        server._ensure_initialized()

                        assert server._service is mock_service
                        assert server._tools == mock_tools
                        assert "test_tool" in server._tool_map


class TestMCPServerHandleRequest:
    """Tests for request handling."""

    @pytest.fixture
    def initialized_server(self) -> MCPServer:
        """Create server with mocked initialization."""
        server = MCPServer()

        mock_session = MagicMock()
        server._session = mock_session

        mock_service = MagicMock()
        server._service = mock_service

        mock_tool = MagicMock()
        mock_tool.metadata.name = "test_tool"
        mock_tool.metadata.description = "Test tool description"
        mock_tool.call.return_value = {"result": "success"}

        server._tools = [mock_tool]
        server._tool_map = {"test_tool": mock_tool}

        return server

    def test_handle_initialize(self, initialized_server: MCPServer) -> None:
        """Handle initialize request returns capabilities."""
        request = {"id": 1, "method": "initialize", "params": {}}

        response = initialized_server._handle_request(request)

        assert response is not None
        assert response["id"] == 1
        assert "result" in response
        assert response["result"]["protocolVersion"] == "2024-11-05"
        assert "capabilities" in response["result"]
        assert "serverInfo" in response["result"]

    def test_handle_tools_list(self, initialized_server: MCPServer) -> None:
        """Handle tools/list request returns tool list."""
        request = {"id": 2, "method": "tools/list", "params": {}}

        response = initialized_server._handle_request(request)

        assert response is not None
        assert response["id"] == 2
        assert "result" in response
        assert "tools" in response["result"]
        assert len(response["result"]["tools"]) == 1
        assert response["result"]["tools"][0]["name"] == "test_tool"

    def test_handle_tools_call(self, initialized_server: MCPServer) -> None:
        """Handle tools/call request invokes tool."""
        request = {
            "id": 3,
            "method": "tools/call",
            "params": {"name": "test_tool", "arguments": {"arg1": "value1"}},
        }

        response = initialized_server._handle_request(request)

        assert response is not None
        assert response["id"] == 3
        assert "result" in response
        assert response["result"]["isError"] is False
        assert "content" in response["result"]

        # Verify tool was called
        initialized_server._tool_map["test_tool"].call.assert_called_once_with(arg1="value1")

    def test_handle_tools_call_unknown_tool(self, initialized_server: MCPServer) -> None:
        """Handle tools/call with unknown tool returns error."""
        request = {
            "id": 4,
            "method": "tools/call",
            "params": {"name": "unknown_tool", "arguments": {}},
        }

        response = initialized_server._handle_request(request)

        assert response is not None
        assert response["result"]["isError"] is True
        assert "Unknown tool" in response["result"]["content"][0]["text"]

    def test_handle_resources_list(self, initialized_server: MCPServer) -> None:
        """Handle resources/list request."""
        request = {"id": 5, "method": "resources/list", "params": {}}

        with patch("catalog.api.mcp.server.list_resources") as mock_list:
            mock_list.return_value = [{"uri": "catalog://vault", "name": "vault"}]

            response = initialized_server._handle_request(request)

            assert response is not None
            assert "result" in response
            assert "resources" in response["result"]

    def test_handle_resources_read(self, initialized_server: MCPServer) -> None:
        """Handle resources/read request."""
        request = {
            "id": 6,
            "method": "resources/read",
            "params": {"uri": "catalog://vault/test.md"},
        }

        with patch("catalog.api.mcp.server.read_resource") as mock_read:
            mock_read.return_value = [
                {"uri": "catalog://vault/test.md", "text": "Content", "mimeType": "text/markdown"}
            ]

            response = initialized_server._handle_request(request)

            assert response is not None
            assert "result" in response
            assert "contents" in response["result"]

    def test_handle_shutdown(self, initialized_server: MCPServer) -> None:
        """Handle shutdown request sets running to False."""
        initialized_server._running = True
        request = {"id": 7, "method": "shutdown", "params": {}}

        response = initialized_server._handle_request(request)

        assert response is not None
        assert initialized_server._running is False

    def test_handle_unknown_method(self, initialized_server: MCPServer) -> None:
        """Handle unknown method returns error."""
        request = {"id": 8, "method": "unknown/method", "params": {}}

        response = initialized_server._handle_request(request)

        assert response is not None
        assert "error" in response
        assert response["error"]["code"] == -32601

    def test_handle_notification_no_id(self, initialized_server: MCPServer) -> None:
        """Handle request without ID (notification) returns None."""
        request = {"method": "shutdown", "params": {}}

        response = initialized_server._handle_request(request)

        # Notifications don't get responses
        assert response is None


class TestMCPServerJsonRpc:
    """Tests for JSON-RPC formatting."""

    @pytest.fixture
    def server(self) -> MCPServer:
        """Create basic server."""
        return MCPServer()

    def test_make_result(self, server: MCPServer) -> None:
        """_make_result creates valid JSON-RPC response."""
        result = {"data": "test"}

        response = server._make_result(result, 1)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert response["result"] == {"data": "test"}

    def test_make_error(self, server: MCPServer) -> None:
        """_make_error creates valid JSON-RPC error."""
        response = server._make_error(-32600, "Invalid request", 2)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 2
        assert response["error"]["code"] == -32600
        assert response["error"]["message"] == "Invalid request"


class TestMCPServerRunLoop:
    """Tests for main run loop."""

    def test_run_loop_processes_requests(self) -> None:
        """_run_loop processes JSON-RPC requests from stdin."""
        server = MCPServer()
        server._running = True

        # Mock initialized state
        server._session = MagicMock()
        server._service = MagicMock()
        server._tools = []
        server._tool_map = {}

        # Prepare input/output
        input_data = json.dumps({"id": 1, "method": "initialize", "params": {}}) + "\n"

        with patch("sys.stdin", StringIO(input_data)):
            output = StringIO()
            with patch("sys.stdout", output):
                # Run one iteration then exit
                server._running = False
                server._run_loop()

    def test_run_loop_handles_invalid_json(self) -> None:
        """_run_loop handles invalid JSON gracefully."""
        server = MCPServer()
        server._running = True
        server._session = MagicMock()
        server._service = MagicMock()
        server._tools = []
        server._tool_map = {}

        # Invalid JSON followed by EOF
        input_data = "not valid json\n"

        with patch("sys.stdin", StringIO(input_data)):
            output = StringIO()
            with patch("sys.stdout", output):
                server._run_loop()

                # Should have written error response
                output.seek(0)
                response_line = output.readline()
                if response_line:
                    response = json.loads(response_line)
                    assert "error" in response
                    assert response["error"]["code"] == -32700


class TestMCPServerCleanup:
    """Tests for server cleanup."""

    def test_cleanup_closes_session(self) -> None:
        """_cleanup closes database session."""
        server = MCPServer()
        mock_session = MagicMock()
        server._session = mock_session
        server._running = True

        server._cleanup()

        mock_session.close.assert_called_once()
        assert server._running is False

    def test_cleanup_handles_close_error(self) -> None:
        """_cleanup handles session close error gracefully."""
        server = MCPServer()
        mock_session = MagicMock()
        mock_session.close.side_effect = Exception("Close failed")
        server._session = mock_session
        server._running = True

        # Should not raise
        server._cleanup()

        assert server._running is False


class TestRunMcpServer:
    """Tests for run_mcp_server entry point."""

    def test_run_mcp_server_creates_and_starts(self) -> None:
        """run_mcp_server creates MCPServer and calls start."""
        from catalog.api.mcp.server import run_mcp_server

        with patch("catalog.api.mcp.server.MCPServer") as mock_cls:
            mock_server = MagicMock()
            mock_cls.return_value = mock_server

            run_mcp_server()

            mock_cls.assert_called_once()
            mock_server.start.assert_called_once()
