"""catalog.api.mcp.tools - MCP tool definitions for RAG search.

Provides LlamaIndex FunctionTool wrappers for the SearchService.
These tools enable AI agents to search and retrieve documents from the catalog.

Example usage:
    from catalog.api.mcp.tools import create_mcp_tools
    from catalog.search.service import SearchService
    from catalog.store.database import get_session

    with get_session() as session:
        service = SearchService(session)
        tools = create_mcp_tools(service)

        # Use tools with an agent
        for tool in tools:
            print(f"Tool: {tool.metadata.name}")
"""

from typing import Any

from agentlayer.logging import get_logger
from llama_index.core.tools import FunctionTool
from pydantic import BaseModel, Field

from catalog.core.status import check_health
from catalog.search.models import SearchCriteria, SearchResult
from catalog.search.service import SearchService
from catalog.store.dataset import DatasetService

__all__ = ["create_mcp_tools"]

logger = get_logger(__name__)


class SearchToolResult(BaseModel):
    """Pydantic model for search tool results."""

    results: list[dict[str, Any]] = Field(default_factory=list)
    query: str
    mode: str
    total_count: int = 0
    timing_ms: float | None = None


class DocumentResult(BaseModel):
    """Pydantic model for document retrieval results."""

    path: str
    dataset_name: str
    body: str
    title: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class StatusResult(BaseModel):
    """Pydantic model for status check results."""

    healthy: bool
    components: list[dict[str, Any]] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


def _result_to_dict(result: SearchResult) -> dict[str, Any]:
    """Convert SearchResult to a dictionary for tool output.

    Args:
        result: SearchResult instance.

    Returns:
        Dictionary representation suitable for tool output.
    """
    return {
        "path": result.path,
        "dataset_name": result.dataset_name,
        "score": result.score,
        "snippet": result.snippet.model_dump() if result.snippet else None,
        "metadata": result.metadata,
    }


