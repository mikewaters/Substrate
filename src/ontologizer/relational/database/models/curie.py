"""Common base classes for SQLAlchemy declarative models."""

import secrets
from sqlalchemy import String, event
from sqlalchemy.orm import Mapped, declarative_mixin, mapped_column, DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs

from advanced_alchemy.base import CommonTableAttributes
from advanced_alchemy.mixins import (
    AuditColumns,
)
from advanced_alchemy.mixins.sentinel import SentinelMixin
class Base(DeclarativeBase):
    pass


@declarative_mixin
class CURIEPrimaryKey():
    """CURIE Primary Key Field Mixin with auto-generation support.

    Subclasses can override:
        _curie_namespace_prefix: Namespace prefix for CURIE generation (e.g., "cat")
        _curie_title_field: Field name to use for generating CURIE (default: "title")
    """

    id: Mapped[str] = mapped_column(
        String(255), primary_key=True, nullable=False, unique=True, index=True
    )

    # Subclasses can override these for auto-generation
    _curie_namespace_prefix: str | None = None
    _curie_title_field: str = "title"

#, CommonTableAttributes, AdvancedDeclarativeBase, AsyncAttrs
class CURIEBase(CommonTableAttributes, CURIEPrimaryKey, AuditColumns, Base, AsyncAttrs):
    """Base for all SQLAlchemy declarative models with CURIE primary keys.

    Auto-generates CURIE-based IDs on insert if:
    - No ID is already set
    - _curie_namespace_prefix is configured on the subclass
    - The title field (or _curie_title_field) has a value
    """

    __abstract__ = True


@declarative_mixin
class PrimaryKey():
    """Primary Key Field Mixin with auto-generation for random IDs."""

    id: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
        nullable=False,
        unique=True,
        index=True,
        default=lambda: secrets.token_urlsafe(8),
    )


class IdBase(CommonTableAttributes, PrimaryKey, AuditColumns, Base, AsyncAttrs):
    """Base for models with random string IDs.

    Automatically generates an 8-character random ID using secrets.token_urlsafe().
    """

    __abstract__ = True


# Centralized event listener for CURIE ID generation
@event.listens_for(CURIEBase, "before_insert", propagate=True)
def generate_curie_id(mapper, connection, target):
    """Auto-generate CURIE-based ID if not set.

    This listener fires for all CURIEBase subclasses. It generates an ID
    from the configured namespace prefix and title field.

    Args:
        mapper: SQLAlchemy mapper
        connection: Database connection
        target: Model instance being inserted
    """
    # Import here to avoid circular dependencies
    from ontologizer.utils.slug import make_namespace

    # Skip if ID already set
    if target.id:
        return

    # Skip if no namespace prefix configured
    if (
        not hasattr(target, "_curie_namespace_prefix")
        or not target._curie_namespace_prefix
    ):
        return

    # Get title field value
    title_field = getattr(target, "_curie_title_field", "title")
    title = getattr(target, title_field, None)

    # Skip if title is missing (let proper validation handle it)
    if not title:
        return

    # Generate CURIE
    target.id = make_namespace(target._curie_namespace_prefix, title)
