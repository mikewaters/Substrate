"""Service layer for Catalog operations.

This service provides business logic for catalog entities, bridging between
Pydantic schemas (I/O) and ORM models.

Services extend SQLAlchemyAsyncRepositoryService which provides built-in methods:
    - create(data) -> ORM
    - get(id) -> ORM
    - get_one(filters) -> ORM
    - get_one_or_none(filters) -> ORM | None
    - list(filters) -> list[ORM]
    - list_and_count(filters, limit_offset) -> tuple[list[ORM], int]
    - update(data, id) -> ORM
    - upsert(data, id) -> ORM
    - delete(id) -> None

Use these built-in methods directly from the API layer.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from advanced_alchemy.exceptions import NotFoundError
from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService

from ontologizer.relational.models import Catalog, Purpose, Repository, Resource
from ontologizer.relational.repository.catalog import (
    CatalogRepository,
    PurposeRepository,
    RepositoryRepository,
    ResourceRepository,
)
from ontologizer.schema import (
    TopicSuggestionRequest,
)
from ontologizer.schema.catalog import (
    ApplySuggestionsRequest,
    NoteSuggestionRequest,
    NoteSuggestionResponse,
    TopicSuggestionDetail,
)
from ontologizer.relational.services.topic_suggestion import TopicSuggestionService
from ontologizer.relational.services.document_classification import (
    DocumentClassificationService,
)

if TYPE_CHECKING:
    from ontologizer.relational.models import Taxonomy
    from ontologizer.relational.services import (
        TaxonomyService,
        TopicTaxonomyService,
    )

logger = logging.getLogger(__name__)


class CatalogService(SQLAlchemyAsyncRepositoryService[Catalog, CatalogRepository]):
    """Service for catalog operations.

    Extends SQLAlchemyAsyncRepositoryService with CatalogRepository.
    Overrides create and update to handle taxonomy relationship resolution.
    """

    repository_type = CatalogRepository

    async def create(self, data: Any) -> Catalog:
        """Create a new catalog, resolving taxonomy identifiers to objects.

        Args:
            data: Catalog creation data (Pydantic or dict with taxonomies as list of identifiers)

        Returns:
            Created catalog ORM instance
        """

        # Convert Pydantic model to dict if needed
        if hasattr(data, "model_dump"):
            data_dict = data.model_dump(exclude_unset=True)
        else:
            data_dict = dict(data) if not isinstance(data, dict) else data

        # Extract and resolve taxonomy identifiers
        taxonomy_ids = data_dict.pop("taxonomies", [])
        taxonomies = await self._resolve_taxonomies(taxonomy_ids)

        # Create catalog without taxonomies field
        catalog = await super().create(data_dict)

        # Assign taxonomies relationship
        catalog.taxonomies = taxonomies

        # Flush to persist the relationship
        await self.repository.session.flush()
        await self.repository.session.refresh(catalog)

        return catalog

    async def update(self, data, item_id) -> Catalog:
        """Update a catalog, resolving taxonomy identifiers to objects if provided.

        Args:
            data: Catalog update data (Pydantic or dict with taxonomies as list of identifiers)
            item_id: ID of the catalog to update

        Returns:
            Updated catalog ORM instance
        """

        # Convert Pydantic model to dict if needed
        if hasattr(data, "model_dump"):
            data_dict = data.model_dump(exclude_unset=True)
        else:
            data_dict = dict(data) if not isinstance(data, dict) else data

        # Extract and resolve taxonomy identifiers if provided
        taxonomy_ids = data_dict.pop("taxonomies", None)

        # Update catalog without taxonomies field
        catalog = await super().update(data_dict, item_id)

        # Update taxonomies relationship if provided
        if taxonomy_ids is not None:
            taxonomies = await self._resolve_taxonomies(taxonomy_ids)
            catalog.taxonomies = taxonomies
            await self.repository.session.flush()
            await self.repository.session.refresh(catalog)

        return catalog

    async def _resolve_taxonomies(self, taxonomy_ids: list[str]) -> list[Taxonomy]:
        """Resolve taxonomy identifiers to Taxonomy ORM objects.

        Args:
            taxonomy_ids: List of taxonomy identifiers (business keys)

        Returns:
            List of Taxonomy ORM instances

        Raises:
            NotFoundError: If any taxonomy identifier is not found
        """
        from sqlalchemy import select

        taxonomies = []
        for tax_id in taxonomy_ids:
            result = await self.repository.session.execute(
                select(Taxonomy).where(Taxonomy.id == tax_id)
            )
            taxonomy = result.scalar_one_or_none()
            if not taxonomy:
                raise NotFoundError(f"Taxonomy with id '{tax_id}' not found")
            taxonomies.append(taxonomy)

        return taxonomies


class RepositoryService(SQLAlchemyAsyncRepositoryService[Repository]):
    """Service for repository operations.

    Extends SQLAlchemyAsyncRepositoryService with RepositoryRepository.
    Use built-in methods (create, get, list_and_count, update, delete) directly.
    """

    repository_type = RepositoryRepository


class PurposeService(SQLAlchemyAsyncRepositoryService[Purpose]):
    """Service for purpose operations.

    Extends SQLAlchemyAsyncRepositoryService with PurposeRepository.
    Use built-in methods (create, get, list_and_count, update, delete) directly.
    """

    repository_type = PurposeRepository


class ResourceService(SQLAlchemyAsyncRepositoryService[Resource]):
    """Service for resource operations.

    Extends SQLAlchemyAsyncRepositoryService with ResourceRepository.
    Use built-in methods (create, get, list_and_count, update, delete) directly.

    For filtered queries, pass SQLAlchemy filters to list_and_count:
        filters = [ResourceORM.catalog_id == catalog_id]
        results, total = await service.list_and_count(*filters, LimitOffset(limit, offset))
    """

    repository_type = ResourceRepository


class NoteTopicSuggestionService:
    """Service for suggesting topics for notes based on their content.

    This service orchestrates topic suggestion using multiple strategies:
    - Fast mode: Keyword-based classification (< 100ms)
    - Accurate mode: LLM-based classification (2-5s)
    - Hybrid mode: Both keyword and LLM (default)

    Dependencies:
        - ResourceService: To retrieve note content
        - ClassifierService: For keyword-based suggestions
        - DocumentClassificationService: For LLM-based suggestions
        - TaxonomyService: For taxonomy operations
        - TopicTaxonomyService: For topic operations
    """

    def __init__(
        self,
        resource_service: ResourceService,
        classifier_service: TopicSuggestionService,
        doc_classification_service: DocumentClassificationService,
        taxonomy_service: TaxonomyService,
        topic_service: TopicTaxonomyService,
    ):
        self.resource_service = resource_service
        self.classifier_service = classifier_service
        self.doc_classification_service = doc_classification_service
        self.taxonomy_service = taxonomy_service
        self.topic_service = topic_service

    async def suggest_topics_for_note(
        self,
        note_id: str,
        request: NoteSuggestionRequest,
    ) -> NoteSuggestionResponse:
        """Suggest topics for a note based on its content.

        Args:
            note_id: ID of the note/resource
            request: Suggestion request with mode and options

        Returns:
            Suggestion response with existing and new topic proposals

        Raises:
            NotFoundError: If note doesn't exist
            ValueError: If note has no content
        """
        # Get the note/resource
        try:
            note = await self.resource_service.get(note_id)
        except NotFoundError as ex:
            raise NotFoundError(f"Resource with ID {note_id} not found") from ex

        # Extract content from note
        content = self._extract_note_content(note)
        if not content:
            raise ValueError("Note has no content to classify")

        logger.info(
            f"Suggesting topics for note {note_id} (mode={request.mode}, "
            f"content_length={len(content)})"
        )

        # Determine taxonomy to use
        taxonomy_id = request.taxonomy_hint
        if not taxonomy_id:
            # Auto-detect taxonomy (for now, use first available)
            # TODO: Implement taxonomy auto-detection in Phase 2
            taxonomies, _ = await self.taxonomy_service.list_and_count(limit=1)
            if not taxonomies:
                raise ValueError("No taxonomies available for classification")
            taxonomy_id = taxonomies[0].id
            logger.info(f"Auto-selected taxonomy: {taxonomy_id}")

        # Execute suggestion based on mode
        existing_topics: list[TopicSuggestionDetail] = []

        if request.mode == "fast":
            existing_topics = await self._suggest_fast(content, taxonomy_id)
        elif request.mode == "accurate":
            existing_topics = await self._suggest_accurate(
                content, taxonomy_id, note.title
            )
        elif request.mode == "hybrid":
            existing_topics = await self._suggest_hybrid(
                content, taxonomy_id, note.title
            )
        else:
            raise ValueError(f"Invalid mode: {request.mode}")

        # Phase 3: New topic suggestions
        new_topic_suggestions = []
        if request.include_new_topics:
            # Only suggest new topics if we have few good matches
            good_matches = [t for t in existing_topics if t.confidence >= 0.6]
            if len(good_matches) < 3:
                logger.info(
                    f"Few good matches ({len(good_matches)}), suggesting new topics"
                )
                from ontologizer.schema.classifier import TopicSuggestion

                # Convert existing topics to TopicSuggestion for context
                existing_topic_suggestions = [
                    TopicSuggestion(
                        topic_id=t.topic_id,
                        topic_identifier=t.topic_identifier,
                        topic_title=t.topic_title,
                        topic_description="",
                        confidence=t.confidence,
                        rank=i + 1,
                        reasoning=t.reasoning or "",
                    )
                    for i, t in enumerate(existing_topics)
                ]
                new_topic_suggestions = (
                    await self.doc_classification_service.suggest_new_topics(
                        content=content,
                        taxonomy_id=taxonomy_id,
                        existing_suggestions=existing_topic_suggestions,
                        max_proposals=3,
                    )
                )

        return NoteSuggestionResponse(
            existing_topics=existing_topics,
            new_topic_suggestions=new_topic_suggestions,
            taxonomy_suggestions=[],
        )

    async def _suggest_fast(
        self,
        content: str,
        taxonomy_id: str,
    ) -> list[TopicSuggestionDetail]:
        """Fast keyword-based topic suggestion.

        Args:
            content: Note content to classify
            taxonomy_id: Taxonomy to scope suggestions

        Returns:
            List of topic suggestions
        """
        # Call ClassifierService for keyword-based suggestions
        classifier_request = TopicSuggestionRequest(
            text=content,
            taxonomy_id=taxonomy_id,
            limit=10,
            min_confidence=0.1,
        )

        classifier_response = await self.classifier_service.suggest_topics(
            classifier_request
        )

        # Get taxonomy details for response
        taxonomy = await self.taxonomy_service.get(taxonomy_id)

        # Convert to TopicSuggestionDetail format
        details: list[TopicSuggestionDetail] = []
        for suggestion in classifier_response.suggestions:
            # Extract matched phrases from metadata
            matched_phrases = suggestion.metadata.get("matched_phrases", [])

            detail = TopicSuggestionDetail(
                topic_id=suggestion.topic_id,
                topic_title=suggestion.title,
                topic_identifier=f"{taxonomy.id}:{suggestion.slug}",
                taxonomy_title=taxonomy.title,
                taxonomy_id=taxonomy_id,
                confidence=suggestion.confidence,
                reasoning=None,  # Keyword classifier doesn't provide reasoning
                matched_phrases=matched_phrases,
                source="keyword",
            )
            details.append(detail)

        logger.info(f"Fast mode returned {len(details)} suggestions")
        return details

    async def _suggest_accurate(
        self,
        content: str,
        taxonomy_id: str,
        note_title: str,
    ) -> list[TopicSuggestionDetail]:
        """Accurate LLM-based topic suggestion.

        Args:
            content: Note content to classify
            taxonomy_id: Taxonomy to scope suggestions
            note_title: Title of the note for better classification

        Returns:
            List of topic suggestions
        """
        from ontologizer.schema.classifier import DocumentClassificationRequest

        # Prepare content with title emphasis
        enhanced_content = f"Title: {note_title}\n\n{content}"

        # Call DocumentClassificationService for LLM-based classification
        classification_request = DocumentClassificationRequest(
            content=enhanced_content,
            document_type="Note",
            taxonomy_hint=taxonomy_id,
            max_topics=10,
            min_confidence=0.3,
            store_result=False,  # Don't persist note classification results
        )

        classification_response = (
            await self.doc_classification_service.classify_document(
                classification_request
            )
        )

        # Get taxonomy details for response
        taxonomy = await self.taxonomy_service.get(taxonomy_id)

        # Convert to TopicSuggestionDetail format
        details: list[TopicSuggestionDetail] = []
        for topic_suggestion in classification_response.suggested_topics:
            detail = TopicSuggestionDetail(
                topic_id=topic_suggestion.topic_id,
                topic_title=topic_suggestion.topic_title,
                topic_identifier=topic_suggestion.topic_identifier,
                taxonomy_title=taxonomy.title,
                taxonomy_id=taxonomy_id,
                confidence=topic_suggestion.confidence,
                reasoning=topic_suggestion.reasoning,
                matched_phrases=[],  # LLM doesn't provide phrase matching
                source="llm",
            )
            details.append(detail)

        logger.info(f"Accurate mode returned {len(details)} suggestions")
        return details

    async def _suggest_hybrid(
        self,
        content: str,
        taxonomy_id: str,
        note_title: str,
    ) -> list[TopicSuggestionDetail]:
        """Hybrid topic suggestion combining keyword and LLM approaches.

        This runs keyword classification immediately and LLM classification,
        then merges and deduplicates the results.

        Args:
            content: Note content to classify
            taxonomy_id: Taxonomy to scope suggestions
            note_title: Title of the note

        Returns:
            List of topic suggestions, merged and ranked
        """
        # Run both classifiers
        keyword_suggestions = await self._suggest_fast(content, taxonomy_id)
        llm_suggestions = await self._suggest_accurate(content, taxonomy_id, note_title)

        # Merge and deduplicate by topic_id
        suggestions_by_id: dict[uuid.UUID, TopicSuggestionDetail] = {}

        # Add keyword suggestions first
        for suggestion in keyword_suggestions:
            suggestions_by_id[suggestion.topic_id] = suggestion

        # Add or merge LLM suggestions
        for llm_suggestion in llm_suggestions:
            if llm_suggestion.topic_id in suggestions_by_id:
                # Topic suggested by both - take the higher confidence and combine data
                keyword_suggestion = suggestions_by_id[llm_suggestion.topic_id]

                # Use weighted average favoring LLM confidence (70% LLM, 30% keyword)
                combined_confidence = (
                    llm_suggestion.confidence * 0.7
                    + keyword_suggestion.confidence * 0.3
                )

                # Create merged suggestion
                suggestions_by_id[llm_suggestion.topic_id] = TopicSuggestionDetail(
                    topic_id=llm_suggestion.topic_id,
                    topic_title=llm_suggestion.topic_title,
                    topic_identifier=llm_suggestion.topic_identifier,
                    taxonomy_title=llm_suggestion.taxonomy_title,
                    taxonomy_id=llm_suggestion.taxonomy_id,
                    confidence=min(1.0, combined_confidence),  # Cap at 1.0
                    reasoning=llm_suggestion.reasoning,  # Use LLM reasoning
                    matched_phrases=keyword_suggestion.matched_phrases,  # Keep keyword phrases
                    source="keyword,llm",  # type: ignore # Indicate both sources
                )
            else:
                # Only LLM suggested this topic
                suggestions_by_id[llm_suggestion.topic_id] = llm_suggestion

        # Sort by confidence and return
        merged_suggestions = sorted(
            suggestions_by_id.values(),
            key=lambda s: s.confidence,
            reverse=True,
        )

        logger.info(f"Hybrid mode returned {len(merged_suggestions)} suggestions")
        return merged_suggestions

    async def apply_topic_suggestions(
        self,
        note_id: str,
        request: ApplySuggestionsRequest,
    ) -> Resource:
        """Apply topic suggestions to a note.

        This updates the note's related_topics field with the selected topics.

        Args:
            note_id: ID of the note/resource
            request: Request with selected topic IDs and new topics to create

        Returns:
            Updated resource

        Raises:
            NotFoundError: If note doesn't exist
        """
        # Get the note
        try:
            note = await self.resource_service.get(note_id)
        except NotFoundError as ex:
            raise NotFoundError(f"Resource with ID {note_id} not found") from ex

        # Phase 3: Handle new topic creation
        newly_created_topic_ids = []
        if request.new_topics_to_create:
            from ontologizer.schema import TopicCreate

            for new_topic in request.new_topics_to_create:
                # Create the topic
                topic_data = TopicCreate(
                    title=new_topic.title,
                    description=new_topic.description,
                    taxonomy_id=new_topic.taxonomy_id,
                    status="active",
                )
                created_topic = await self.topic_service.create(topic_data)

                # Create edges to parent topics
                for parent_id in new_topic.parent_ids:
                    await self.topic_service.create_edge(
                        parent_id=parent_id,
                        child_id=created_topic.id,
                        edge_type="broader",
                    )

                newly_created_topic_ids.append(created_topic.id)
                logger.info(
                    f"Created new topic: {created_topic.title} ({created_topic.id})"
                )

        # Get all topic identifiers (existing + newly created)
        all_topic_ids = set(request.selected_topic_ids) | set(newly_created_topic_ids)

        # Convert topic UUIDs to ids for the related_topics field
        topic_identifiers = []
        for topic_id in all_topic_ids:
            topic = await self.topic_service.get(topic_id)
            if topic:
                topic_identifiers.append(topic.id)

        # Update the note's related_topics field
        note.related_topics = topic_identifiers

        # Persist the changes
        updated_note = await self.resource_service.update(note, note_id)

        logger.info(f"Applied {len(topic_identifiers)} topics to note {note_id}")

        return updated_note

    def _extract_note_content(self, note: Resource) -> str:
        """Extract content from a note/resource for classification.

        Args:
            note: The note/resource ORM instance

        Returns:
            Combined content from title and description
        """
        parts = []

        if note.title:
            parts.append(note.title)

        if note.description:
            parts.append(note.description)

        return " ".join(parts)
