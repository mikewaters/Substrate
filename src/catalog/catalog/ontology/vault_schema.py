"""catalog.ontology.vault_schema - Pydantic base for vault-specific frontmatter schemas.

Clients subclass ``VaultSchema`` and annotate fields with
``json_schema_extra={"maps_to": "<ontology_field>"}`` to declare how
vault frontmatter keys map to the shared :class:`DocumentMeta` ontology.

Fields without ``maps_to`` flow into ``DocumentMeta.extra``.

Example::

    class MyVaultSchema(VaultSchema):
        tags: list[str] = Field(default_factory=list, json_schema_extra={"maps_to": "tags"})
        aliases: list[str] = Field(default_factory=list)  # -> extra
        type: str | None = Field(None, json_schema_extra={"maps_to": "categories"})
        cssclass: str | None = None  # -> extra
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from catalog.ontology.schema import DocumentMeta

# Ontology fields that accept list values (coerced from scalar strings).
_LIST_ONTOLOGY_FIELDS = frozenset({"tags", "categories"})

# All valid ontology target names.
_VALID_ONTOLOGY_TARGETS = frozenset(DocumentMeta.__dataclass_fields__.keys()) - {"extra"}


class VaultSchema(BaseModel):
    """Base Pydantic model for vault-specific frontmatter schemas.

    Subclasses declare typed fields matching their vault's frontmatter keys.
    Use ``json_schema_extra={"maps_to": "..."}`` on a field to route it to
    the corresponding :class:`DocumentMeta` attribute.

    ``model_config["extra"] = "allow"`` captures any undeclared frontmatter
    keys so nothing is silently dropped.
    """

    model_config = {"extra": "allow"}

    @classmethod
    def from_frontmatter(cls, raw: dict[str, Any]) -> VaultSchema:
        """Validate raw frontmatter through this schema.

        Pydantic handles type coercion, defaults, and extra-field capture.

        Args:
            raw: Raw YAML frontmatter dict.

        Returns:
            Validated schema instance.
        """
        return cls.model_validate(raw)

    def to_document_meta(self) -> DocumentMeta:
        """Convert validated frontmatter into a :class:`DocumentMeta`.

        Fields annotated with ``maps_to`` are routed to the corresponding
        ontology attribute.  All other fields (including Pydantic extras)
        go into ``DocumentMeta.extra``.

        Returns:
            Populated DocumentMeta instance.
        """
        ontology_values: dict[str, Any] = {}
        extra: dict[str, Any] = {}

        # Process declared fields (access on class, not instance).
        for field_name, field_info in type(self).model_fields.items():
            value = getattr(self, field_name)
            maps_to = _get_maps_to(field_info)

            if maps_to is not None and maps_to in _VALID_ONTOLOGY_TARGETS:
                value = _coerce_for_target(maps_to, value)
                # Merge lists for multi-field mappings to the same target.
                if maps_to in _LIST_ONTOLOGY_FIELDS and maps_to in ontology_values:
                    ontology_values[maps_to] = ontology_values[maps_to] + value
                else:
                    ontology_values[maps_to] = value
            else:
                # Skip None and empty collections to keep extra clean.
                if value is None:
                    continue
                if isinstance(value, (list, dict)) and not value:
                    continue
                extra[field_name] = value

        # Capture Pydantic extras (undeclared frontmatter keys).
        if self.model_extra:
            for k, v in self.model_extra.items():
                if v is not None:
                    extra[k] = v

        return DocumentMeta(
            title=ontology_values.get("title"),
            description=ontology_values.get("description"),
            tags=ontology_values.get("tags", []),
            categories=ontology_values.get("categories", []),
            author=ontology_values.get("author"),
            extra=extra,
        )


def _get_maps_to(field_info: Any) -> str | None:
    """Extract the ``maps_to`` annotation from a Pydantic FieldInfo."""
    schema_extra = field_info.json_schema_extra
    if isinstance(schema_extra, dict):
        return schema_extra.get("maps_to")
    return None


def _coerce_for_target(target: str, value: Any) -> Any:
    """Coerce a value to match the expected ontology field type.

    - List targets: scalar string → single-element list.
    - String targets: non-string → str().
    """
    if target in _LIST_ONTOLOGY_FIELDS:
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return value
        if value is None:
            return []
        return [str(value)]
    # Scalar string targets (title, description, author).
    if value is not None and not isinstance(value, str):
        return str(value)
    return value
