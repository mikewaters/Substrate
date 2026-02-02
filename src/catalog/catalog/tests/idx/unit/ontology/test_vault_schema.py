"""Tests for catalog.ontology.vault_schema — VaultSchema mapping."""

import pytest
from pydantic import Field

from catalog.ontology.schema import DocumentMeta
from catalog.ontology.vault_schema import VaultSchema


# --- Test schemas ---

class SimpleSchema(VaultSchema):
    """Minimal schema with basic mappings."""
    tags: list[str] = Field(default_factory=list, json_schema_extra={"maps_to": "tags"})
    aliases: list[str] = Field(default_factory=list)  # no maps_to -> extra


class FullSchema(VaultSchema):
    """Schema exercising all ontology targets."""
    tags: list[str] = Field(default_factory=list, json_schema_extra={"maps_to": "tags"})
    note_type: str | None = Field(None, json_schema_extra={"maps_to": "categories"})
    author: str | None = Field(None, json_schema_extra={"maps_to": "author"})
    aliases: list[str] = Field(default_factory=list)
    cssclass: str | None = None


# --- Tests ---

class TestFromFrontmatter:
    """from_frontmatter() validates and coerces raw dicts."""

    def test_basic_validation(self) -> None:
        schema = SimpleSchema.from_frontmatter({"tags": ["a", "b"], "aliases": ["x"]})
        assert schema.tags == ["a", "b"]
        assert schema.aliases == ["x"]

    def test_empty_dict(self) -> None:
        schema = SimpleSchema.from_frontmatter({})
        assert schema.tags == []
        assert schema.aliases == []

    def test_extra_fields_captured(self) -> None:
        schema = SimpleSchema.from_frontmatter(
            {"tags": ["a"], "cssclass": "wide", "unknown_key": 42}
        )
        assert schema.model_extra == {"cssclass": "wide", "unknown_key": 42}

    def test_type_coercion_string_to_list(self) -> None:
        """Pydantic should handle string-to-list if types allow it."""
        schema = SimpleSchema.from_frontmatter({"tags": ["single"]})
        assert schema.tags == ["single"]


class TestToDocumentMeta:
    """to_document_meta() routes fields correctly."""

    def test_mapped_fields_route_to_ontology(self) -> None:
        schema = SimpleSchema.from_frontmatter({"tags": ["a", "b"]})
        meta = schema.to_document_meta()
        assert meta.tags == ["a", "b"]

    def test_unmapped_fields_route_to_extra(self) -> None:
        schema = SimpleSchema.from_frontmatter({"tags": ["a"], "aliases": ["x", "y"]})
        meta = schema.to_document_meta()
        assert meta.extra["aliases"] == ["x", "y"]

    def test_pydantic_extras_route_to_extra(self) -> None:
        schema = SimpleSchema.from_frontmatter({"cssclass": "wide"})
        meta = schema.to_document_meta()
        assert meta.extra["cssclass"] == "wide"

    def test_full_schema_mapping(self) -> None:
        schema = FullSchema.from_frontmatter({
            "tags": ["python", "ml"],
            "note_type": "tutorial",
            "author": "Mike",
            "aliases": ["Py ML"],
            "cssclass": "wide",
            "random_field": True,
        })
        meta = schema.to_document_meta()
        assert meta.tags == ["python", "ml"]
        assert meta.categories == ["tutorial"]
        assert meta.author == "Mike"
        assert meta.extra["aliases"] == ["Py ML"]
        assert meta.extra["cssclass"] == "wide"
        assert meta.extra["random_field"] is True

    def test_none_values_not_in_extra(self) -> None:
        schema = FullSchema.from_frontmatter({"tags": ["a"]})
        meta = schema.to_document_meta()
        assert "author" not in meta.extra
        assert "cssclass" not in meta.extra
        assert "note_type" not in meta.extra

    def test_scalar_string_coerced_to_list_for_categories(self) -> None:
        schema = FullSchema.from_frontmatter({"note_type": "book-note"})
        meta = schema.to_document_meta()
        assert meta.categories == ["book-note"]

    def test_empty_frontmatter(self) -> None:
        schema = FullSchema.from_frontmatter({})
        meta = schema.to_document_meta()
        assert meta.tags == []
        assert meta.categories == []
        assert meta.author is None
        assert meta.extra == {}
