"""FastAPI routes for catalog endpoints."""

from collections.abc import AsyncGenerator
from typing import Annotated

from advanced_alchemy.filters import LimitOffset
from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ontology.api.dependencies import get_db
from ontology.api.errors import NotFoundError
from ontology.relational.models import Resource as ResourceORM
from ontology.relational.repository import (
    DocumentClassificationRepository,
    TopicRepository,
    TopicSuggestionRepository,
)
from ontology.relational.repository import TaxonomyRepository
from ontology.schema.catalog import (
    ApplySuggestionsRequest,
    CatalogCreate,
    CatalogListResponse,
    CatalogResponse,
    CatalogUpdate,
    NoteSuggestionRequest,
    NoteSuggestionResponse,
    PurposeCreate,
    PurposeListResponse,
    PurposeResponse,
    PurposeUpdate,
    RepositoryCreate,
    RepositoryListResponse,
    RepositoryResponse,
    RepositoryUpdate,
    ResourceCreate,
    ResourceListResponse,
    ResourceResponse,
    ResourceUpdate,
)
from ontology.relational.services import (
    TaxonomyService,
    TopicTaxonomyService,
)
from ontology.relational.services.catalog import (
    CatalogService,
    NoteTopicSuggestionService,
    PurposeService,
    RepositoryService,
    ResourceService,
)
from ontology.relational.services import TopicSuggestionService
from ontology.relational.services.document_classification import (
    DocumentClassificationService,
)


# Catalog service dependency
async def get_catalog_service(
    db: AsyncSession = Depends(get_db),
) -> AsyncGenerator[CatalogService, None]:
    """Get CatalogService dependency."""
    async with CatalogService.new(session=db) as service:
        yield service


# Repository service dependency
async def get_repository_service(
    db: AsyncSession = Depends(get_db),
) -> AsyncGenerator[RepositoryService, None]:
    """Get RepositoryService dependency."""
    async with RepositoryService.new(session=db) as service:
        yield service


# Purpose service dependency
async def get_purpose_service(
    db: AsyncSession = Depends(get_db),
) -> AsyncGenerator[PurposeService, None]:
    """Get PurposeService dependency."""
    async with PurposeService.new(session=db) as service:
        yield service


# Resource service dependency
async def get_resource_service(
    db: AsyncSession = Depends(get_db),
) -> AsyncGenerator[ResourceService, None]:
    """Get ResourceService dependency."""
    async with ResourceService.new(session=db) as service:
        yield service


# NoteTopicSuggestionService dependency
async def get_note_topic_suggestion_service(
    db: AsyncSession = Depends(get_db),
) -> AsyncGenerator[NoteTopicSuggestionService, None]:
    """Get NoteTopicSuggestionService dependency with all required services."""
    async with (
        ResourceService.new(session=db) as resource_service,
        TopicSuggestionService.new(
            session=db, repository_type=TopicSuggestionRepository
        ) as classifier_service,
        TaxonomyService.new(
            session=db, repository_type=TaxonomyRepository
        ) as taxonomy_service,
        TopicTaxonomyService.new(
            session=db, repository_type=TopicRepository
        ) as topic_service,
    ):
        # Create DocumentClassificationService (not an async context manager)
        doc_classification_repo = DocumentClassificationRepository(session=db)
        taxonomy_repo = TaxonomyRepository(session=db)
        topic_repo = TopicRepository(session=db)

        doc_classification_service = DocumentClassificationService(
            classification_repo=doc_classification_repo,
            taxonomy_repo=taxonomy_repo,
            topic_repo=topic_repo,
        )

        # Create and yield the NoteTopicSuggestionService
        service = NoteTopicSuggestionService(
            resource_service=resource_service,
            classifier_service=classifier_service,
            doc_classification_service=doc_classification_service,
            taxonomy_service=taxonomy_service,
            topic_service=topic_service,
        )
        yield service


# Catalog router
catalog_router = APIRouter(prefix="/catalogs", tags=["catalogs"])


