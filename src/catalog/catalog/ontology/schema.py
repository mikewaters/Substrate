"""catalog.ontology.schema - Shared document metadata ontology.

Defines the canonical DocumentMeta dataclass that all source-specific
schemas map into. This is the structured metadata that gets persisted
alongside documents in the catalog store.

Also provides the ``FrontmatterSchema`` Protocol so that
FrontmatterTransform can accept any schema implementation without
depending on a concrete class like VaultSchema.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class DocumentMeta:
    """Canonical document metadata shared across all source types.

    Fields represent the common metadata ontology. Source-specific fields
    that don't map to any ontology field go into ``extra``.

    Attributes:
        title: Document title.
        description: Short document description or summary.
        tags: Free-form tags / labels.
        categories: Categorical classifications (e.g. note type).
        author: Document author.
        extra: Overflow bucket for source-specific fields.
    """

    title: str | None = None
    description: str | None = None
    tags: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    author: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a compact dict, omitting None and empty values."""
        out: dict[str, Any] = {}
        if self.title is not None:
            out["title"] = self.title
        if self.description is not None:
            out["description"] = self.description
        if self.tags:
            out["tags"] = self.tags
        if self.categories:
            out["categories"] = self.categories
        if self.author is not None:
            out["author"] = self.author
        if self.extra:
            out["extra"] = self.extra
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DocumentMeta:
        """Deserialize from a dict (round-trip from ``to_dict``)."""
        return cls(
            title=data.get("title"),
            description=data.get("description"),
            tags=data.get("tags", []),
            categories=data.get("categories", []),
            author=data.get("author"),
            extra=data.get("extra", {}),
        )


@runtime_checkable
class FrontmatterSchema(Protocol):
    """Protocol for frontmatter schema implementations.

    Any class that provides ``from_frontmatter()`` and ``to_document_meta()``
    satisfies this protocol, decoupling FrontmatterTransform from VaultSchema's
    concrete location.
    """

    @classmethod
    def from_frontmatter(cls, raw: dict[str, Any]) -> FrontmatterSchema: ...

    def to_document_meta(self) -> DocumentMeta: ...
