"""Repository for classifier-related entities.

This module provides repository layer for document classification,
topic suggestions, and topic assignments.
"""

from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from sqlalchemy import select

from ontology.relational.models.classifier import (
    TopicSuggestion,
    DocumentClassification,
    DocumentTopicAssignment,
)


class TopicSuggestionRepository(SQLAlchemyAsyncRepository[TopicSuggestion]):
    """Repository for persisting classifier suggestions.

    Consumers (really, the service layer) should be responsible for
    tokenizing, the db should just store the outputs along with the
    method/model used by the service for a given suggestion.
    """

    model_type = TopicSuggestion


class DocumentClassificationRepository(
    SQLAlchemyAsyncRepository[DocumentClassification]
):
    """Repository for DocumentClassification entities.

    Handles CRUD operations for document classifications and their
    associated topic assignments.
    """

    model_type = DocumentClassification

    async def add_with_topics(
        self,
        classification: DocumentClassification,
        topic_assignments: list[DocumentTopicAssignment],
    ) -> DocumentClassification:
        """Create a classification with associated topic assignments.

        This is a transactional operation - if any part fails, nothing is saved.

        Args:
            classification: The classification ORM model
            topic_assignments: List of topic assignment ORM models

        Returns:
            Persisted classification with populated ID
        """
        # Add classification
        self.session.add(classification)
        await self.session.flush()  # Get the ID

        # Add topic assignments
        for assignment in topic_assignments:
            assignment.classification_id = classification.id
            self.session.add(assignment)

        await self.session.flush()
        await self.session.refresh(classification)

        return classification

    async def get_by_document(
        self, document_id: str, document_type: str, limit: int = 10
    ) -> list[DocumentClassification]:
        """Get classification history for a document.

        Args:
            document_id: Document identifier
            document_type: Type of document
            limit: Maximum results to return

        Returns:
            List of classifications, most recent first
        """
        stmt = (
            select(DocumentClassification)
            .where(
                DocumentClassification.document_id == document_id,
                DocumentClassification.document_type == document_type,
            )
            .order_by(DocumentClassification.created_at.desc())
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_by_document(
        self, document_id: str, document_type: str
    ) -> DocumentClassification | None:
        """Get the most recent classification for a document.

        Args:
            document_id: Document identifier
            document_type: Type of document

        Returns:
            Most recent classification or None
        """
        stmt = (
            select(DocumentClassification)
            .where(
                DocumentClassification.document_id == document_id,
                DocumentClassification.document_type == document_type,
            )
            .order_by(DocumentClassification.created_at.desc())
            .limit(1)
        )

        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_with_topics(
        self, classification_id: str
    ) -> tuple[DocumentClassification, list[DocumentTopicAssignment]]:
        """Get a classification with all its topic assignments.

        Args:
            classification_id: Classification identifier

        Returns:
            Tuple of (classification, topic_assignments)
        """
        # Get classification
        classification = await self.get(classification_id)

        # Get topic assignments
        stmt = (
            select(DocumentTopicAssignment)
            .where(DocumentTopicAssignment.classification_id == classification_id)
            .order_by(DocumentTopicAssignment.rank.asc())
        )

        result = await self.session.execute(stmt)
        assignments = list(result.scalars().all())

        return classification, assignments

    async def update_feedback(
        self,
        classification_id: str,
        feedback: str,
        corrected_taxonomy_id: str | None = None,
    ) -> DocumentClassification:
        """Update user feedback on a classification.

        Args:
            classification_id: Classification to update
            feedback: Feedback value (accepted, rejected, modified)
            corrected_taxonomy_id: If modified, the correct taxonomy

        Returns:
            Updated classification
        """
        classification = await self.get(classification_id)
        classification.user_feedback = feedback

        if corrected_taxonomy_id:
            if classification.meta is None:
                classification.meta = {}
            classification.meta["corrected_taxonomy_id"] = str(corrected_taxonomy_id)

        await self.session.flush()
        await self.session.refresh(classification)

        return classification


class DocumentTopicAssignmentRepository(
    SQLAlchemyAsyncRepository[DocumentTopicAssignment]
):
    """Repository for DocumentTopicAssignment entities."""

    model_type = DocumentTopicAssignment

    async def update_feedback(
        self, assignment_id: str, feedback: str
    ) -> DocumentTopicAssignment:
        """Update user feedback on a topic assignment."""
        assignment = await self.get(assignment_id)
        assignment.user_feedback = feedback

        await self.session.flush()
        await self.session.refresh(assignment)

        return assignment


__all__ = [
    "TopicSuggestionRepository",
    "DocumentClassificationRepository",
    "DocumentTopicAssignmentRepository",
]
