"""catalog.api.mcp - Model Context Protocol tools and server.

Provides MCP integration for AI assistant access to catalog functionality.
Includes tool definitions, resource handlers, and a stdio-based JSON-RPC server.

Example usage:
    # Create tools for an agent
    from catalog.api.mcp import create_mcp_tools
    from catalog.search.service_v2 import SearchServiceV2

    service = SearchServiceV2(session)
    tools = create_mcp_tools(service)

    # Run the MCP server
    from catalog.api.mcp import run_mcp_server
    run_mcp_server()
"""

from catalog.api.mcp.resources import list_resources, read_resource
from catalog.api.mcp.server import MCPServer, run_mcp_server
from catalog.api.mcp.tools import create_mcp_tools

__all__ = [
    "create_mcp_tools",
    "list_resources",
    "MCPServer",
    "read_resource",
    "run_mcp_server",
]
