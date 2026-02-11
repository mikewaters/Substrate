from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Annotated

from advanced_alchemy.exceptions import NotFoundError as SQLAlchemyNotFoundError
from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ontologizer.api.dependencies import get_db
from ontologizer.api.errors import NotFoundError
from ontologizer.schema import (
    TopicCreate,
    TopicEdgeCreate,
    TopicEdgeResponse,
    TopicListResponse,
    TopicResponse,
    TopicStatus,
    TopicUpdate,
)
from ontologizer.relational.services import (
    TopicTaxonomyService,
)


### Topic
async def get_topic_service(
    db: AsyncSession = Depends(get_db),
) -> AsyncGenerator[TopicTaxonomyService, None]:
    """Get TopicService dependency."""
    async with TopicTaxonomyService.new(session=db) as service:
        yield service


topic_router = APIRouter(prefix="/topics", tags=["topics"])


# ==================== Edge Operations (Must be BEFORE /{topic_id} routes) ====================


@topic_router.post(
    "/edges",
    response_model=TopicEdgeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a topic edge",
)
async def create_edge(
    edge: TopicEdgeCreate,
    service: Annotated[TopicTaxonomyService, Depends(get_topic_service)],
) -> TopicEdgeResponse:
    """Create a topic edge (relationship).

    Args:
        edge: Edge creation data
        service: Topic service dependency

    Returns:
        Created edge

    Raises:
        ValidationError: If edge would create a cycle
    """
    edge = await service.create_edge(edge)
    return service.to_schema(edge, schema_type=TopicEdgeResponse)


@topic_router.delete(
    "/edges/{parent_id}/{child_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a topic edge",
)
async def delete_edge(
    parent_id: Annotated[str, Path(description="Parent topic ID")],
    child_id: Annotated[str, Path(description="Child topic ID")],
    service: Annotated[TopicTaxonomyService, Depends(get_topic_service)],
) -> None:
    """Delete a topic edge.

    Args:
        parent_id: Parent topic ID
        child_id: Child topic ID
        service: Topic service dependency

    Raises:
        NotFoundError: If edge not found
    """
    success = await service.delete_edge(parent_id, child_id)
    if not success:
        raise NotFoundError("Edge", f"{parent_id} -> {child_id}")


# ==================== CRUD Operations ====================


@topic_router.post(
    "",
    response_model=TopicResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new topic",
)
async def add_topic(
    topic: TopicCreate,
    service: Annotated[TopicTaxonomyService, Depends(get_topic_service)],
) -> TopicResponse:
    """Create a new topic.

    Args:
        topic: Topic creation data
        service: Topic service dependency

    Returns:
        Created topic

    Raises:
        ValidationError: If validation fails or slug is already taken
    """
    topic = await service.create(topic)
    return service.to_schema(topic, schema_type=TopicResponse)


