"""Query service layer for read-only Topic operations.

This service provides read-only query operations for topics, including search,
discovery, and relationship analysis features. It separates query operations
from command operations in the TopicTaxonomyService.

Implementation:
- This module exposes "its own" schema, rather than returning ORM instances
and expecting the client to cast them using `service.to+schema(obj, schema_type)`
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ontologizer.relational.repository import (
        TopicRepository,
    )

logger = logging.getLogger(__name__)

from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService
from sqlalchemy import and_, func, or_, select

from ontologizer.relational.models import Topic, TopicEdge

from ontologizer.relational.repository import (
    TopicRepository,
)
from ontologizer.schema import (
    TopicListResponse,
    TopicOverview,
    TopicOverviewListResponse,
    TopicRelationshipRef,
    TopicResponse,
    TopicSearchRequest,
)


class TopicQueryService(SQLAlchemyAsyncRepositoryService[Topic]):
    """Service for read-only topic query operations.

    This service handles topic query business logic, including search,
    discovery, and relationship analysis features. All methods in this
    service are read-only and do not modify database state.
    """

    repository_type = TopicRepository

    async def find_orphan_topics(
        self, taxonomy_id: str | None = None
    ) -> list[TopicResponse]:
        """Find topics with no parent relationships.

        An orphan topic has no incoming edges (no parents).

        Args:
            taxonomy_id: Optional filter by taxonomy

        Returns:
            List of orphan topics as TopicResponse schemas
        """
        # Find topics that don't have any parent edges
        subquery = select(TopicEdge.child_id).distinct()

        conditions = [Topic.id.notin_(subquery)]
        if taxonomy_id:
            conditions.append(Topic.taxonomy_id == taxonomy_id)

        stmt = select(Topic).where(and_(*conditions))
        result = await self.repository.session.execute(stmt)
        topics_orm = result.scalars().all()

        return [TopicResponse.model_validate(t) for t in topics_orm]

    async def find_multi_parent_topics(
        self, min_parents: int = 2, taxonomy_id: str | None = None
    ) -> list[TopicResponse]:
        """Find topics with multiple parent relationships.

        Args:
            min_parents: Minimum number of parents (default: 2)
            taxonomy_id: Optional filter by taxonomy

        Returns:
            List of topics with multiple parents as TopicResponse schemas
        """
        # Find topics that have multiple incoming edges
        subquery = (
            select(TopicEdge.child_id)
            .group_by(TopicEdge.child_id)
            .having(func.count(TopicEdge.parent_id) >= min_parents)
        )

        conditions = [Topic.id.in_(subquery)]
        if taxonomy_id:
            conditions.append(Topic.taxonomy_id == taxonomy_id)

        stmt = select(Topic).where(and_(*conditions))
        result = await self.repository.session.execute(stmt)
        topics_orm = result.scalars().all()

        return [TopicResponse.model_validate(t) for t in topics_orm]

    async def search_topics(self, request: TopicSearchRequest) -> TopicListResponse:
        """Search for topics by title or alias.

        This implements exact substring matching. For fuzzy search, see
        search_topics_fuzzy().

        Args:
            request: Search request with query and filters

        Returns:
            Paginated list of matching topics
        """
        # Build query
        search_pattern = f"%{request.query}%"
        conditions = [
            Topic.title.ilike(search_pattern),
            # For SQLite, we need to use JSON functions to search in aliases
            # This is a simple approach; for production, consider FTS5
        ]

        # Add taxonomy filter if provided
        if request.taxonomy_id is not None:
            statement = (
                select(Topic)
                .where(
                    Topic.taxonomy_id == request.taxonomy_id,
                    or_(*conditions),
                )
                .limit(request.limit)
                .offset(request.offset)
            )
            count_statement = select(Topic).where(
                Topic.taxonomy_id == request.taxonomy_id,
                or_(*conditions),
            )
        else:
            statement = (
                select(Topic)
                .where(or_(*conditions))
                .limit(request.limit)
                .offset(request.offset)
            )
            count_statement = select(Topic).where(or_(*conditions))

        # Execute search
        result = await self.repository.session.execute(statement)
        topics_orm = result.scalars().all()

        # Get count
        count_result = await self.repository.session.execute(count_statement)
        total = len(count_result.scalars().all())

        if request.status:
            topics_orm = [t for t in topics_orm if t.status == request.status]
            # Recalculate total with status filter
            conditions = [
                or_(
                    Topic.title.ilike(f"%{request.query}%"),
                    Topic.aliases.cast(str).ilike(f"%{request.query}%"),  # type: ignore
                )
            ]
            if request.taxonomy_id:
                conditions.append(Topic.taxonomy_id == request.taxonomy_id)
            conditions.append(Topic.status == request.status)

            count_stmt = (
                select(func.count()).select_from(Topic).where(and_(*conditions))
            )
            total_result = await self.repository.session.execute(count_stmt)
            total = total_result.scalar_one()

        items = [TopicResponse.model_validate(t) for t in topics_orm]
        return TopicListResponse(
            items=items, total=total, limit=request.limit, offset=request.offset
        )

    async def list_topic_overviews(
        self,
        taxonomy_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        search: str | None = None,
        sort_by: str = "title",
        sort_order: str = "asc",
    ) -> TopicOverviewListResponse:
        """List enriched topics for a taxonomy with parent/child metadata.

        Args:
            taxonomy_id: ID of the taxonomy
            limit: Maximum number of results
            offset: Number of results to skip
            status: Optional status filter
            search: Optional full-text search over title/description
            sort_by: Field to sort by (title, status, created_at, updated_at, child_count)
            sort_order: Sort order (asc, desc)

        Returns:
            Paginated list of topic overviews
        """
        # Build filters
        filters: list[Any] = [Topic.taxonomy_id == taxonomy_id]

        if status is not None:
            filters.append(Topic.status == status)

        if search is not None:
            # Search in title and description
            search_term = f"%{search}%"
            filters.append(
                or_(
                    Topic.title.ilike(search_term),
                    Topic.description.ilike(search_term),
                )
            )

        # Build base query
        stmt = select(Topic).where(and_(*filters))

        # Add sorting (for non-child_count fields)
        if sort_by == "title":
            sort_col = Topic.title
        elif sort_by == "status":
            sort_col = Topic.status
        elif sort_by == "created_at":
            sort_col = Topic.created_at
        elif sort_by == "updated_at":
            sort_col = Topic.updated_at
        else:
            sort_col = Topic.title  # default

        if sort_order == "desc":
            stmt = stmt.order_by(sort_col.desc())
        else:
            stmt = stmt.order_by(sort_col.asc())

        # Get total count
        count_stmt = select(func.count()).select_from(Topic).where(and_(*filters))
        total = (await self.repository.session.execute(count_stmt)).scalar()

        # Apply pagination
        stmt = stmt.limit(limit).offset(offset)

        # Execute query
        result = await self.repository.session.execute(stmt)
        topics_orm = result.scalars().all()

        # For each topic, get parent and child info
        overviews = []
        for topic_orm in topics_orm:
            topic_response = TopicResponse.model_validate(topic_orm)

            # Get parent topics
            parent_stmt = (
                select(Topic)
                .join(TopicEdge, Topic.id == TopicEdge.parent_id)
                .where(TopicEdge.child_id == topic_orm.id)
            )
            parent_result = await self.repository.session.execute(parent_stmt)
            parents_orm = parent_result.scalars().all()
            parents = [TopicRelationshipRef.model_validate(p) for p in parents_orm]

            # Get child topics
            child_stmt = (
                select(Topic)
                .join(TopicEdge, Topic.id == TopicEdge.child_id)
                .where(TopicEdge.parent_id == topic_orm.id)
            )
            child_result = await self.repository.session.execute(child_stmt)
            children_orm = child_result.scalars().all()
            children = [TopicRelationshipRef.model_validate(c) for c in children_orm]

            overviews.append(
                TopicOverview(
                    topic=topic_response,
                    child_count=len(children),
                    children=children,
                    parents=parents,
                )
            )

        # Handle child_count sorting (post-query sort if needed)
        if sort_by == "child_count":
            overviews.sort(key=lambda o: o.child_count, reverse=(sort_order == "desc"))

        return TopicOverviewListResponse(
            items=overviews,
            total=total or 0,
            limit=limit,
            offset=offset,
        )

    async def get_topic_overview(self, topic_id: str) -> TopicOverview:
        """Get a single topic with its parent/child relationships.

        Args:
            topic_id: ID of the topic to retrieve

        Returns:
            TopicOverview with topic details and relationship metadata

        Raises:
            NotFoundError: If topic doesn't exist
        """
        # Get the topic
        topic_orm = await self.repository.get(topic_id)
        topic_response = TopicResponse.model_validate(topic_orm)

        # Get parent topics (topics that have edges pointing to this topic)
        parent_stmt = (
            select(Topic)
            .join(TopicEdge, Topic.id == TopicEdge.parent_id)
            .where(TopicEdge.child_id == topic_id)
        )
        parent_result = await self.repository.session.execute(parent_stmt)
        parents_orm = parent_result.scalars().all()
        parents = [TopicRelationshipRef.model_validate(p) for p in parents_orm]

        # Get child topics (topics that this topic has edges pointing to)
        child_stmt = (
            select(Topic)
            .join(TopicEdge, Topic.id == TopicEdge.child_id)
            .where(TopicEdge.parent_id == topic_id)
        )
        child_result = await self.repository.session.execute(child_stmt)
        children_orm = child_result.scalars().all()
        children = [TopicRelationshipRef.model_validate(c) for c in children_orm]

        return TopicOverview(
            topic=topic_response,
            child_count=len(children),
            children=children,
            parents=parents,
        )
