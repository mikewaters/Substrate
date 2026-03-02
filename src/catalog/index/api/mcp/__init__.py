"""index.api.mcp - Model Context Protocol tools and server.

Provides MCP integration for AI assistant access to index functionality.
Includes tool definitions, resource handlers, and a stdio-based JSON-RPC server.

Example usage:
    # Create tools for an agent
    from index.api.mcp import create_mcp_tools
    from index.search.service import SearchService

    service = SearchService(session)
    tools = create_mcp_tools(service)

    # Run the MCP server
    from index.api.mcp import run_mcp_server
    run_mcp_server()
"""

from index.api.mcp.resources import list_resources, read_resource
from index.api.mcp.server import MCPServer, run_mcp_server
from index.api.mcp.tools import create_mcp_tools

__all__ = [
    "create_mcp_tools",
    "list_resources",
    "MCPServer",
    "read_resource",
    "run_mcp_server",
]
