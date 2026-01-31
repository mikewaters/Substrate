from collections.abc import AsyncGenerator
from typing import Annotated

from advanced_alchemy.exceptions import NotFoundError as SQLAlchemyNotFoundError
from advanced_alchemy.filters import LimitOffset
from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ontology.api.dependencies import get_db
from ontology.api.errors import NotFoundError
from ontology.schema.taxonomy import TaxonomyCreate, TaxonomyListResponse, TaxonomyResponse, TaxonomyUpdate
from ontology.relational.services import (
    TaxonomyService,
    TopicQueryService,
)


### Taxonomy
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


@taxonomy_router.post(
    "",
    response_model=TaxonomyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new taxonomy",
)
async def create_taxonomy(
    taxonomy: TaxonomyCreate,
    service: Annotated[TaxonomyService, Depends(get_taxonomy_service)],
) -> TaxonomyResponse:
    """Create a new taxonomy.

    Args:
        taxonomy: Taxonomy creation data
        service: Taxonomy service dependency

    Returns:
        Created taxonomy

    Raises:
        ValidationError: If validation fails
    """
    return await service.create(taxonomy)


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
    "/{taxonomy_id}",
    response_model=TaxonomyResponse,
    summary="Get a taxonomy by ID",
)
async def get_taxonomy(
    taxonomy_id: Annotated[str, Path(description="Taxonomy ID")],
    service: Annotated[TaxonomyService, Depends(get_taxonomy_service)],
) -> TaxonomyResponse:
    """Get a taxonomy by ID.

    Args:
        taxonomy_id: Taxonomy ID
        service: Taxonomy service dependency

    Returns:
        Taxonomy

    Raises:
        NotFoundError: If taxonomy not found
    """
    try:
        taxonomy = await service.get(taxonomy_id)
    except SQLAlchemyNotFoundError:
        raise NotFoundError("Taxonomy", taxonomy_id)

    return service.to_schema(taxonomy, schema_type=TaxonomyResponse)


@taxonomy_router.put(
    "/{taxonomy_id}",
    response_model=TaxonomyResponse,
    summary="Update a taxonomy",
)
async def update_taxonomy(
    taxonomy_id: Annotated[str, Path(description="Taxonomy ID")],
    updates: TaxonomyUpdate,
    service: Annotated[TaxonomyService, Depends(get_taxonomy_service)],
) -> TaxonomyResponse:
    """Update a taxonomy.

    Args:
        taxonomy_id: Taxonomy ID
        updates: Fields to update
        service: Taxonomy service dependency

    Returns:
        Updated taxonomy

    Raises:
        NotFoundError: If taxonomy not found
    """

    try:
        taxonomy = await service.update(updates, taxonomy_id)
    except SQLAlchemyNotFoundError:
        raise NotFoundError("Taxonomy", taxonomy_id)

    return service.to_schema(taxonomy, schema_type=TaxonomyResponse)


@taxonomy_router.delete(
    "/{taxonomy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a taxonomy",
)
async def delete_taxonomy(
    taxonomy_id: Annotated[str, Path(description="Taxonomy ID")],
    service: Annotated[TaxonomyService, Depends(get_taxonomy_service)],
    cascade: Annotated[bool, Query(description="Delete associated topics")] = True,
) -> None:
    """Delete a taxonomy.

    Args:
        taxonomy_id: Taxonomy ID
        service: Taxonomy service dependency
        cascade: If True, delete associated topics

    Raises:
        NotFoundError: If taxonomy not found
    """
    try:
        await service.delete(taxonomy_id)
    except SQLAlchemyNotFoundError:
        raise NotFoundError("Taxonomy", taxonomy_id)


