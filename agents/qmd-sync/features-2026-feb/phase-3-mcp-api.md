# Phase 3: MCP & API

## Overview
Phase 3 exposes v2 search capabilities through the Model Context Protocol (MCP), enabling integration with Claude Code, Claude Desktop, and other AI agents. This phase transforms the catalog from a library into an AI-native service.

**Business Value:** Enables AI agents to search and retrieve documents directly, creating a seamless knowledge retrieval experience for Claude-powered applications.

---

## Feature 3.1: MCP Tool Definitions

### Business Value
Defines the contract between catalog and AI agents. Well-designed tools with clear descriptions enable effective agent-driven search, reducing the need for user intervention in finding relevant documents.

### Technical Specification

**Location:** `src/catalog/catalog/api/mcp/tools.py`

**Tool Definitions:**
```python
from llama_index.core.tools import FunctionTool

def create_mcp_tools(search_service: SearchServiceV2) -> list[FunctionTool]:
    return [
        FunctionTool.from_defaults(
            fn=lambda query, dataset=None, limit=20: _search_fts(search_service, query, dataset, limit),
            name="catalog_search",
            description="BM25 keyword search over indexed documents. Best for exact phrase or keyword matching.",
        ),
        FunctionTool.from_defaults(
            fn=lambda query, dataset=None, limit=20: _search_vector(search_service, query, dataset, limit),
            name="catalog_vsearch",
            description="Semantic vector search over indexed documents. Best for conceptual or meaning-based queries.",
        ),
        FunctionTool.from_defaults(
            fn=lambda query, dataset=None, limit=20, rerank=True: _search_hybrid(search_service, query, dataset, limit, rerank),
            name="catalog_query",
            description="Hybrid search combining BM25 and vector search with RRF fusion and optional LLM reranking. Best overall quality.",
        ),
        FunctionTool.from_defaults(
            fn=lambda path_or_docid: _get_document(search_service, path_or_docid),
            name="catalog_get",
            description="Retrieve full document content by file path or document ID (6-char hash prefix).",
        ),
        FunctionTool.from_defaults(
            fn=lambda pattern: _get_documents(search_service, pattern),
            name="catalog_multi_get",
            description="Retrieve multiple documents matching a glob pattern (e.g., 'docs/*.md').",
        ),
        FunctionTool.from_defaults(
            fn=lambda: _get_status(search_service),
            name="catalog_status",
            description="Get index health information: document count, last update time, dataset list.",
        ),
    ]
```

**Tool Schemas:**
| Tool | Parameters | Returns |
|------|------------|---------|
| catalog_search | query: str, dataset?: str, limit?: int | SearchResults |
| catalog_vsearch | query: str, dataset?: str, limit?: int | SearchResults |
| catalog_query | query: str, dataset?: str, limit?: int, rerank?: bool | SearchResults |
| catalog_get | path_or_docid: str | DocumentResult |
| catalog_multi_get | pattern: str | list[DocumentResult] |
| catalog_status | (none) | HealthStatus |

### Acceptance Criteria
- [ ] FunctionTool definitions for all 6 tools
- [ ] Clear, agent-friendly descriptions
- [ ] Type-safe parameter handling
- [ ] Error handling for invalid inputs
- [ ] Unit tests for tool dispatch

### Dependencies
- Feature 2.6 (SearchServiceV2)
- llama_index.core.tools

### Estimated Effort
Medium (3-4 hours)

---

## Feature 3.2: MCP Server Implementation

### Business Value
Enables Claude Code and Claude Desktop to access catalog search directly. Users can ask Claude to find documents without leaving their workflow, dramatically improving productivity.

### Technical Specification

**Location:** `src/catalog/catalog/api/mcp/server.py`

**Server Implementation:**
```python
"""MCP server implementation for catalog."""
import json
import sys
from typing import Any

from catalog.store.database import get_session
from catalog.search.service_v2 import SearchServiceV2
from catalog.api.mcp.tools import create_mcp_tools


class MCPServer:
    """MCP server over stdio."""

    def __init__(self):
        self.session = None
        self.service = None
        self.tools = None

    def start(self):
        """Start the MCP server."""
        with get_session() as session:
            self.session = session
            self.service = SearchServiceV2(session)
            self.tools = {t.metadata.name: t for t in create_mcp_tools(self.service)}
            self._run_loop()

    def _run_loop(self):
        """Main request/response loop."""
        for line in sys.stdin:
            try:
                request = json.loads(line.strip())
                response = self._handle_request(request)
                print(json.dumps(response), flush=True)
            except Exception as e:
                print(json.dumps({"error": str(e)}), flush=True)

    def _handle_request(self, request: dict) -> dict:
        """Handle MCP protocol request."""
        method = request.get("method")

        if method == "tools/list":
            return self._list_tools()
        elif method == "tools/call":
            return self._call_tool(request.get("params", {}))
        elif method == "resources/list":
            return self._list_resources()
        elif method == "resources/read":
            return self._read_resource(request.get("params", {}))
        else:
            return {"error": f"Unknown method: {method}"}

    def _list_tools(self) -> dict:
        """Return available tools."""
        return {
            "tools": [
                {
                    "name": name,
                    "description": tool.metadata.description,
                    "inputSchema": tool.metadata.fn_schema,
                }
                for name, tool in self.tools.items()
            ]
        }

    def _call_tool(self, params: dict) -> dict:
        """Execute a tool call."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name not in self.tools:
            return {"error": f"Unknown tool: {tool_name}"}

        tool = self.tools[tool_name]
        result = tool(**arguments)
        return {"content": [{"type": "text", "text": str(result)}]}


def run_mcp_server():
    """Entry point for MCP server."""
    server = MCPServer()
    server.start()


if __name__ == "__main__":
    run_mcp_server()
```

