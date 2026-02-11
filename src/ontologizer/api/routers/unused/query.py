"""Query API endpoints for topic discovery and analytics.

This module provides read-only query endpoints for searching, discovering,
and analyzing topics. All endpoints use TopicQueryService for read operations.
"""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ontologizer.api.dependencies import get_db
from ontologizer.schema import (
    TopicCountsResponse,
    TopicListResponse,
    TopicRecentListResponse,
    TopicResponse,
    TopicSearchRequest,
    TopicSummaryResponse,
)
from ontologizer.relational.services import TopicQueryService, TopicTaxonomyService


async def get_query_service(
    db: AsyncSession = Depends(get_db),
) -> AsyncGenerator[TopicQueryService, None]:
    """Get TopicQueryService dependency for read-only operations."""
    async with TopicQueryService.new(session=db) as service:
        yield service


async def get_topic_service(
    db: AsyncSession = Depends(get_db),
) -> AsyncGenerator[TopicTaxonomyService, None]:
    """Get TopicService dependency."""
    async with TopicTaxonomyService.new(session=db) as service:
        yield service


query_router = APIRouter(prefix="/topics", tags=["topics", "queries"])


# ==================== Search & Discovery ====================


@query_router.post(
    "/search",
    response_model=TopicListResponse,
    summary="Search for topics",
)
async def search_topics(
    request: TopicSearchRequest,
    service: Annotated[TopicQueryService, Depends(get_query_service)],
) -> TopicListResponse:
    """Search for topics by title or alias.

    Supports case-insensitive substring matching with optional filters
    for taxonomy and status.

    Args:
        request: Search request with query and filters
        service: Topic query service dependency

    Returns:
        Paginated list of matching topics
    """
    return await service.search_topics(request)


@query_router.get(
    "/orphans",
    response_model=list[TopicResponse],
    summary="Find orphan topics",
)
async def find_orphan_topics(
    service: Annotated[TopicQueryService, Depends(get_query_service)],
    taxonomy_id: Annotated[
        str | None, Query(description="Filter by taxonomy")
    ] = None,
) -> list[TopicResponse]:
    """Find topics with no parent relationships.

    Args:
        service: Topic query service dependency
        taxonomy_id: Optional filter by taxonomy

    Returns:
        List of orphan topics
    """
    return await service.find_orphan_topics(taxonomy_id=taxonomy_id)


@query_router.get(
    "/multi-parent",
    response_model=list[TopicResponse],
    summary="Find topics with multiple parents",
)
async def find_multi_parent_topics(
    service: Annotated[TopicQueryService, Depends(get_query_service)],
    min_parents: Annotated[
        int, Query(ge=2, description="Minimum number of parents")
    ] = 2,
    taxonomy_id: Annotated[
        str | None, Query(description="Filter by taxonomy")
    ] = None,
) -> list[TopicResponse]:
    """Find topics with multiple parent relationships.

    Args:
        service: Topic query service dependency
        min_parents: Minimum number of parents
        taxonomy_id: Optional filter by taxonomy

    Returns:
        List of topics with multiple parents
    """
    return await service.find_multi_parent_topics(
        min_parents=min_parents, taxonomy_id=taxonomy_id
    )


# ==================== Topic Analytics & Overview ====================


@query_router.get(
    "/summary",
    response_model=TopicSummaryResponse,
    summary="Aggregate topic counts by status",
)
async def get_topic_summary(
    service: Annotated[TopicTaxonomyService, Depends(get_topic_service)],
    taxonomy_id: Annotated[
        str | None, Query(description="Optional taxonomy ID")
    ] = None,
) -> TopicSummaryResponse:
    """Get topic counts grouped by status.

    Args:
        service: Topic service dependency
        taxonomy_id: Optional filter by taxonomy

    Returns:
        Topic summary with counts by status
    """
    return await service.get_topic_summary(taxonomy_id)


@query_router.get(
    "/counts",
    response_model=TopicCountsResponse,
    summary="Topic counts grouped by taxonomy",
)
async def get_topic_counts(
    service: Annotated[TopicTaxonomyService, Depends(get_topic_service)],
) -> TopicCountsResponse:
    """Get topic counts grouped by taxonomy.

    Args:
        service: Topic service dependency

    Returns:
        Topic counts by taxonomy
    """
    return await service.get_topic_counts_by_taxonomy()


@query_router.get(
    "/recent",
    response_model=TopicRecentListResponse,
    summary="Recently created topics",
)
async def get_recent_topics(
    service: Annotated[TopicTaxonomyService, Depends(get_topic_service)],
    taxonomy_id: Annotated[
        str | None, Query(description="Optional taxonomy ID")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Maximum results")] = 10,
) -> TopicRecentListResponse:
    """Get recently created topics.

    Args:
        service: Topic service dependency
        taxonomy_id: Optional filter by taxonomy
        limit: Maximum number of results

    Returns:
        List of recently created topics
    """
    return await service.get_recent_topics(taxonomy_id, limit)
