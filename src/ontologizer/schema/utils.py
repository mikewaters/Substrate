from __future__ import annotations

"""Utilities for composing Pydantic API DTOs.

- `WithTimestamps`: common response mixin with id/created/updated
- `Page[T]`: generic paging envelope
- `partial_model(...)`: derive a PATCH/Update model by optionalizing fields

These helpers intentionally stay small and dependency-free so they can be
adopted incrementally within modules.
"""

from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, create_model
import annotated_types as at


class WithTimestamps(BaseModel):
    """Mixin for responses that include common timestamp fields."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Generic paging envelope.

    Example: ``CatalogPage = Page[CatalogOut]``
    """

    items: list[T]
    total: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)
    offset: int = Field(..., ge=0)


def partial_model(name: str, model: type[BaseModel]) -> type[BaseModel]:
    """Create a PATCH/Update model by making each field optional.

    - Preserves core validation constraints (e.g., ``min_length``, ``ge``) when
      a field is provided.
    - Sets a ``None`` default so all fields are optional.

    Parameters
    ----------
    name:
        The class name for the generated model.
    model:
        The source Pydantic model whose fields should be optionalized.
    """

    # Build a field map suitable for pydantic.create_model
    fields: dict[str, tuple[Any, Any]] = {}
    for fname, finfo in model.model_fields.items():
        # Ensure an annotation exists
        ann = finfo.annotation or Any

        # Preserve common constraints by mapping from FieldInfo.metadata
        kw: dict[str, Any] = {}
        for meta in getattr(finfo, "metadata", ()):
            if isinstance(meta, at.MinLen):
                kw["min_length"] = meta.min_length
            elif isinstance(meta, at.MaxLen):
                kw["max_length"] = meta.max_length
            elif isinstance(meta, at.Ge):
                kw["ge"] = meta.ge
            elif isinstance(meta, at.Gt):
                kw["gt"] = meta.gt
            elif isinstance(meta, at.Le):
                kw["le"] = meta.le
            elif isinstance(meta, at.Lt):
                kw["lt"] = meta.lt

        # Copy user-facing metadata when available
        if getattr(finfo, "title", None):
            kw["title"] = finfo.title
        if getattr(finfo, "description", None):
            kw["description"] = finfo.description
        if getattr(finfo, "json_schema_extra", None):
            kw["json_schema_extra"] = finfo.json_schema_extra

        # Optionalize the annotation and set default to None
        fields[fname] = (Optional[ann], Field(default=None, **kw))

    cls = create_model(name, __base__=BaseModel, **fields)
    cls.__module__ = __name__
    return cls