@topic_router.get(
    "",
    response_model=TopicListResponse,
    summary="List topics with filters",
)
async def list_topics(
    service: Annotated[TopicTaxonomyService, Depends(get_topic_service)],
    taxonomy_id: Annotated[
        str | None, Query(description="Filter by taxonomy")
    ] = None,
    status_filter: Annotated[
        TopicStatus | None, Query(alias="status", description="Filter by status")
    ] = None,
    created_after: Annotated[
        datetime | None, Query(description="Filter by creation date (after)")
    ] = None,
    created_before: Annotated[
        datetime | None, Query(description="Filter by creation date (before)")
    ] = None,
    path_prefix: Annotated[
        str | None, Query(description="Filter by materialized path prefix")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TopicListResponse:
    """List topics with optional filters and pagination.

    Args:
        service: Topic service dependency
        taxonomy_id: Filter by taxonomy
        status_filter: Filter by status
        created_after: Filter by creation date (after)
        created_before: Filter by creation date (before)
        limit: Maximum number of results (1-100)
        offset: Number of results to skip

    Returns:
        Paginated list of topics
    """
    topics = await service.list(
        taxonomy_id=taxonomy_id,
        status=status_filter,
        created_after=created_after,
        created_before=created_before,
        path_prefix=path_prefix,
        limit=limit,
        offset=offset,
    )
    return TopicListResponse(
        items=[service.to_schema(t, schema_type=TopicResponse) for t in topics],
        total=len(topics),
        limit=limit,
        offset=offset,
    )


@topic_router.get(
    "/{topic_id}",
    response_model=TopicResponse,
    summary="Get a topic by ID",
)
async def get_topic(
    topic_id: Annotated[str, Path(description="Topic ID")],
    service: Annotated[TopicTaxonomyService, Depends(get_topic_service)],
) -> TopicResponse:
    """Get a topic by ID.

    Args:
        topic_id: Topic ID
        service: Topic service dependency

    Returns:
        Topic

    Raises:
        NotFoundError: If topic not found
    """
    try:
        topic = await service.get(topic_id)
    except SQLAlchemyNotFoundError:
        raise NotFoundError("Topic", topic_id)
    return service.to_schema(topic, schema_type=TopicResponse)


@topic_router.put(
    "/{topic_id}",
    response_model=TopicResponse,
    summary="Update a topic",
)
async def update_topic(
    topic_id: Annotated[str, Path(description="Topic ID")],
    updates: TopicUpdate,
    service: Annotated[TopicTaxonomyService, Depends(get_topic_service)],
) -> TopicResponse:
    """Update a topic.

    Args:
        topic_id: Topic ID
        updates: Fields to update
        service: Topic service dependency

    Returns:
        Updated topic

    Raises:
        NotFoundError: If topic not found
    """
    topic = await service.update(updates, topic_id)
    if topic is None:
        raise NotFoundError("Topic", topic_id)
    return service.to_schema(topic, schema_type=TopicResponse)


@topic_router.delete(
    "/{topic_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a topic",
)
async def delete_topic(
    topic_id: Annotated[str, Path(description="Topic ID")],
    service: Annotated[TopicTaxonomyService, Depends(get_topic_service)],
) -> None:
    """Delete a topic.

    Args:
        topic_id: Topic ID
        service: Topic service dependency

    Raises:
        NotFoundError: If topic not found
    """
    success = await service.delete_topic(topic_id)
    if not success:
        raise NotFoundError("Topic", topic_id)


@topic_router.post(
    "/{topic_id}/deprecate",
    response_model=TopicResponse,
    summary="Deprecate a topic",
)
async def deprecate_topic(
    topic_id: Annotated[str, Path(description="Topic ID")],
    service: Annotated[TopicTaxonomyService, Depends(get_topic_service)],
) -> TopicResponse:
    """Mark a topic as deprecated.

    Args:
        topic_id: Topic ID
        service: Topic service dependency

    Returns:
        Deprecated topic

    Raises:
        NotFoundError: If topic not found
    """
    topic = await service.update({"status": "deprecated"}, topic_id)
    if topic is None:
        raise NotFoundError("Topic", topic_id)
    return service.to_schema(topic, schema_type=TopicResponse)


# ==================== Hierarchy Traversal ====================


@topic_router.get(
    "/{topic_id}/ancestors",
    response_model=list[TopicResponse],
    summary="Get ancestor topics",
)
async def get_ancestors(
    topic_id: Annotated[str, Path(description="Topic ID")],
    service: Annotated[TopicTaxonomyService, Depends(get_topic_service)],
    max_depth: Annotated[
        int | None, Query(ge=1, description="Maximum depth to traverse")
    ] = None,
) -> list[TopicResponse]:
    """Get all ancestor topics.

    Args:
        topic_id: Topic ID
        service: Topic service dependency
        max_depth: Optional maximum depth to traverse

    Returns:
        List of ancestor topics

    Raises:
        NotFoundError: If topic not found
    """
    # Verify topic exists
    topic = await service.get(topic_id)
    if topic is None:
        raise NotFoundError("Topic", topic_id)

    topics = await service.get_ancestors(topic_id, max_depth=max_depth)
    return [service.to_schema(t, schema_type=TopicResponse) for t in topics]


@topic_router.get(
    "/{topic_id}/descendants",
    response_model=list[TopicResponse],
    summary="Get descendant topics",
)
async def get_descendants(
    topic_id: Annotated[str, Path(description="Topic ID")],
    service: Annotated[TopicTaxonomyService, Depends(get_topic_service)],
    max_depth: Annotated[
        int | None, Query(ge=1, description="Maximum depth to traverse")
    ] = None,
) -> list[TopicResponse]:
    """Get all descendant topics.

    Args:
        topic_id: Topic ID
        service: Topic service dependency
        max_depth: Optional maximum depth to traverse

    Returns:
        List of descendant topics

    Raises:
        NotFoundError: If topic not found
    """
    # Verify topic exists
    topic = await service.get(topic_id)
    if topic is None:
        raise NotFoundError("Topic", topic_id)

    topics = await service.get_descendants(topic_id, max_depth=max_depth)
    return [service.to_schema(t, schema_type=TopicResponse) for t in topics]
