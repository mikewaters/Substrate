"""catalog.store.models.content - SQLAlchemy ORM models for the content database.

The content database stores large document bodies and content that benefits
from separation from the catalog metadata. This database is ATTACHed to the
catalog database connection, allowing cross-database queries via schema prefix.

Models defined here use ``__table_args__ = {"schema": "content"}`` to indicate
they belong to the attached content database.
"""

from sqlalchemy.orm import DeclarativeBase

__all__ = [
    "ContentBase",
]


class ContentBase(DeclarativeBase):
    """SQLAlchemy declarative base for content database models.

    Models inheriting from ContentBase will be created in the content database.
    Use ``__table_args__ = {"schema": "content"}`` to ensure proper ATTACH
    behavior when querying from the catalog database connection.
    """

    pass


# Future content models will be defined here, e.g.:
#
# class DocumentContent(ContentBase):
#     __tablename__ = "document_content"
#     __table_args__ = {"schema": "content"}
#
#     id: Mapped[int] = mapped_column(primary_key=True)
#     document_id: Mapped[int] = mapped_column(nullable=False, index=True)
#     body: Mapped[str] = mapped_column(Text, nullable=False)
#     ...
