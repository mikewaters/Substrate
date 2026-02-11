"""Repository for Topic entities.

This module provides the repository layer for Topic CRUD operations,
transforming between domain models (attrs) and ORM models (SQLAlchemy).
"""

import logging

from sqlalchemy import select

logger = logging.getLogger(__name__)
from advanced_alchemy.exceptions import NotFoundError
from advanced_alchemy.repository import SQLAlchemyAsyncRepository

from ontologizer.relational.models import (
    Taxonomy,
    Topic,
    TopicClosure,
    TopicEdge,
)

"""
Available Repository methods:
    add
    add_many
    delete
    delete_many
    delete_where
    exists
    get
    get_one
    get_one_or_none
    get_or_upsert
    get_and_update
    count
    update
    update_many
    list_and_count
    upsert
    upsert_many
    list
"""


class TopicEdgeRepository(SQLAlchemyAsyncRepository[TopicEdge]):
    """Repository for TopicEdge entities.

    This repository handles edge creation, deletion, and closure table management.
    It coordinates with TopicRepository for materialized path updates.
    """

    model_type = TopicEdge

    HIERARCHICAL_ROLES = ("broader", "narrower", "part_of", "instance_of")

    def __init__(self, topic_repo: "TopicRepository", **kwargs):
        """Initialize with a reference to TopicRepository for path updates."""
        super().__init__(**kwargs)
        self.topic_repo = topic_repo

    async def add(self, data: TopicEdge, **kwargs) -> TopicEdge:
        """Create a new topic edge (relationship).

        This overrides the base add() method to include:
        - Validation that both topics exist
        - Cycle detection
        - Primary parent assignment
        - Closure table maintenance
        - Materialized path updates

        Args:
            data: Edge data (TopicEdge ORM instance)
            **kwargs: Additional arguments passed to base add()

        Returns:
            Created edge ORM model

        Raises:
            ValueError: If edge would create a cycle or if topics don't exist
        """
        # Validate both topics exist
        try:
            parent = await self.topic_repo.get(data.parent_id)
            child = await self.topic_repo.get(data.child_id)
        except NotFoundError as e:
            raise ValueError(f"Topic not found: {e}")

        # Check for self-loop
        if data.parent_id == data.child_id:
            raise ValueError("Cannot create edge from topic to itself")

        # Check if edge would create cycle
        if await self._would_create_cycle(data.parent_id, data.child_id):
            raise ValueError(
                f"Cannot create edge: would create cycle between "
                f"{data.parent_id} and {data.child_id}"
            )

        is_hierarchical = data.role in self.HIERARCHICAL_ROLES

        # Create edge using base class method
        edge_orm = await super().add(data, **kwargs)
        await self.session.flush()

        assigned_primary = False
        if is_hierarchical:
            if data.is_primary:
                await self._assign_primary_parent(edge_orm)
                assigned_primary = True
            elif await self._get_primary_edge(data.child_id) is None:
                await self._assign_primary_parent(edge_orm)
                assigned_primary = True

        # Maintain closure table
        await self._add_edge_to_closure(data.parent_id, data.child_id)

        if assigned_primary:
            await self.topic_repo._refresh_materialized_path(
                data.child_id, include_descendants=True
            )

        return edge_orm

    async def delete_edge(self, parent_id: str, child_id: str) -> bool:
        """Delete a topic edge.

        Args:
            parent_id: Parent topic ID
            child_id: Child topic ID

        Returns:
            True if deleted, False if not found
        """
        # Find the edge
        statement = select(TopicEdge).where(
            TopicEdge.parent_id == parent_id,
            TopicEdge.child_id == child_id,
        )
        result = await self.session.execute(statement)
        edge_orm = result.scalar_one_or_none()

        if edge_orm is None:
            return False

        is_hierarchical = edge_orm.role in self.HIERARCHICAL_ROLES
        was_primary = edge_orm.is_primary

        # Delete from closure table first
        await self._remove_edge_from_closure(parent_id, child_id)

        # Delete the edge
        await self.session.delete(edge_orm)
        await self.session.flush()

        if is_hierarchical and was_primary:
            await self._ensure_primary_parent(child_id)
            await self.topic_repo._refresh_materialized_path(
                child_id, include_descendants=True
            )

        return True

    # ==================== Closure Table Management (Private) ====================

    async def _would_create_cycle(self, parent_id: str, child_id: str) -> bool:
        """Check if adding an edge would create a cycle.

        Uses the closure table to detect cycles: adding parent->child would
        create a cycle if child is already an ancestor of parent.

        Args:
            parent_id: Proposed parent topic ID
            child_id: Proposed child topic ID

        Returns:
            True if edge would create a cycle
        """
        # Check if child is already an ancestor of parent
        # (i.e., there's already a path from child to parent)
        statement = select(TopicClosure).where(
            TopicClosure.ancestor_id == child_id,
            TopicClosure.descendant_id == parent_id,
        )
        result = await self.session.execute(statement)
        existing_path = result.scalar_one_or_none()

        return existing_path is not None

    async def _add_edge_to_closure(self, parent_id: str, child_id: str) -> None:
        """Add an edge to the closure table.

        This maintains the transitive closure by adding:
        1. Self-loops for both topics (if not exist)
        2. Direct edge (parent -> child, depth=1)
        3. All paths from ancestors of parent to child
        4. All paths from parent to descendants of child
        5. All paths from ancestors of parent to descendants of child

        Args:
            parent_id: Parent topic ID
            child_id: Child topic ID
        """

        # Helper function to add closure entry if it doesn't exist
        async def add_closure_if_not_exists(
            ancestor: str, descendant: str, depth: int
        ) -> None:
            stmt = select(TopicClosure).where(
                TopicClosure.ancestor_id == ancestor,
                TopicClosure.descendant_id == descendant,
            )
            result = await self.session.execute(stmt)
            if result.scalar_one_or_none() is None:
                self.session.add(
                    TopicClosure(
                        ancestor_id=ancestor,
                        descendant_id=descendant,
                        depth=depth,
                    )
                )

        # Add self-loops if they don't exist
        for topic_id in [parent_id, child_id]:
            await add_closure_if_not_exists(topic_id, topic_id, 0)

        # Add direct edge
        await add_closure_if_not_exists(parent_id, child_id, 1)

        # Add paths from all ancestors of parent to child
        ancestor_stmt = select(TopicClosure).where(
            TopicClosure.descendant_id == parent_id
        )
        ancestor_result = await self.session.execute(ancestor_stmt)
        ancestors = ancestor_result.scalars().all()

        for ancestor_closure in ancestors:
            if (
                ancestor_closure.ancestor_id != parent_id
            ):  # Skip the direct edge we just added
                await add_closure_if_not_exists(
                    ancestor_closure.ancestor_id,
                    child_id,
                    ancestor_closure.depth + 1,
                )

        # Add paths from parent to all descendants of child
        descendant_stmt = select(TopicClosure).where(
            TopicClosure.ancestor_id == child_id
        )
        descendant_result = await self.session.execute(descendant_stmt)
        descendants = descendant_result.scalars().all()

        for descendant_closure in descendants:
            if descendant_closure.descendant_id != child_id:  # Skip the direct edge
                await add_closure_if_not_exists(
                    parent_id,
                    descendant_closure.descendant_id,
                    descendant_closure.depth + 1,
                )

        # Add paths from all ancestors of parent to all descendants of child
        for ancestor_closure in ancestors:
            for descendant_closure in descendants:
                if (
                    ancestor_closure.ancestor_id != parent_id
                    and descendant_closure.descendant_id != child_id
                ):
                    await add_closure_if_not_exists(
                        ancestor_closure.ancestor_id,
                        descendant_closure.descendant_id,
                        ancestor_closure.depth + descendant_closure.depth + 1,
                    )

        await self.session.flush()

    async def _remove_edge_from_closure(self, parent_id: str, child_id: str) -> None:
        """Remove an edge from the closure table.

        This is more complex than adding because we need to remove only the
        paths that depend on this specific edge.

        Args:
            parent_id: Parent topic ID
            child_id: Child topic ID
        """
        # Find all closure entries that would be affected by removing this edge
        # These are paths that go through this specific edge

        # Get all ancestors of parent (including parent itself)
        ancestor_stmt = select(TopicClosure).where(
            TopicClosure.descendant_id == parent_id
        )
        ancestor_result = await self.session.execute(ancestor_stmt)
        ancestors = ancestor_result.scalars().all()

        # Get all descendants of child (including child itself)
        descendant_stmt = select(TopicClosure).where(
            TopicClosure.ancestor_id == child_id
        )
        descendant_result = await self.session.execute(descendant_stmt)
        descendants = descendant_result.scalars().all()

        # Delete closure entries from all ancestors of parent to all descendants of child
        for ancestor_closure in ancestors:
            for descendant_closure in descendants:
                # Check if there's an alternative path
                # If there is, don't delete this closure entry
                if not await self._has_alternative_path(
                    ancestor_closure.ancestor_id,
                    descendant_closure.descendant_id,
                    parent_id,
                    child_id,
                ):
                    delete_stmt = select(TopicClosure).where(
                        TopicClosure.ancestor_id == ancestor_closure.ancestor_id,
                        TopicClosure.descendant_id == descendant_closure.descendant_id,
                    )
                    result = await self.session.execute(delete_stmt)
                    closure_to_delete = result.scalar_one_or_none()
                    if closure_to_delete:
                        await self.session.delete(closure_to_delete)

        await self.session.flush()

    async def _has_alternative_path(
        self,
        ancestor_id: str,
        descendant_id: str,
        exclude_parent: str,
        exclude_child: str,
    ) -> bool:
        """Check if there's an alternative path between two topics.

        This is used when deleting an edge to determine if closure entries
        should be kept (because there's another path) or deleted.

        Args:
            ancestor_id: Starting topic ID
            descendant_id: Ending topic ID
            exclude_parent: Parent of edge being deleted
            exclude_child: Child of edge being deleted

        Returns:
            True if alternative path exists
        """
        # Simple check: if we're looking for a path from A to D, and we're
        # excluding edge B->C, we need to find if there's a path A->...->D
        # that doesn't use B->C

        # For now, we'll use a simplified approach: check if there are other
        # edges that could provide the path. This could be optimized further.

        if ancestor_id == descendant_id:
            return True  # Self-loop always exists

        # Get all edges
        edges_stmt = select(TopicEdge).where(
            TopicEdge.parent_id != exclude_parent,
            TopicEdge.child_id != exclude_child,
        )
        edges_result = await self.session.execute(edges_stmt)
        edges = edges_result.scalars().all()

        # Build adjacency list
        graph: dict[str, list[str]] = {}
        for edge in edges:
            parent = edge.parent_id
            child = edge.child_id
            if parent not in graph:
                graph[parent] = []
            graph[parent].append(child)

        # DFS to find path
        visited = set()

        def dfs(current: str) -> bool:
            if current == descendant_id:
                return True
            if current in visited:
                return False
            visited.add(current)

            for neighbor in graph.get(current, []):
                if dfs(neighbor):
                    return True

            return False

        return dfs(ancestor_id)

    async def _get_primary_edge(self, child_id: str) -> TopicEdge | None:
        statement = (
            select(TopicEdge)
            .where(
                TopicEdge.child_id == child_id,
                TopicEdge.is_primary.is_(True),
                TopicEdge.role.in_(self.HIERARCHICAL_ROLES),
            )
            .limit(1)
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def _assign_primary_parent(self, edge_orm: TopicEdge) -> None:
        if edge_orm.role not in self.HIERARCHICAL_ROLES:
            edge_orm.is_primary = False
            return

        other_stmt = select(TopicEdge).where(
            TopicEdge.child_id == edge_orm.child_id,
            TopicEdge.id != edge_orm.id,
            TopicEdge.is_primary.is_(True),
        )
        other_result = await self.session.execute(other_stmt)
        for other in other_result.scalars():
            other.is_primary = False

        edge_orm.is_primary = True

    async def _ensure_primary_parent(self, child_id: str) -> None:
        if await self._get_primary_edge(child_id) is not None:
            return

        candidate_stmt = (
            select(TopicEdge)
            .where(
                TopicEdge.child_id == child_id,
                TopicEdge.role.in_(self.HIERARCHICAL_ROLES),
            )
            .order_by(TopicEdge.created_at.asc())
        )
        candidate_result = await self.session.execute(candidate_stmt)
        candidate = candidate_result.scalars().first()
        if candidate is not None:
            await self._assign_primary_parent(candidate)


class TopicRepository(SQLAlchemyAsyncRepository[Topic]):
    """Repository for Topic entities.

    This repository handles CRUD operations for topics, including slug generation,
    search functionality, and conversion between domain and database models.

    """

    model_type = Topic

    HIERARCHICAL_ROLES = ("broader", "narrower", "part_of", "instance_of")

    # Override built-ins where I have to modify materialized path for changes
    async def add(self, data: Topic, **kwargs) -> Topic:
        """Override of `add` to refresh materialized path"""
        instance = await super().add(data, **kwargs)
        await self.session.flush()

        # Initialize materialized path (root level for now)
        await self._refresh_materialized_path(instance.id)
        return instance

    async def update(self, data: Topic, **kwargs) -> Topic:
        """Override of `update` to refresh materialized path"""
        updated = await super().update(data, **kwargs)
        await self.session.flush()

        await self._refresh_materialized_path(updated.id, include_descendants=True)
        return updated

    async def upsert(self, data: Topic, **kwargs) -> Topic:
        """Override of `update` to refresh materialized path"""
        updated_or_new = await super().upsert(data, **kwargs)
        await self.session.flush()

        await self._refresh_materialized_path(
            updated_or_new.id, include_descendants=True
        )
        return updated_or_new

    async def _refresh_materialized_path(
        self, topic_id: str, *, include_descendants: bool = False
    ) -> None:
        await self._update_topic_path(topic_id)

        if include_descendants:
            descendants_stmt = select(TopicClosure.descendant_id).where(
                TopicClosure.ancestor_id == topic_id,
                TopicClosure.depth > 0,
            )
            descendant_result = await self.session.execute(descendants_stmt)
            descendant_ids = descendant_result.scalars().all()
            for descendant_id in descendant_ids:
                if descendant_id == topic_id:
                    continue
                await self._update_topic_path(descendant_id)

    async def _get_primary_edge(self, child_id: str) -> TopicEdge | None:
        """Get the primary hierarchical edge for a topic.

        This is a read-only helper method used for materialized path calculations.
        """
        statement = (
            select(TopicEdge)
            .where(
                TopicEdge.child_id == child_id,
                TopicEdge.is_primary.is_(True),
                TopicEdge.role.in_(self.HIERARCHICAL_ROLES),
            )
            .limit(1)
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def _update_topic_path(self, topic_id: str) -> None:
        topic_orm = await self.session.get(Topic, topic_id)
        if topic_orm is None:
            return

        segments: list[str] = []
        current = topic_orm
        visited: set[str] = set()

        while current and current.slug:
            current_id = current.id
            if current_id in visited:
                break
            visited.add(current_id)
            segments.append(current.slug)

            primary_edge = await self._get_primary_edge(current_id)
            if primary_edge is None:
                break

            parent = await self.session.get(Topic, primary_edge.parent_id)
            if parent is None:
                break
            current = parent

        if not segments:
            return

        segments.reverse()
        topic_orm.path = "/" + "/".join(segments)


class TaxonomyRepository(SQLAlchemyAsyncRepository[Taxonomy]):
    """Repository for Taxonomy entities.

    This repository handles CRUD operations for taxonomies, converting between
    domain models (attrs) and database models (SQLAlchemy ORM).
    """

    model_type = Taxonomy

    async def get_all_active(self) -> list[Taxonomy]:
        """Get all active taxonomies for classification.

        Returns taxonomies ordered by title for consistent prompt construction.
        """
        stmt = select(Taxonomy).order_by(Taxonomy.title.asc())

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_with_topics(
        self, taxonomy_id: str, status: str | None = "active"
    ) -> tuple[Taxonomy, list["Topic"]]:
        """Get a taxonomy with all its topics.

        Args:
            taxonomy_id: Taxonomy identifier
            status: Optional status filter for topics

        Returns:
            Tuple of (taxonomy, topics)
        """
        taxonomy = await self.get(taxonomy_id)

        stmt = select(Topic).where(Topic.taxonomy_id == taxonomy_id)

        if status:
            stmt = stmt.where(Topic.status == status)

        stmt = stmt.order_by(Topic.title.asc())

        result = await self.session.execute(stmt)
        topics = list(result.scalars().all())

        return taxonomy, topics
