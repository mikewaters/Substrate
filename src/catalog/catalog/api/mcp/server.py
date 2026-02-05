"""catalog.api.mcp.server - MCP Server implementation for catalog.

Provides a stdio-based JSON-RPC server implementing the Model Context Protocol (MCP).
Enables AI assistants to interact with the catalog search and retrieval functionality.

Example usage:
    # As entry point
    from catalog.api.mcp.server import run_mcp_server
    run_mcp_server()

    # Programmatic usage
    from catalog.api.mcp.server import MCPServer
    server = MCPServer()
    server.start()
"""

import json
import sys
from typing import Any

from agentlayer.logging import get_logger

from catalog.api.mcp.resources import list_resources, read_resource
from catalog.api.mcp.tools import create_mcp_tools
from catalog.search.service_v2 import SearchServiceV2
from catalog.store.database import get_session
from catalog.store.session_context import use_session

__all__ = ["MCPServer", "run_mcp_server"]

logger = get_logger(__name__)


class MCPServer:
    """MCP Server with stdio JSON-RPC protocol.

    Implements the Model Context Protocol for AI assistant integration.
    Handles tool listing, tool invocation, resource listing, and resource reading.

    Attributes:
        _session: SQLAlchemy database session.
        _service: SearchServiceV2 instance.
        _tools: List of FunctionTool instances.
        _tool_map: Dictionary mapping tool names to FunctionTool instances.
    """

    def __init__(self) -> None:
        """Initialize the MCP server.

        Sets up database session, search service, and tools.
        """
        self._session = None
        self._service = None
        self._tools = None
        self._tool_map = None
        self._running = False

    def _ensure_initialized(self) -> None:
        """Ensure service and tools are initialized.

        Lazily initializes database session, search service, and MCP tools.
        """
        if self._service is None:
            self._session = get_session().__enter__()
            use_session(self._session).__enter__()
            self._service = SearchServiceV2(self._session)
            self._tools = create_mcp_tools(self._service)
            self._tool_map = {t.metadata.name: t for t in self._tools}
            logger.debug(f"Initialized MCPServer with {len(self._tools)} tools")

    def start(self) -> None:
        """Start the MCP server.

        Runs the main request/response loop, reading from stdin
        and writing to stdout.
        """
        self._running = True
        logger.info("Starting MCP server")

        try:
            self._ensure_initialized()
            self._run_loop()
        except KeyboardInterrupt:
            logger.info("MCP server interrupted")
        except Exception as e:
            logger.error(f"MCP server error: {e}")
            raise
        finally:
            self._cleanup()

    def _run_loop(self) -> None:
        """Main request/response loop.

        Reads JSON-RPC requests from stdin and writes responses to stdout.
        """
        while self._running:
            try:
                line = sys.stdin.readline()
                if not line:
                    logger.debug("EOF received, shutting down")
                    break

                line = line.strip()
                if not line:
                    continue

                request = json.loads(line)
                response = self._handle_request(request)

                if response is not None:
                    self._write_response(response)

            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON received: {e}")
                self._write_error(-32700, "Parse error", None)
            except Exception as e:
                logger.error(f"Request handling error: {e}")
                self._write_error(-32603, str(e), None)

    def _handle_request(self, request: dict[str, Any]) -> dict[str, Any] | None:
        """Route request to appropriate handler.

        Args:
            request: JSON-RPC request dictionary.

        Returns:
            JSON-RPC response dictionary, or None for notifications.
        """
        method = request.get("method", "")
        params = request.get("params", {})
        request_id = request.get("id")

        logger.debug(f"Handling request: {method}")

        # Dispatch to handler
        handlers = {
            "initialize": self._handle_initialize,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "resources/list": self._handle_resources_list,
            "resources/read": self._handle_resources_read,
            "shutdown": self._handle_shutdown,
        }

        handler = handlers.get(method)
        if handler is None:
            if request_id is not None:
                return self._make_error(-32601, f"Method not found: {method}", request_id)
            return None

        try:
            result = handler(params)
            if request_id is not None:
                return self._make_result(result, request_id)
            return None
        except Exception as e:
            logger.error(f"Handler error for {method}: {e}")
            if request_id is not None:
                return self._make_error(-32603, str(e), request_id)
            return None

    def _handle_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle initialize request.

        Args:
            params: Request parameters.

        Returns:
            Server capabilities.
        """
        logger.info("MCP server initialized")
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False},
            },
            "serverInfo": {
                "name": "catalog-mcp",
                "version": "1.0.0",
            },
        }

    def _handle_tools_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle tools/list request.

        Args:
            params: Request parameters (unused).

        Returns:
            List of available tools with schemas.
        """
        self._ensure_initialized()

        tools = []
        for tool in self._tools:
            tool_info = {
                "name": tool.metadata.name,
                "description": tool.metadata.description or "",
            }

            # Add input schema if available
            if hasattr(tool.metadata, "fn_schema") and tool.metadata.fn_schema:
                schema = tool.metadata.fn_schema
                if hasattr(schema, "model_json_schema"):
                    tool_info["inputSchema"] = schema.model_json_schema()

            tools.append(tool_info)

        return {"tools": tools}

    def _handle_tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle tools/call request.

        Args:
            params: Request parameters with tool name and arguments.

        Returns:
            Tool execution result.
        """
        self._ensure_initialized()

        name = params.get("name", "")
        arguments = params.get("arguments", {})

        tool = self._tool_map.get(name)
        if tool is None:
            return {
                "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
                "isError": True,
            }

        try:
            result = tool.call(**arguments)

            # Convert result to content format
            if isinstance(result, dict):
                text = json.dumps(result, indent=2)
            else:
                text = str(result)

            return {
                "content": [{"type": "text", "text": text}],
                "isError": False,
            }

        except Exception as e:
            logger.error(f"Tool call failed for {name}: {e}")
            return {
                "content": [{"type": "text", "text": f"Error: {e}"}],
                "isError": True,
            }

    def _handle_resources_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle resources/list request.

        Args:
            params: Request parameters (unused).

        Returns:
            List of available resources.
        """
        self._ensure_initialized()

        try:
            resources = list_resources(self._service)
            return {"resources": resources}
        except Exception as e:
            logger.error(f"resources/list failed: {e}")
            return {"resources": []}

    def _handle_resources_read(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle resources/read request.

        Args:
            params: Request parameters with resource URI.

        Returns:
            Resource contents.
        """
        self._ensure_initialized()

        uri = params.get("uri", "")

        try:
            contents = read_resource(self._service, uri)
            return {"contents": contents}
        except Exception as e:
            logger.error(f"resources/read failed for {uri}: {e}")
            return {
                "contents": [{"uri": uri, "text": f"Error: {e}", "mimeType": "text/plain"}],
            }

    def _handle_shutdown(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle shutdown request.

        Args:
            params: Request parameters (unused).

        Returns:
            Empty result.
        """
        logger.info("Shutdown requested")
        self._running = False
        return {}

    def _make_result(self, result: Any, request_id: Any) -> dict[str, Any]:
        """Create JSON-RPC result response.

        Args:
            result: Result value.
            request_id: Request ID.

        Returns:
            JSON-RPC response dictionary.
        """
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        }

    def _make_error(
        self,
        code: int,
        message: str,
        request_id: Any,
    ) -> dict[str, Any]:
        """Create JSON-RPC error response.

        Args:
            code: Error code.
            message: Error message.
            request_id: Request ID.

        Returns:
            JSON-RPC error response dictionary.
        """
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message,
            },
        }

    def _write_response(self, response: dict[str, Any]) -> None:
        """Write JSON-RPC response to stdout.

        Args:
            response: Response dictionary.
        """
        line = json.dumps(response)
        sys.stdout.write(line + "\n")
        sys.stdout.flush()

    def _write_error(self, code: int, message: str, request_id: Any) -> None:
        """Write JSON-RPC error to stdout.

        Args:
            code: Error code.
            message: Error message.
            request_id: Request ID.
        """
        response = self._make_error(code, message, request_id)
        self._write_response(response)

    def _cleanup(self) -> None:
        """Clean up resources on shutdown."""
        logger.debug("Cleaning up MCP server resources")
        if self._session is not None:
            try:
                self._session.close()
            except Exception as e:
                logger.warning(f"Error closing session: {e}")
        self._running = False


def run_mcp_server() -> None:
    """Run the MCP server.

    Main entry point for the MCP server. Creates an MCPServer instance
    and starts the request/response loop.
    """
    server = MCPServer()
    server.start()


if __name__ == "__main__":
    run_mcp_server()
