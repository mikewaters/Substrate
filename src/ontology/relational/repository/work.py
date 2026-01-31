"""Repository for Activity entities.

This module provides the repository layer for Activity CRUD operations,
transforming between domain models (attrs) and ORM models (SQLAlchemy).
"""

import logging

from advanced_alchemy.repository import SQLAlchemyAsyncRepository

from ontology.relational.models import Activity

logger = logging.getLogger(__name__)

"""
Available Repository methods (inherited from SQLAlchemyAsyncRepository):
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


class ActivityRepository(SQLAlchemyAsyncRepository[Activity]):
    """Repository for Activity entities.

    This repository handles CRUD operations for activities, including
    identifier generation and conversion between domain and database models.
    """

    model_type = Activity