**Package Init:** `src/catalog/catalog/api/mcp/__init__.py`
```python
"""MCP server and tools for catalog search."""
from catalog.api.mcp.tools import create_mcp_tools
from catalog.api.mcp.server import run_mcp_server, MCPServer

__all__ = ["create_mcp_tools", "run_mcp_server", "MCPServer"]
```

**Claude Desktop Configuration:**
```json
{
  "mcpServers": {
    "catalog": {
      "command": "uv",
      "args": ["run", "python", "-m", "catalog.api.mcp.server"]
    }
  }
}
```

### Acceptance Criteria
- [ ] MCPServer class with stdio protocol
- [ ] tools/list, tools/call method handlers
- [ ] resources/list, resources/read method handlers
- [ ] Error handling and graceful degradation
- [ ] Entry point script
- [ ] Documentation for Claude Desktop setup
- [ ] Integration test with mock MCP client

### Dependencies
- Feature 3.1 (MCP tools)
- Feature 2.6 (SearchServiceV2)

### Estimated Effort
Medium (4-5 hours)

---

## Feature 3.3: MCP Resources

### Business Value
Exposes documents and datasets as MCP resources, enabling AI agents to browse and reference content using URIs. Creates a navigable knowledge structure for agents.

### Technical Specification

**Location:** `src/catalog/catalog/api/mcp/resources.py`

**Resource Definitions:**
```python
def list_resources(service: SearchServiceV2) -> list[dict]:
    """List available MCP resources."""
    resources = []

    # List datasets
    datasets = service.list_datasets()
    for dataset in datasets:
        resources.append({
            "uri": f"catalog://{dataset.name}",
            "name": dataset.name,
            "description": f"Dataset: {dataset.name} ({dataset.document_count} documents)",
            "mimeType": "application/x-catalog-dataset",
        })

    return resources


def read_resource(service: SearchServiceV2, uri: str) -> dict:
    """Read a resource by URI."""
    if uri.startswith("catalog://"):
        path = uri[10:]  # Remove 'catalog://'

        if "/" in path:
            # Document path: catalog://dataset/path/to/file.md
            dataset, doc_path = path.split("/", 1)
            return service.get_document(doc_path, dataset_name=dataset)
        else:
            # Dataset listing: catalog://dataset
            return service.list_documents(dataset_name=path)

    raise ValueError(f"Invalid catalog URI: {uri}")
```

**URI Scheme:**
- `catalog://{dataset}` - List documents in dataset
- `catalog://{dataset}/{path}` - Get specific document

### Acceptance Criteria
- [ ] list_resources function
- [ ] read_resource function
- [ ] URI scheme documentation
- [ ] Integration with MCPServer
- [ ] Unit tests for resource operations

### Dependencies
- Feature 3.2 (MCP server)

### Estimated Effort
Small (2-3 hours)

---

## Phase 3 Test Plan

**Unit Tests:** `tests/rag_v2/test_mcp_tools.py`
- Tool creation and metadata
- Tool dispatch and parameter handling
- Error handling for invalid inputs

**Integration Tests:** `tests/rag_v2/test_mcp_server.py`
- Server startup and shutdown
- Request/response protocol
- Full search workflow via MCP

**Manual Testing:**
- Claude Desktop integration
- Claude Code integration

---

## Phase 3 Deliverables

| Deliverable | Location |
|-------------|----------|
| MCP tool definitions | `catalog/api/mcp/tools.py` |
| MCP server | `catalog/api/mcp/server.py` |
| MCP resources | `catalog/api/mcp/resources.py` |
| Package init | `catalog/api/mcp/__init__.py` |
| Claude Desktop config example | `docs/mcp-setup.md` |
| Unit tests | `tests/rag_v2/test_mcp_*.py` |

---

## Claude Desktop Setup Guide

### Installation

1. Ensure catalog is installed:
   ```bash
   cd src/catalog
   uv sync
   ```

2. Add to Claude Desktop configuration (`~/.config/claude/claude_desktop_config.json`):
   ```json
   {
     "mcpServers": {
       "catalog": {
         "command": "uv",
         "args": ["run", "--directory", "/path/to/substrate/src/catalog", "python", "-m", "catalog.api.mcp.server"]
       }
     }
   }
   ```

3. Restart Claude Desktop

### Usage

Once configured, Claude can:
- Search documents: "Search my notes for authentication configuration"
- Get specific documents: "Get the document at docs/auth.md"
- Check status: "How many documents are indexed?"

### Troubleshooting

- **Server not starting:** Check `uv run python -m catalog.api.mcp.server` runs manually
- **No results:** Ensure documents are ingested with `catalog ingest`
- **Permission errors:** Check database file permissions
