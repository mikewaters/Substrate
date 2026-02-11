"""Service layer for Topic operations.

This service provides business logic for topics, including search and
discovery features. It bridges between Pydantic schemas (I/O) and domain
models (business logic).
"""

from __future__ import annotations
import logging
import re

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from ontologizer.relational.repository import (
        TopicEdgeRepository,
        TopicRepository,
    )

logger = logging.getLogger(__name__)
from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService
from sqlalchemy import select

from ontologizer.relational.models import Topic, TopicEdge, TopicClosure


from ontologizer.relational.repository import (
    TopicEdgeRepository,
    TopicRepository,
)
from ontologizer.schema import (
    TopicEdgeCreate,
)

TOKEN_PATTERN = re.compile(r"[a-z0-9]+", re.IGNORECASE)
MODEL_NAME = "simple-keyword-matcher"
MODEL_VERSION = "0.1.0"


"""
Available Service methods:
    exists
    get
    get_one
    get_one_or_none
    list
    list_and_count
    create
    create_many
    update
    update_many
    upsert
    upsert_many
    get_or_upsert
    get_and_update
    delete
    delete_many
    delete_where
"""


class TopicTaxonomyService(SQLAlchemyAsyncRepositoryService[Topic]):
    """Service for topic operations.

    This service handles topic business logic, including CRUD operations,
    search, and discovery features.

    - Built-ins should return ORM instances, like they normally would;
    - New methods should return Domain instances, wrapping calls to built-ins

    """

    repository_type = TopicRepository

    def __init__(self, **kwargs):
        """Initialize service with both Topic and TopicEdge repositories."""
        super().__init__(**kwargs)
        self._edge_repository: TopicEdgeRepository | None = None

    @property
    def edge_repository(self) -> TopicEdgeRepository:
        """Lazy-load edge repository with reference to topic repository."""
        if self._edge_repository is None:
            self._edge_repository = TopicEdgeRepository(
                topic_repo=self.repository,
                session=self.repository.session,
            )
        return self._edge_repository

    async def re_parent(self):
        """TODO"""
        return

    # ==================== Edge Operations ====================

    async def create_edge(self, data: TopicEdgeCreate) -> TopicEdge:
        """Create a topic edge (relationship).

        Args:
            data: Edge creation data

        Returns:
            Created edge ( instance)

        Raises:
            ValueError: If edge would create a cycle
        """
        # Convert Pydantic schema to ORM object
        edge_orm_input = TopicEdge(
            parent_id=data.parent_id,
            child_id=data.child_id,
            role=data.role,
            source=data.source,
            confidence=data.confidence,
            is_primary=data.is_primary,
        )
        edge_orm = await self.edge_repository.add(edge_orm_input)
        return edge_orm

    async def delete_edge(self, parent_id: str, child_id: str) -> bool:
        """Delete a topic edge.

        Args:
            parent_id: Parent topic ID
            child_id: Child topic ID

        Returns:
            True if deleted, False if not found
        """
        return await self.edge_repository.delete_edge(parent_id, child_id)

    async def get_ancestors(
        self, topic_id: str, max_depth: int | None = None
    ) -> list[Topic]:
        """Get all ancestor topics.

        Args:
            topic_id: Topic ID
            max_depth: Optional maximum depth to traverse

        Returns:
            List of ancestor topics
        """
        # Query closure table for ancestors
        conditions = [TopicClosure.descendant_id == topic_id]
        if max_depth is not None:
            conditions.append(TopicClosure.depth <= max_depth)

        statement = (
            select(Topic)
            .join(
                TopicClosure,
                Topic.id == TopicClosure.ancestor_id,
            )
            .where(*conditions)
            .where(TopicClosure.depth > 0)  # Exclude self
        )

        result = await self.repository.session.execute(statement)
        return result.scalars().all()

    async def get_descendants(
        self, topic_id: str, max_depth: int | None = None
    ) -> list[Topic]:
        """Get all descendant topics.

        Args:
            topic_id: Topic ID
            max_depth: Optional maximum depth to traverse

        Returns:
            List of descendant topics
        """
        # Query closure table for descendants
        conditions = [TopicClosure.ancestor_id == topic_id]
        if max_depth is not None:
            conditions.append(TopicClosure.depth <= max_depth)

        statement = (
            select(Topic)
            .join(
                TopicClosure,
                Topic.id == TopicClosure.descendant_id,
            )
            .where(*conditions)
            .where(TopicClosure.depth > 0)  # Exclude self
        )

        result = await self.repository.session.execute(statement)
        return result.scalars().all()