@catalog_router.post(
    "",
    response_model=CatalogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new catalog",
)
async def create_catalog(
    catalog: CatalogCreate,
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> CatalogResponse:
    """Create a new catalog.

    Args:
        catalog: Catalog creation data
        service: Catalog service dependency

    Returns:
        Created catalog
    """
    catalog_orm = await service.create(catalog)
    return CatalogResponse.model_validate(catalog_orm)


@catalog_router.get(
    "",
    response_model=CatalogListResponse,
    summary="List catalogs",
)
async def list_catalogs(
    service: Annotated[CatalogService, Depends(get_catalog_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CatalogListResponse:
    """List catalogs with pagination.

    Args:
        service: Catalog service dependency
        limit: Maximum number of results (1-100)
        offset: Number of results to skip

    Returns:
        Paginated list of catalogs
    """
    results, total = await service.list_and_count(LimitOffset(limit, offset))
    items = [CatalogResponse.model_validate(r) for r in results]
    return CatalogListResponse(items=items, total=total, limit=limit, offset=offset)


@catalog_router.get(
    "/{catalog_id}",
    response_model=CatalogResponse,
    summary="Get a catalog by ID",
)
async def get_catalog(
    catalog_id: Annotated[str, Path(description="Catalog ID")],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> CatalogResponse:
    """Get a catalog by ID.

    Args:
        catalog_id: Catalog ID
        service: Catalog service dependency

    Returns:
        Catalog

    Raises:
        NotFoundError: If catalog not found
    """
    try:
        catalog_orm = await service.get(catalog_id)
        return CatalogResponse.model_validate(catalog_orm)
    except Exception:
        raise NotFoundError("Catalog", catalog_id)


@catalog_router.put(
    "/{catalog_id}",
    response_model=CatalogResponse,
    summary="Update a catalog",
)
async def update_catalog(
    catalog_id: Annotated[str, Path(description="Catalog ID")],
    updates: CatalogUpdate,
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> CatalogResponse:
    """Update a catalog.

    Args:
        catalog_id: Catalog ID
        updates: Fields to update
        service: Catalog service dependency

    Returns:
        Updated catalog

    Raises:
        NotFoundError: If catalog not found
    """
    try:
        catalog_orm = await service.update(updates, catalog_id)
        return CatalogResponse.model_validate(catalog_orm)
    except Exception:
        raise NotFoundError("Catalog", catalog_id)


@catalog_router.delete(
    "/{catalog_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a catalog",
)
async def delete_catalog(
    catalog_id: Annotated[str, Path(description="Catalog ID")],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> None:
    """Delete a catalog.

    Args:
        catalog_id: Catalog ID
        service: Catalog service dependency

    Raises:
        NotFoundError: If catalog not found
    """
    try:
        await service.delete(catalog_id)
    except Exception:
        raise NotFoundError("Catalog", catalog_id)


# Repository router
repository_router = APIRouter(prefix="/repositories", tags=["repositories"])


@repository_router.post(
    "",
    response_model=RepositoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new repository",
)
async def create_repository(
    repository: RepositoryCreate,
    service: Annotated[RepositoryService, Depends(get_repository_service)],
) -> RepositoryResponse:
    """Create a new repository.

    Args:
        repository: Repository creation data
        service: Repository service dependency

    Returns:
        Created repository
    """
    repository_orm = await service.create(repository)
    return RepositoryResponse.model_validate(repository_orm)


@repository_router.get(
    "",
    response_model=RepositoryListResponse,
    summary="List repositories",
)
async def list_repositories(
    service: Annotated[RepositoryService, Depends(get_repository_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RepositoryListResponse:
    """List repositories with pagination.

    Args:
        service: Repository service dependency
        limit: Maximum number of results (1-100)
        offset: Number of results to skip

    Returns:
        Paginated list of repositories
    """
    results, total = await service.list_and_count(LimitOffset(limit, offset))
    items = [RepositoryResponse.model_validate(r) for r in results]
    return RepositoryListResponse(items=items, total=total, limit=limit, offset=offset)


@repository_router.get(
    "/{repository_id}",
    response_model=RepositoryResponse,
    summary="Get a repository by ID",
)
async def get_repository(
    repository_id: Annotated[str, Path(description="Repository ID")],
    service: Annotated[RepositoryService, Depends(get_repository_service)],
) -> RepositoryResponse:
    """Get a repository by ID.

    Args:
        repository_id: Repository ID
        service: Repository service dependency

    Returns:
        Repository

    Raises:
        NotFoundError: If repository not found
    """
    try:
        repository_orm = await service.get(repository_id)
        return RepositoryResponse.model_validate(repository_orm)
    except Exception:
        raise NotFoundError("Repository", repository_id)


@repository_router.put(
    "/{repository_id}",
    response_model=RepositoryResponse,
    summary="Update a repository",
)
async def update_repository(
    repository_id: Annotated[str, Path(description="Repository ID")],
    updates: RepositoryUpdate,
    service: Annotated[RepositoryService, Depends(get_repository_service)],
) -> RepositoryResponse:
    """Update a repository.

    Args:
        repository_id: Repository ID
        updates: Fields to update
        service: Repository service dependency

    Returns:
        Updated repository

    Raises:
        NotFoundError: If repository not found
    """
    try:
        repository_orm = await service.update(updates, repository_id)
        return RepositoryResponse.model_validate(repository_orm)
    except Exception:
        raise NotFoundError("Repository", repository_id)


@repository_router.delete(
    "/{repository_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a repository",
)
async def delete_repository(
    repository_id: Annotated[str, Path(description="Repository ID")],
    service: Annotated[RepositoryService, Depends(get_repository_service)],
) -> None:
    """Delete a repository.

    Args:
        repository_id: Repository ID
        service: Repository service dependency

    Raises:
        NotFoundError: If repository not found
    """
    try:
        await service.delete(repository_id)
    except Exception:
        raise NotFoundError("Repository", repository_id)


# Purpose router
purpose_router = APIRouter(prefix="/purposes", tags=["purposes"])


@purpose_router.post(
    "",
    response_model=PurposeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new purpose",
)
async def create_purpose(
    purpose: PurposeCreate,
    service: Annotated[PurposeService, Depends(get_purpose_service)],
) -> PurposeResponse:
    """Create a new purpose.

    Args:
        purpose: Purpose creation data
        service: Purpose service dependency

    Returns:
        Created purpose
    """
    purpose_orm = await service.create(purpose)
    return PurposeResponse.model_validate(purpose_orm)


@purpose_router.get(
    "",
    response_model=PurposeListResponse,
    summary="List purposes",
)
async def list_purposes(
    service: Annotated[PurposeService, Depends(get_purpose_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PurposeListResponse:
    """List purposes with pagination.

    Args:
        service: Purpose service dependency
        limit: Maximum number of results (1-100)
        offset: Number of results to skip

    Returns:
        Paginated list of purposes
    """
    results, total = await service.list_and_count(LimitOffset(limit, offset))
    items = [PurposeResponse.model_validate(r) for r in results]
    return PurposeListResponse(items=items, total=total, limit=limit, offset=offset)


@purpose_router.get(
    "/{purpose_id}",
    response_model=PurposeResponse,
    summary="Get a purpose by ID",
)
async def get_purpose(
    purpose_id: Annotated[str, Path(description="Purpose ID")],
    service: Annotated[PurposeService, Depends(get_purpose_service)],
) -> PurposeResponse:
    """Get a purpose by ID.

    Args:
        purpose_id: Purpose ID
        service: Purpose service dependency

    Returns:
        Purpose

    Raises:
        NotFoundError: If purpose not found
    """
    try:
        purpose_orm = await service.get(purpose_id)
        return PurposeResponse.model_validate(purpose_orm)
    except Exception:
        raise NotFoundError("Purpose", purpose_id)


@purpose_router.put(
    "/{purpose_id}",
    response_model=PurposeResponse,
    summary="Update a purpose",
)
async def update_purpose(
    purpose_id: Annotated[str, Path(description="Purpose ID")],
    updates: PurposeUpdate,
    service: Annotated[PurposeService, Depends(get_purpose_service)],
) -> PurposeResponse:
    """Update a purpose.

    Args:
        purpose_id: Purpose ID
        updates: Fields to update
        service: Purpose service dependency

    Returns:
        Updated purpose

    Raises:
        NotFoundError: If purpose not found
    """
    try:
        purpose_orm = await service.update(updates, purpose_id)
        return PurposeResponse.model_validate(purpose_orm)
    except Exception:
        raise NotFoundError("Purpose", purpose_id)


@purpose_router.delete(
    "/{purpose_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a purpose",
)
async def delete_purpose(
    purpose_id: Annotated[str, Path(description="Purpose ID")],
    service: Annotated[PurposeService, Depends(get_purpose_service)],
) -> None:
    """Delete a purpose.

    Args:
        purpose_id: Purpose ID
        service: Purpose service dependency

    Raises:
        NotFoundError: If purpose not found
    """
    try:
        await service.delete(purpose_id)
    except Exception:
        raise NotFoundError("Purpose", purpose_id)


# Resource router
resource_router = APIRouter(prefix="/resources", tags=["resources"])


@resource_router.post(
    "",
    response_model=ResourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new resource",
)
async def create_resource(
    resource: ResourceCreate,
    service: Annotated[ResourceService, Depends(get_resource_service)],
) -> ResourceResponse:
    """Create a new resource.

    Args:
        resource: Resource creation data
        service: Resource service dependency

    Returns:
        Created resource
    """
    resource_orm = await service.create(resource)
    return ResourceResponse.model_validate(resource_orm)


@resource_router.get(
    "",
    response_model=ResourceListResponse,
    summary="List resources",
)
async def list_resources(
    service: Annotated[ResourceService, Depends(get_resource_service)],
    catalog_id: Annotated[
        str | None, Query(description="Filter by catalog ID")
    ] = None,
    repository_id: Annotated[
        str | None, Query(description="Filter by repository ID")
    ] = None,
    resource_type: Annotated[
        str | None, Query(description="Filter by resource type")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ResourceListResponse:
    """List resources with optional filters and pagination.

    Args:
        service: Resource service dependency
        catalog_id: Optional catalog ID filter
        repository_id: Optional repository ID filter
        resource_type: Optional resource type filter
        limit: Maximum number of results (1-100)
        offset: Number of results to skip

    Returns:
        Paginated list of resources
    """
    # Build filters
    filters = []
    if catalog_id:
        filters.append(ResourceORM.catalog_id == catalog_id)
    if repository_id:
        filters.append(ResourceORM.repository_id == repository_id)
    if resource_type:
        filters.append(ResourceORM.resource_type == resource_type)

    # Call service with filters
    if filters:
        results, total = await service.list_and_count(
            *filters, LimitOffset(limit, offset)
        )
    else:
        results, total = await service.list_and_count(LimitOffset(limit, offset))

    items = [ResourceResponse.model_validate(r) for r in results]
    return ResourceListResponse(items=items, total=total, limit=limit, offset=offset)


@resource_router.get(
    "/{resource_id}",
    response_model=ResourceResponse,
    summary="Get a resource by ID",
)
async def get_resource(
    resource_id: Annotated[str, Path(description="Resource ID")],
    service: Annotated[ResourceService, Depends(get_resource_service)],
) -> ResourceResponse:
    """Get a resource by ID.

    Args:
        resource_id: Resource ID
        service: Resource service dependency

    Returns:
        Resource

    Raises:
        NotFoundError: If resource not found
    """
    try:
        resource_orm = await service.get(resource_id)
        return ResourceResponse.model_validate(resource_orm)
    except Exception:
        raise NotFoundError("Resource", resource_id)


@resource_router.put(
    "/{resource_id}",
    response_model=ResourceResponse,
    summary="Update a resource",
)
async def update_resource(
    resource_id: Annotated[str, Path(description="Resource ID")],
    updates: ResourceUpdate,
    service: Annotated[ResourceService, Depends(get_resource_service)],
) -> ResourceResponse:
    """Update a resource.

    Args:
        resource_id: Resource ID
        updates: Fields to update
        service: Resource service dependency

    Returns:
        Updated resource

    Raises:
        NotFoundError: If resource not found
    """
    try:
        resource_orm = await service.update(updates, resource_id)
        return ResourceResponse.model_validate(resource_orm)
    except Exception:
        raise NotFoundError("Resource", resource_id)


@resource_router.delete(
    "/{resource_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a resource",
)
async def delete_resource(
    resource_id: Annotated[str, Path(description="Resource ID")],
    service: Annotated[ResourceService, Depends(get_resource_service)],
) -> None:
    """Delete a resource.

    Args:
        resource_id: Resource ID
        service: Resource service dependency

    Raises:
        NotFoundError: If resource not found
    """
    try:
        await service.delete(resource_id)
    except Exception:
        raise NotFoundError("Resource", resource_id)


# Note Topic Suggestion Endpoints (FEAT-006)


@resource_router.post(
    "/{resource_id}/suggest-topics",
    response_model=NoteSuggestionResponse,
    summary="Suggest topics for a note",
    tags=["resources", "topics"],
)
async def suggest_topics_for_note(
    resource_id: Annotated[str, Path(description="Resource/Note ID")],
    request: NoteSuggestionRequest,
    service: Annotated[
        NoteTopicSuggestionService, Depends(get_note_topic_suggestion_service)
    ],
) -> NoteSuggestionResponse:
    """Suggest topics for a note based on its content.

    This endpoint analyzes the note's title and description to suggest
    relevant topics. It supports three modes:

    - **fast**: Keyword-based classification (< 100ms) - Quick phrase matching
    - **accurate**: LLM-based classification (2-5s) - Deep semantic analysis with reasoning
    - **hybrid**: Both keyword and LLM (default) - Combines both approaches for best results

    Args:
        resource_id: ID of the note/resource
        request: Suggestion request with mode and options
        service: Note topic suggestion service dependency

    Returns:
        Suggestion response with existing topics and new topic proposals

    Raises:
        NotFoundError: If resource not found
        ValueError: If resource has no content or no taxonomies available
    """
    try:
        return await service.suggest_topics_for_note(resource_id, request)
    except Exception as e:
        if "not found" in str(e).lower():
            raise NotFoundError("Resource", resource_id)
        raise


@resource_router.post(
    "/{resource_id}/apply-suggestions",
    response_model=ResourceResponse,
    summary="Apply topic suggestions to a note",
    tags=["resources", "topics"],
)
async def apply_topic_suggestions(
    resource_id: Annotated[str, Path(description="Resource/Note ID")],
    request: ApplySuggestionsRequest,
    service: Annotated[
        NoteTopicSuggestionService, Depends(get_note_topic_suggestion_service)
    ],
) -> ResourceResponse:
    """Apply topic suggestions to a note.

    This updates the note's related_topics field with the selected topics
    and optionally creates new topics.

    Args:
        resource_id: ID of the note/resource
        request: Request with selected topic IDs and new topics to create
        service: Note topic suggestion service dependency

    Returns:
        Updated resource with applied topics

    Raises:
        NotFoundError: If resource not found
    """
    try:
        updated_resource = await service.apply_topic_suggestions(resource_id, request)
        return ResourceResponse.model_validate(updated_resource)
    except Exception as e:
        if "not found" in str(e).lower():
            raise NotFoundError("Resource", resource_id)
        raise
