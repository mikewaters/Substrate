"""catalog.api.mcp.resources - MCP resource definitions for catalog.

Provides resource listing and reading functions for the Model Context Protocol.
Resources expose datasets and documents via catalog:// URI scheme.

URI scheme:
    catalog://{dataset}           - List documents in dataset
    catalog://{dataset}/{path}    - Get specific document

Example usage:
    from catalog.api.mcp.resources import list_resources, read_resource
    from catalog.search.service_v2 import SearchServiceV2

    service = SearchServiceV2(session)

    # List all resources
    resources = list_resources(service)

    # Read a specific document
    contents = read_resource(service, "catalog://vault/notes/todo.md")
"""

from typing import Any

from agentlayer.logging import get_logger

from catalog.search.service_v2 import SearchServiceV2
from catalog.store.dataset import DatasetService

__all__ = ["list_resources", "read_resource"]

logger = get_logger(__name__)


def list_resources(service: SearchServiceV2) -> list[dict[str, Any]]:
    """List all available resources as catalog:// URIs.

    Returns datasets as top-level resources. Each dataset can be read
    to get a list of documents, or individual documents can be accessed
    via catalog://{dataset}/{path}.

    Args:
        service: SearchServiceV2 instance with database session.

    Returns:
        List of resource dictionaries with uri, name, description, and mimeType.

    Example:
        resources = list_resources(service)
        # [
        #     {
        #         "uri": "catalog://vault",
        #         "name": "vault",
        #         "description": "Dataset: vault (obsidian, 150 documents)",
        #         "mimeType": "application/json",
        #     },
        #     ...
        # ]
    """
    try:
        dataset_service = DatasetService(service.session)
        datasets = dataset_service.list_datasets()

        resources = []
        for ds in datasets:
            resources.append({
                "uri": f"catalog://{ds.name}",
                "name": ds.name,
                "description": (
                    f"Dataset: {ds.name} ({ds.source_type}, {ds.document_count} documents)"
                ),
                "mimeType": "application/json",
            })

        logger.debug(f"Listed {len(resources)} catalog resources")
        return resources

    except Exception as e:
        logger.error(f"Failed to list resources: {e}")
        return []


def read_resource(service: SearchServiceV2, uri: str) -> list[dict[str, Any]]:
    """Read a resource by catalog:// URI.

    URI formats:
    - catalog://{dataset}: Returns JSON list of documents in the dataset
    - catalog://{dataset}/{path}: Returns the specific document content

    Args:
        service: SearchServiceV2 instance with database session.
        uri: Resource URI in catalog:// format.

    Returns:
        List of content dictionaries with uri, text, and mimeType.

    Raises:
        ValueError: If URI format is invalid.

    Example:
        # List documents in a dataset
        contents = read_resource(service, "catalog://vault")

        # Get specific document
        contents = read_resource(service, "catalog://vault/notes/todo.md")
    """
    if not uri.startswith("catalog://"):
        raise ValueError(f"Invalid URI scheme, expected catalog://: {uri}")

    path = uri[len("catalog://"):]
    if not path:
        raise ValueError("Empty catalog URI path")

    # Split into dataset and document path
    parts = path.split("/", 1)
    dataset_name = parts[0]
    doc_path = parts[1] if len(parts) > 1 else None

    logger.debug(f"Reading resource: dataset={dataset_name}, path={doc_path}")

    try:
        dataset_service = DatasetService(service.session)

        # Get dataset
        try:
            dataset = dataset_service.get_dataset_by_name(dataset_name)
        except Exception:
            return [{
                "uri": uri,
                "text": f"Dataset not found: {dataset_name}",
                "mimeType": "text/plain",
            }]

        if doc_path is None:
            # Return list of documents in dataset
            return _read_dataset_listing(dataset_service, dataset, uri)
        else:
            # Return specific document
            return _read_document(dataset_service, dataset, doc_path, uri)

    except Exception as e:
        logger.error(f"Failed to read resource {uri}: {e}")
        return [{
            "uri": uri,
            "text": f"Error reading resource: {e}",
            "mimeType": "text/plain",
        }]


def _read_dataset_listing(
    dataset_service: DatasetService,
    dataset: Any,
    uri: str,
) -> list[dict[str, Any]]:
    """Read dataset listing as JSON.

    Args:
        dataset_service: DatasetService instance.
        dataset: Dataset info object.
        uri: Original URI for response.

    Returns:
        List with single content entry containing document listing.
    """
    import json

    docs = dataset_service.list_documents(dataset.id, active_only=True)

    listing = {
        "dataset": dataset.name,
        "source_type": dataset.source_type,
        "document_count": len(docs),
        "documents": [
            {
                "path": doc.path,
                "title": doc.title,
                "uri": f"catalog://{dataset.name}/{doc.path}",
            }
            for doc in docs
        ],
    }

    return [{
        "uri": uri,
        "text": json.dumps(listing, indent=2),
        "mimeType": "application/json",
    }]


def _read_document(
    dataset_service: DatasetService,
    dataset: Any,
    doc_path: str,
    uri: str,
) -> list[dict[str, Any]]:
    """Read specific document content.

    Args:
        dataset_service: DatasetService instance.
        dataset: Dataset info object.
        doc_path: Document path within dataset.
        uri: Original URI for response.

    Returns:
        List with single content entry containing document body.
    """
    try:
        doc = dataset_service.get_document_by_path(dataset.id, doc_path)

        # Determine mime type from path
        mime_type = _get_mime_type(doc_path)

        return [{
            "uri": uri,
            "text": doc.body,
            "mimeType": mime_type,
        }]

    except Exception:
        return [{
            "uri": uri,
            "text": f"Document not found: {doc_path}",
            "mimeType": "text/plain",
        }]


def _get_mime_type(path: str) -> str:
    """Determine MIME type from file path.

    Args:
        path: File path.

    Returns:
        MIME type string.
    """
    path_lower = path.lower()

    if path_lower.endswith(".md"):
        return "text/markdown"
    elif path_lower.endswith(".txt"):
        return "text/plain"
    elif path_lower.endswith(".json"):
        return "application/json"
    elif path_lower.endswith(".yaml") or path_lower.endswith(".yml"):
        return "text/yaml"
    elif path_lower.endswith(".html") or path_lower.endswith(".htm"):
        return "text/html"
    elif path_lower.endswith(".xml"):
        return "application/xml"
    elif path_lower.endswith(".py"):
        return "text/x-python"
    elif path_lower.endswith(".js"):
        return "text/javascript"
    elif path_lower.endswith(".ts"):
        return "text/typescript"
    elif path_lower.endswith(".css"):
        return "text/css"
    else:
        return "text/plain"
