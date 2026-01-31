"""SQLAlchemy ORM models for Activity entities.

This module defines the database schema for the work/activity system using
SQLAlchemy 2.x with Advanced Alchemy patterns.

Models:
    - Activity: Base table for all work activities with single-table inheritance
"""

from sqlalchemy import (
    CheckConstraint,
    Index,
    Text,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from ontology.relational.database import CURIEBase
from ontology.domain import ACTIVITY_DEFAULT_NAMESPACE_PREFIX


class Activity(CURIEBase):
    """Base table for all work activities.

    Uses single-table inheritance with activity_type as the discriminator.
    All activity types (Effort, Task, Research, etc.) are stored in this table.

    Attributes:
        id: Unique identifier (UUID)
        identifier: CURIE-format identifier (e.g., "act:my-task")
        title: Human-readable title
        description: Optional longer description
        activity_type: Type of activity (Effort, Task, Research, Study, Experiment, Thinking)
        url: Optional URL associated with this activity
        created_by: Who created this activity
        created_on: When the activity was created (stored in created_at)
        last_updated_on: When the activity was last updated (stored in updated_at)
    """

    __tablename__ = "activity"
    __table_args__ = (
        CheckConstraint(
            "activity_type IN ('Effort', 'Experiment', 'Research', 'Study', 'Task', 'Thinking')",
            name="ck_activity_type",
        ),
        Index("ix_activity_title", "title"),
        Index("ix_activity_type", "activity_type"),
        Index("ix_activity_created_at", "created_at"),
        Index("ix_activity_created_by", "created_by"),
    )

    _curie_namespace_prefix = ACTIVITY_DEFAULT_NAMESPACE_PREFIX

    # Primary fields
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    activity_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # Optional fields
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Note: created_at and updated_at are provided by CURIEBase
    # We map created_on -> created_at and last_updated_on -> updated_at

    def __repr__(self) -> str:
        return f"<Activity(id={self.id}, type='{self.activity_type}', title='{self.title}')>"
