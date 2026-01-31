"""Service layer for Activity operations.

This service provides business logic for activities, including search and
discovery features. It bridges between Pydantic schemas (I/O) and domain
models (business logic).
"""

from __future__ import annotations

import asyncio
import logging
from functools import wraps
from typing import Any

from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService

from ontology.relational.models import Activity as ActivityORM
from ontology.relational.repository.work import ActivityRepository

logger = logging.getLogger(__name__)


def dual_mode(method):
    """Allow async methods to be used from sync contexts when no loop is running."""

    @wraps(method)
    def wrapper(self, *args: Any, **kwargs: Any):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            return method(self, *args, **kwargs)

        return asyncio.run(method(self, *args, **kwargs))

    return wrapper


"""
Available Service methods (inherited from SQLAlchemyAsyncRepositoryService):
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


class ActivityService(SQLAlchemyAsyncRepositoryService[ActivityORM]):
    """Service for activity operations.

    This service handles activity business logic, including CRUD operations,
    search, and discovery features.
    """

    repository_type = ActivityRepository
