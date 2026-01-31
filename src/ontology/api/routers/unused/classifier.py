from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ontology.api.dependencies import get_db
from ontology.relational.repository import TaxonomyRepository
from ontology.schema.classifier import (
    ClassificationHistoryResponse,
    DocumentClassificationRequest,
    DocumentClassificationResponse,
    FeedbackRequest,
    ParentSuggestion,
    ParentSuggestionRequest,
    TopicSuggestionRequest,
    TopicSuggestionResponse,
)
from ontology.relational.services import TopicSuggestionService
from ontology.relational.services.document_classification import (
    DocumentClassificationService,
)


### Classifier
async def get_classifier_service(
    db: AsyncSession = Depends(get_db),
) -> AsyncGenerator[TopicSuggestionService, None]:
    """Get ClassifierService dependency."""
    async with TopicSuggestionService.new(session=db) as service:
        yield service


async def get_classification_service(
    db: AsyncSession = Depends(get_db),
) -> DocumentClassificationService:
    """Get DocumentClassificationService dependency."""
    from ontology.relational.repository import (
        TopicRepository,
    )
    from ontology.relational.repository.classifier import (
        DocumentClassificationRepository,
    )

    classification_repo = DocumentClassificationRepository(session=db)
    taxonomy_repo = TaxonomyRepository(session=db)
    topic_repo = TopicRepository(session=db)

    return DocumentClassificationService(
        classification_repo=classification_repo,
        taxonomy_repo=taxonomy_repo,
        topic_repo=topic_repo,
    )


classifier_router = APIRouter(prefix="/classifier", tags=["classifier"])
classification_router = APIRouter(prefix="/classification", tags=["classification"])


@classifier_router.post(
    "/suggestions",
    response_model=TopicSuggestionResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate topic suggestions for input text",
)
async def suggest_topics(
    request: TopicSuggestionRequest,
    service: Annotated[TopicSuggestionService, Depends(get_classifier_service)],
) -> TopicSuggestionResponse:
    """Return ranked topic suggestions for the supplied text."""
    return await service.suggest_topics(request)


@classification_router.post(
    "/classify",
    response_model=DocumentClassificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Classify document into taxonomy and topics",
    description="""
    Classify document content into an appropriate taxonomy and suggest relevant topics.

    This endpoint performs a two-stage LLM-based classification:
    1. Analyzes content to suggest which taxonomy it belongs to
    2. Suggests relevant topics within the selected taxonomy

    The classification results can optionally be persisted for historical tracking.
    """,
)
async def classify_document(
    request: DocumentClassificationRequest,
    service: Annotated[
        DocumentClassificationService, Depends(get_classification_service)
    ],
) -> DocumentClassificationResponse:
    """Classify a document into taxonomy and topics."""
    try:
        return await service.classify_document(request)
    except ValueError as e:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception:
        import logging

        logger = logging.getLogger(__name__)
        logger.exception("Classification failed")
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Classification failed due to internal error",
        )


@classification_router.get(
    "/history/{document_id}",
    response_model=ClassificationHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get classification history for a document",
)
async def get_classification_history(
    document_id: str,
    service: Annotated[
        DocumentClassificationService, Depends(get_classification_service)
    ],
    document_type: str = Query(..., description="Type of document"),
    limit: int = Query(10, description="Maximum results"),
) -> ClassificationHistoryResponse:
    """Retrieve historical classification results for a document."""
    classifications = await service.get_classification_history(
        document_id=document_id,
        document_type=document_type,
        limit=limit,
    )

    return ClassificationHistoryResponse(
        document_id=document_id,
        document_type=document_type,
        classifications=classifications,
        total=len(classifications),
    )


@classification_router.post(
    "/feedback",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Submit feedback on classification results",
)
async def submit_feedback(
    request: FeedbackRequest,
    service: Annotated[
        DocumentClassificationService, Depends(get_classification_service)
    ],
) -> None:
    """Record user feedback to improve future classifications."""
    await service.submit_feedback(request)


# ==================== Parent Suggestion (FEAT-006 Phase 4) ====================


@classifier_router.post(
    "/suggest-parents/{topic_id}",
    response_model=list[ParentSuggestion],
    summary="Suggest parent topics",
    tags=["classifier", "ai"],
)
async def suggest_parent_topics(
    topic_id: Annotated[str, Path(description="Topic ID")],
    request: ParentSuggestionRequest,
    service: Annotated[
        DocumentClassificationService, Depends(get_classification_service)
    ],
) -> list[ParentSuggestion]:
    """Suggest parent topics for a topic using LLM analysis.

    This endpoint uses AI to analyze the topic and suggest appropriate
    parent topics (broader concepts) from the same taxonomy.

    Args:
        topic_id: ID of the topic to find parents for
        request: Optional list of candidate parent IDs
        service: Document classification service dependency

    Returns:
        List of parent suggestions with confidence scores and reasoning

    Raises:
        NotFoundError: If topic not found
    """
    # Get parent suggestions
    suggestions = await service.suggest_parent_topics(
        topic_id=topic_id,
        candidate_parent_ids=request.candidate_parent_ids,
        max_suggestions=5,
    )

    return suggestions


__all__ = [
    "classifier_router",
    "classification_router",
    "get_classifier_service",
    "get_classification_service",
]
