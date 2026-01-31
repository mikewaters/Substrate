"""Service layer for the ontology."""

from __future__ import annotations

from typing import Any, TypeVar
from collections.abc import Callable

from sqlalchemy.orm import DeclarativeBase

from advanced_alchemy.service import (
    SQLAlchemyAsyncQueryService,
    SQLAlchemyAsyncRepositoryReadService,
    SQLAlchemyAsyncRepositoryService,
)

T = TypeVar("T")


def _wrap_method(method: Callable[..., Any]) -> Callable[..., Any]:
    """Wraps a method to convert its ORM result to a Pydantic schema."""

    async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        """Wrapper function that converts the result to a schema."""
        result = await method(self, *args, **kwargs)

        # Get the schema type from the service if available
        schema_type = getattr(self, "schema_type", None)
        if not schema_type:
            return result

        if isinstance(result, DeclarativeBase):
            return self.to_schema(result, schema_type=schema_type)
        if (
            isinstance(result, list)
            and result
            and isinstance(result[0], DeclarativeBase)
        ):
            return [self.to_schema(item, schema_type=schema_type) for item in result]
        if (
            isinstance(result, tuple)
            and len(result) > 0
            and isinstance(result[0], list)
            and result[0]
            and isinstance(result[0][0], DeclarativeBase)
        ):
            return (
                [self.to_schema(item, schema_type=schema_type) for item in result[0]],
                *result[1:],
            )
        # Handle OffsetPagination
        if hasattr(result, "items") and isinstance(result.items, list):
            if result.items and isinstance(result.items[0], DeclarativeBase):
                result.items = [
                    self.to_schema(item, schema_type=schema_type)
                    for item in result.items
                ]
        return result

    return wrapper


class SchemaConvertingMetaclass(type):
    """Metaclass that wraps methods to convert their results to Pydantic schemas."""

    def __new__(mcs, name: str, bases: tuple[type, ...], dct: dict[str, Any]) -> Any:
        """Create a new class with wrapped methods."""
        cls = super().__new__(mcs, name, bases, dct)
        whitelist_attr = "_CONVERT_TO_SCHEMA_WHITELIST"
        if hasattr(cls, whitelist_attr):
            whitelist = getattr(cls, whitelist_attr)
            for method_name in whitelist:
                if hasattr(cls, method_name):
                    method = getattr(cls, method_name)
                    if callable(method) and not method_name.startswith("_"):
                        setattr(cls, method_name, _wrap_method(method))
        return cls


class SchemaConvertingService(metaclass=SchemaConvertingMetaclass):
    """Base class for services that automatically convert results to schemas."""

    _CONVERT_TO_SCHEMA_WHITELIST: list[str] = []


class ReadService(SQLAlchemyAsyncRepositoryReadService[T], SchemaConvertingService):
    """Read-only service that automatically converts ORM models to Pydantic schemas."""

    _CONVERT_TO_SCHEMA_WHITELIST = [
        "get",
        "get_one",
        "get_one_or_none",
        "list",
        "list_and_count",
        "count",
        "exists",
    ]


class Service(SQLAlchemyAsyncRepositoryService[T], SchemaConvertingService):
    """Service that automatically converts ORM models to Pydantic schemas."""

    _CONVERT_TO_SCHEMA_WHITELIST = [
        "get",
        "get_one",
        "get_one_or_none",
        "list",
        "list_and_count",
        "count",
        "exists",
        "create",
        "create_many",
        "update",
        "update_many",
        "delete",
        "delete_many",
        "upsert",
    ]


class QueryService(SQLAlchemyAsyncQueryService, SchemaConvertingService):
    """Query service that automatically converts ORM models to Pydantic schemas."""

    _CONVERT_TO_SCHEMA_WHITELIST: list[str] = []
