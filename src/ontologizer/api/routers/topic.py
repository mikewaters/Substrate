from collections.abc import AsyncGenerator
from typing import Annotated

from advanced_alchemy.exceptions import NotFoundError as SQLAlchemyNotFoundError
from advanced_alchemy.filters import LimitOffset
from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ontologizer.api.dependencies import get_db
from ontologizer.api.errors import NotFoundError
from ontologizer.schema import (
    TopicOverviewListResponse,
    TopicStatus,
    TopicOverview,
    TaxonomyListResponse,
    TaxonomyResponse
)
from ontologizer.relational.services import (
    TopicQueryService,
    TaxonomyService
)


async def get_taxonomy_service(
    db: AsyncSession = Depends(get_db),
) -> AsyncGenerator[TaxonomyService, None]:
    """Get TaxonomyService dependency."""
    async with TaxonomyService.new(session=db) as service:
        yield service

async def get_query_service(
    db: AsyncSession = Depends(get_db),
) -> AsyncGenerator[TopicQueryService, None]:
    """Get TopicQueryService dependency for read-only operations."""
    async with TopicQueryService.new(session=db) as service:
        yield service


taxonomy_router = APIRouter(prefix="/taxonomies", tags=["taxonomies"])
topic_router = APIRouter(prefix="/topics", tags=["topics"])

@taxonomy_router.get(
    "",
    response_model=TaxonomyListResponse,
    summary="List taxonomies",
)
async def list_taxonomies(
    service: Annotated[TaxonomyService, Depends(get_taxonomy_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TaxonomyListResponse:
    """List taxonomies with pagination.

    Args:
        service: Taxonomy service dependency
        limit: Maximum number of results (1-100)
        offset: Number of results to skip

    Returns:
        Paginated list of taxonomies
    """
    result, total = await service.list_and_count(
        LimitOffset(limit=limit, offset=offset)
    )
    items = [service.to_schema(t, schema_type=TaxonomyResponse) for t in result]
    return TaxonomyListResponse(items=items, total=total, limit=limit, offset=offset)



@taxonomy_router.get(
    "/{taxonomy_id}/topics",
    response_model=TopicOverviewListResponse,
    summary="List enriched topics for a taxonomy",
    description="""
    Returns paginated topic overviews for a taxonomy, including parent/child
    metadata needed for UI rendering (child counts, parent names, etc.).
    """,
)
async def list_taxonomy_topic_overviews(
    taxonomy_id: Annotated[
        str, Path(description="Taxonomy ID whose topics should be returned")
    ],
    service: Annotated[TopicQueryService, Depends(get_query_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    status: Annotated[
        TopicStatus | None, Query(description="Filter by status")
    ] = None,
    search: Annotated[
        str | None,
        Query(description="Full-text search over topic title/description"),
    ] = None,
    sort_by: Annotated[
        str,
        Query(
            description="Field to sort by",
            pattern="^(title|status|created_at|updated_at|child_count)$",
        ),
    ] = "title",
    sort_order: Annotated[
        str, Query(description="Sort order", pattern="^(asc|desc)$")
    ] = "asc",
) -> TopicOverviewListResponse:
    """List enriched topics for a taxonomy.

    Args:
        taxonomy_id: Taxonomy ID whose topics should be returned
        service: Topic query service dependency
        limit: Maximum number of results (1-100)
        offset: Number of results to skip
        status: Optional status filter
        search: Optional full-text search
        sort_by: Field to sort by
        sort_order: Sort order (asc/desc)

    Returns:
        Paginated list of topic overviews
    """
    return await service.list_topic_overviews(
        taxonomy_id=taxonomy_id,
        limit=limit,
        offset=offset,
        status=status,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@topic_router.get(
    "/{topic_id}/overview",
    response_model=TopicOverview,
    summary="Fetch a single topic overview",
    description="""
    Returns the TopicOverview (topic details plus parents/children metadata) for a single topic.
    """,
)
async def get_topic_overview(
    topic_id: Annotated[str, Path(description="Topic ID")],
    service: Annotated[TopicQueryService, Depends(get_query_service)],
) -> TopicOverview:
    """Get a single topic overview.

    Args:
        topic_id: Topic ID
        service: Service dependency

    Returns:
        Topic overview with relationship metadata

    Raises:
        NotFoundError: If topic doesn't exist
    """
    try:
        return await service.get_topic_overview(topic_id)
    except SQLAlchemyNotFoundError as e:
        raise NotFoundError("Topic", topic_id) from e