def _make_catalog_search(service: SearchService):
    """Create catalog_search tool function.

    Args:
        service: SearchService instance.

    Returns:
        Callable for BM25 keyword search.
    """

    def catalog_search(
        query: str,
        dataset: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Search the catalog using BM25 keyword matching.

        Performs full-text search using SQLite FTS5 with BM25 ranking.
        Best for exact keyword matches and phrase searches.

        Args:
            query: Search query string (keywords, phrases).
            dataset: Filter to specific dataset name. None for global search.
            limit: Maximum results to return (1-100).

        Returns:
            Dictionary with results list, query, mode, and timing info.
        """
        try:
            criteria = SearchCriteria(
                query=query,
                mode="fts",
                dataset_name=dataset,
                limit=min(max(1, limit), 100),
            )
            search_results = service.search(criteria)

            return {
                "results": [_result_to_dict(r) for r in search_results.results],
                "query": query,
                "mode": "fts",
                "total_count": len(search_results.results),
                "timing_ms": search_results.timing_ms,
            }
        except Exception as e:
            logger.error(f"catalog_search failed: {e}")
            return {
                "results": [],
                "query": query,
                "mode": "fts",
                "total_count": 0,
                "error": str(e),
            }

    return catalog_search


def _make_catalog_vsearch(service: SearchService):
    """Create catalog_vsearch tool function.

    Args:
        service: SearchService instance.

    Returns:
        Callable for semantic vector search.
    """

    def catalog_vsearch(
        query: str,
        dataset: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Search the catalog using semantic vector similarity.

        Performs embedding-based similarity search using Qdrant.
        Best for conceptual queries and finding semantically related content.

        Args:
            query: Natural language query describing what you're looking for.
            dataset: Filter to specific dataset name. None for global search.
            limit: Maximum results to return (1-100).

        Returns:
            Dictionary with results list, query, mode, and timing info.
        """
        try:
            criteria = SearchCriteria(
                query=query,
                mode="vector",
                dataset_name=dataset,
                limit=min(max(1, limit), 100),
            )
            search_results = service.search(criteria)

            return {
                "results": [_result_to_dict(r) for r in search_results.results],
                "query": query,
                "mode": "vector",
                "total_count": len(search_results.results),
                "timing_ms": search_results.timing_ms,
            }
        except Exception as e:
            logger.error(f"catalog_vsearch failed: {e}")
            return {
                "results": [],
                "query": query,
                "mode": "vector",
                "total_count": 0,
                "error": str(e),
            }

    return catalog_vsearch


def _make_catalog_query(service: SearchService):
    """Create catalog_query tool function.

    Args:
        service: SearchService instance.

    Returns:
        Callable for hybrid search with RRF fusion.
    """

    def catalog_query(
        query: str,
        dataset: str | None = None,
        limit: int = 20,
        rerank: bool = True,
    ) -> dict[str, Any]:
        """Search the catalog using hybrid search with RRF fusion.

        Combines BM25 keyword search and vector similarity using
        Reciprocal Rank Fusion. Optionally applies LLM reranking for
        improved relevance.

        Args:
            query: Search query (natural language or keywords).
            dataset: Filter to specific dataset name. None for global search.
            limit: Maximum results to return (1-100).
            rerank: Apply LLM-based reranking for better relevance.

        Returns:
            Dictionary with results list, query, mode, and timing info.
        """
        try:
            criteria = SearchCriteria(
                query=query,
                mode="hybrid",
                dataset_name=dataset,
                limit=min(max(1, limit), 100),
                rerank=rerank,
            )
            search_results = service.search(criteria)

            return {
                "results": [_result_to_dict(r) for r in search_results.results],
                "query": query,
                "mode": "hybrid",
                "total_count": len(search_results.results),
                "timing_ms": search_results.timing_ms,
                "reranked": rerank,
            }
        except Exception as e:
            logger.error(f"catalog_query failed: {e}")
            return {
                "results": [],
                "query": query,
                "mode": "hybrid",
                "total_count": 0,
                "error": str(e),
            }

    return catalog_query


def _make_catalog_get(service: SearchService):
    """Create catalog_get tool function.

    Args:
        service: SearchService instance.

    Returns:
        Callable for document retrieval by path or ID.
    """

    def catalog_get(path_or_docid: str) -> dict[str, Any]:
        """Get a document by path or document ID.

        Retrieves a specific document from the catalog.
        Path can be in format "dataset:path/to/file.md" or just "path/to/file.md".

        Args:
            path_or_docid: Document path (with optional dataset prefix) or doc ID.

        Returns:
            Dictionary with document path, body, title, and metadata.
        """
        try:
            dataset_service = DatasetService(service.session)

            # Parse dataset:path format
            if ":" in path_or_docid and not path_or_docid.startswith("/"):
                parts = path_or_docid.split(":", 1)
                dataset_name = parts[0]
                path = parts[1]
            else:
                # Try to find in any dataset
                dataset_name = None
                path = path_or_docid

            if dataset_name:
                # Get specific dataset
                dataset = dataset_service.get_dataset_by_name(dataset_name)
                doc = dataset_service.get_document_by_path(dataset.id, path)
                return {
                    "path": doc.path,
                    "dataset_name": dataset_name,
                    "body": doc.body,
                    "title": doc.title,
                    "metadata": doc.metadata,
                }
            else:
                # Search across all datasets
                datasets = dataset_service.list_datasets()
                for ds in datasets:
                    try:
                        doc = dataset_service.get_document_by_path(ds.id, path)
                        return {
                            "path": doc.path,
                            "dataset_name": ds.name,
                            "body": doc.body,
                            "title": doc.title,
                            "metadata": doc.metadata,
                        }
                    except Exception:
                        continue

                return {
                    "error": f"Document not found: {path_or_docid}",
                    "path": path_or_docid,
                }

        except Exception as e:
            logger.error(f"catalog_get failed: {e}")
            return {
                "error": str(e),
                "path": path_or_docid,
            }

    return catalog_get


def _make_catalog_multi_get(service: SearchService):
    """Create catalog_multi_get tool function.

    Args:
        service: SearchService instance.

    Returns:
        Callable for multiple document retrieval by glob pattern.
    """

    def catalog_multi_get(pattern: str) -> dict[str, Any]:
        """Get multiple documents by glob pattern.

        Retrieves documents matching a glob pattern within a dataset.
        Pattern can be "dataset:*.md" or "dataset:notes/**/*.md".

        Args:
            pattern: Glob pattern with dataset prefix (e.g., "vault:*.md").

        Returns:
            Dictionary with list of matching documents.
        """
        import fnmatch

        try:
            # Parse dataset:pattern format
            if ":" not in pattern:
                return {
                    "error": "Pattern must include dataset prefix (e.g., 'vault:*.md')",
                    "pattern": pattern,
                    "documents": [],
                }

            parts = pattern.split(":", 1)
            dataset_name = parts[0]
            glob_pattern = parts[1]

            dataset_service = DatasetService(service.session)

            try:
                dataset = dataset_service.get_dataset_by_name(dataset_name)
            except Exception:
                return {
                    "error": f"Dataset not found: {dataset_name}",
                    "pattern": pattern,
                    "documents": [],
                }

            # Get all documents in dataset
            all_docs = dataset_service.list_documents(dataset.id, active_only=True)

            # Filter by glob pattern
            matching_docs = []
            for doc in all_docs:
                if fnmatch.fnmatch(doc.path, glob_pattern):
                    matching_docs.append({
                        "path": doc.path,
                        "dataset_name": dataset_name,
                        "body": doc.body,
                        "title": doc.title,
                        "metadata": doc.metadata,
                    })

            return {
                "pattern": pattern,
                "documents": matching_docs,
                "count": len(matching_docs),
            }

        except Exception as e:
            logger.error(f"catalog_multi_get failed: {e}")
            return {
                "error": str(e),
                "pattern": pattern,
                "documents": [],
            }

    return catalog_multi_get


def _make_catalog_status(service: SearchService):
    """Create catalog_status tool function.

    Args:
        service: SearchService instance.

    Returns:
        Callable for index health status.
    """

    def catalog_status() -> dict[str, Any]:
        """Get catalog index health and status information.

        Returns information about database connectivity, vector store,
        FTS tables, and any issues.

        Returns:
            Dictionary with health status and component details.
        """
        try:
            health = check_health()

            dataset_service = DatasetService(service.session)
            datasets = dataset_service.list_datasets()

            return {
                "healthy": health.is_healthy,
                "components": [
                    {
                        "name": c.name,
                        "healthy": c.healthy,
                        "message": c.message,
                        "details": c.details,
                    }
                    for c in health.components
                ],
                "issues": health.issues,
                "datasets": [
                    {
                        "name": ds.name,
                        "source_type": ds.source_type,
                        "document_count": ds.document_count,
                    }
                    for ds in datasets
                ],
            }

        except Exception as e:
            logger.error(f"catalog_status failed: {e}")
            return {
                "healthy": False,
                "error": str(e),
                "components": [],
                "issues": [str(e)],
                "datasets": [],
            }

    return catalog_status


def create_mcp_tools(service: SearchService) -> list[FunctionTool]:
    """Create MCP tools for the catalog search service.

    Creates LlamaIndex FunctionTool wrappers for all catalog operations:
    - catalog_search: BM25 keyword search
    - catalog_vsearch: Semantic vector search
    - catalog_query: Hybrid search with RRF and optional reranking
    - catalog_get: Get document by path or ID
    - catalog_multi_get: Get multiple documents by glob pattern
    - catalog_status: Get index health info

    Args:
        service: SearchService instance with database session.

    Returns:
        List of FunctionTool instances ready for agent use.

    Example:
        service = SearchService(session)
        tools = create_mcp_tools(service)

        # Get tool by name
        tool_map = {t.metadata.name: t for t in tools}
        search_tool = tool_map["catalog_search"]
    """
    tools = [
        FunctionTool.from_defaults(
            fn=_make_catalog_search(service),
            name="catalog_search",
            description=(
                "BM25 keyword search. Best for exact keyword matches and phrases. "
                "Returns documents ranked by keyword relevance."
            ),
        ),
        FunctionTool.from_defaults(
            fn=_make_catalog_vsearch(service),
            name="catalog_vsearch",
            description=(
                "Semantic vector search. Best for conceptual queries and finding "
                "related content. Uses embedding similarity."
            ),
        ),
        FunctionTool.from_defaults(
            fn=_make_catalog_query(service),
            name="catalog_query",
            description=(
                "Hybrid search combining BM25 and vector search with RRF fusion. "
                "Optional LLM reranking for best relevance. Recommended for most queries."
            ),
        ),
        FunctionTool.from_defaults(
            fn=_make_catalog_get(service),
            name="catalog_get",
            description=(
                "Get a specific document by path. Use 'dataset:path' format or "
                "just path to search all datasets."
            ),
        ),
        FunctionTool.from_defaults(
            fn=_make_catalog_multi_get(service),
            name="catalog_multi_get",
            description=(
                "Get multiple documents matching a glob pattern. "
                "Use 'dataset:pattern' format (e.g., 'vault:notes/*.md')."
            ),
        ),
        FunctionTool.from_defaults(
            fn=_make_catalog_status(service),
            name="catalog_status",
            description=(
                "Get catalog health status including database, vector store, "
                "and FTS table status. Shows all indexed datasets."
            ),
        ),
    ]

    logger.debug(f"Created {len(tools)} MCP tools")
    return tools
