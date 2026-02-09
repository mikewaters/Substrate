"""Tests for catalog.transform.ontology — OntologyMapper."""

import json

import pytest
from llama_index.core.schema import Document as LlamaDocument
from pydantic import Field

from catalog.integrations.obsidian import VaultSpec
from catalog.transform.ontology import OntologyMapper


def _make_node(**metadata: object) -> LlamaDocument:
    """Helper to build a LlamaIndex Document with given metadata."""
    return LlamaDocument(text="body text", metadata=dict(metadata))


# --- Test vault schema for use in tests ---

class SampleVaultSpec(VaultSpec):
    tags: list[str] = Field(default_factory=list, json_schema_extra={"maps_to": "tags"})
    note_type: str | None = Field(None, json_schema_extra={"maps_to": "categories"})
    aliases: list[str] = Field(default_factory=list)
    cssclass: str | None = None


# --- Title derivation (absorbed from ObsidianEnrichmentTransform) ---

class TestTitleDerivation:
    """Title is derived with correct priority ordering."""

    @pytest.fixture
    def transform(self) -> OntologyMapper:
        return OntologyMapper()

    def test_frontmatter_title_wins(self, transform: OntologyMapper) -> None:
        node = _make_node(
            frontmatter={"title": "FM Title", "aliases": ["Alias1"]},
            note_name="NoteName",
        )
        [result] = transform([node])
        assert result.metadata["title"] == "FM Title"

    def test_first_alias_when_no_title(self, transform: OntologyMapper) -> None:
        node = _make_node(
            frontmatter={"aliases": ["Alias1", "Alias2"]},
            note_name="NoteName",
        )
        [result] = transform([node])
        assert result.metadata["title"] == "Alias1"

    def test_note_name_fallback(self, transform: OntologyMapper) -> None:
        node = _make_node(frontmatter={}, note_name="My Note Name")
        [result] = transform([node])
        assert result.metadata["title"] == "My Note Name"

    def test_note_name_when_no_frontmatter(self, transform: OntologyMapper) -> None:
        node = _make_node(note_name="Fallback Name")
        [result] = transform([node])
        assert result.metadata["title"] == "Fallback Name"

    def test_empty_title_skipped(self, transform: OntologyMapper) -> None:
        node = _make_node(
            frontmatter={"title": "   ", "aliases": ["Good Alias"]},
            note_name="NoteName",
        )
        [result] = transform([node])
        assert result.metadata["title"] == "Good Alias"

    def test_title_is_stripped(self, transform: OntologyMapper) -> None:
        node = _make_node(
            frontmatter={"title": "  Padded Title  "},
            note_name="NoteName",
        )
        [result] = transform([node])
        assert result.metadata["title"] == "Padded Title"


# --- Description derivation ---

class TestDescriptionDerivation:
    """Description is derived with correct priority ordering."""

    @pytest.fixture
    def transform(self) -> OntologyMapper:
        return OntologyMapper()

    def test_frontmatter_description_wins(self, transform: OntologyMapper) -> None:
        node = _make_node(
            frontmatter={"description": "FM Desc"},
            summary="Summary text",
            note_name="N",
        )
        [result] = transform([node])
        assert result.metadata["description"] == "FM Desc"

    def test_summary_fallback(self, transform: OntologyMapper) -> None:
        node = _make_node(
            frontmatter={},
            summary="Summary text",
            note_name="N",
        )
        [result] = transform([node])
        assert result.metadata["description"] == "Summary text"

    def test_none_when_nothing_available(self, transform: OntologyMapper) -> None:
        node = _make_node(frontmatter={}, note_name="N")
        [result] = transform([node])
        assert result.metadata["description"] is None

    def test_empty_description_skipped(self, transform: OntologyMapper) -> None:
        node = _make_node(
            frontmatter={"description": "   "},
            summary="Good Summary",
            note_name="N",
        )
        [result] = transform([node])
        assert result.metadata["description"] == "Good Summary"


# --- Ontology metadata output ---

class TestOntologyMetadata:
    """_ontology_meta is written correctly."""

    def test_ontology_meta_present(self) -> None:
        transform = OntologyMapper()
        node = _make_node(
            frontmatter={"title": "T", "tags": ["a"]},
            note_name="N",
        )
        [result] = transform([node])
        ontology = result.metadata["_ontology_meta"]
        assert ontology["title"] == "T"
        assert ontology["tags"] == ["a"]

    def test_ontology_meta_with_ontology_spec(self) -> None:
        transform = OntologyMapper(ontology_spec_cls=SampleVaultSpec)
        node = _make_node(
            frontmatter={
                "tags": ["python"],
                "note_type": "tutorial",
                "aliases": ["Py"],
                "cssclass": "wide",
            },
            note_name="N",
        )
        [result] = transform([node])
        ontology = result.metadata["_ontology_meta"]
        assert ontology["tags"] == ["python"]
        assert ontology["categories"] == ["tutorial"]
        assert ontology["extra"]["aliases"] == ["Py"]
        assert ontology["extra"]["cssclass"] == "wide"

    def test_ontology_meta_serializable(self) -> None:
        transform = OntologyMapper()
        node = _make_node(
            frontmatter={"title": "T", "tags": ["a", "b"]},
            note_name="N",
        )
        [result] = transform([node])
        # Should be JSON-serializable.
        serialized = json.dumps(result.metadata["_ontology_meta"])
        assert isinstance(serialized, str)


# --- Frontmatter key removal ---

class TestFrontmatterRemoval:
    """Raw frontmatter key is removed after processing."""

    def test_frontmatter_key_removed(self) -> None:
        transform = OntologyMapper()
        node = _make_node(
            frontmatter={"title": "T"},
            note_name="N",
        )
        [result] = transform([node])
        assert "frontmatter" not in result.metadata

    def test_custom_frontmatter_key_removed(self) -> None:
        transform = OntologyMapper(frontmatter_key="fm")
        node = _make_node(fm={"title": "T"}, note_name="N")
        [result] = transform([node])
        assert "fm" not in result.metadata


# --- Promote keys ---

class TestPromoteKeys:
    """Selected ontology fields are promoted to top-level node.metadata."""

    def test_default_promotes_tags_and_categories(self) -> None:
        transform = OntologyMapper()
        node = _make_node(
            frontmatter={"tags": ["a", "b"], "type": "tutorial"},
            note_name="N",
        )
        [result] = transform([node])
        assert result.metadata["tags"] == ["a", "b"]
        assert result.metadata["categories"] == ["tutorial"]

    def test_default_does_not_promote_author(self) -> None:
        transform = OntologyMapper()
        node = _make_node(
            frontmatter={"author": "Mike"},
            note_name="N",
        )
        [result] = transform([node])
        assert "author" not in result.metadata

    def test_custom_promote_keys(self) -> None:
        transform = OntologyMapper(promote_keys=["tags", "author"])
        node = _make_node(
            frontmatter={"tags": ["x"], "author": "Mike", "type": "note"},
            note_name="N",
        )
        [result] = transform([node])
        assert result.metadata["tags"] == ["x"]
        assert result.metadata["author"] == "Mike"
        # categories not promoted since not in promote_keys.
        assert "categories" not in result.metadata

    def test_empty_promote_keys(self) -> None:
        transform = OntologyMapper(promote_keys=[])
        node = _make_node(
            frontmatter={"tags": ["a"]},
            note_name="N",
        )
        [result] = transform([node])
        # tags/categories should NOT be in top-level metadata.
        assert "tags" not in result.metadata
        assert "categories" not in result.metadata
        # But should still be in _ontology_meta.
        assert result.metadata["_ontology_meta"]["tags"] == ["a"]

    def test_empty_values_not_promoted(self) -> None:
        transform = OntologyMapper()
        node = _make_node(frontmatter={}, note_name="N")
        [result] = transform([node])
        assert "tags" not in result.metadata
        assert "categories" not in result.metadata

    def test_invalid_promote_key_ignored(self) -> None:
        transform = OntologyMapper(promote_keys=["tags", "extra", "bogus"])
        node = _make_node(
            frontmatter={"tags": ["a"]},
            note_name="N",
        )
        [result] = transform([node])
        assert result.metadata["tags"] == ["a"]
        assert "extra" not in result.metadata
        assert "bogus" not in result.metadata

    def test_promote_with_ontology_spec(self) -> None:
        transform = OntologyMapper(
            ontology_spec_cls=SampleVaultSpec,
            promote_keys=["tags", "categories"],
        )
        node = _make_node(
            frontmatter={"tags": ["python"], "note_type": "tutorial"},
            note_name="N",
        )
        [result] = transform([node])
        assert result.metadata["tags"] == ["python"]
        assert result.metadata["categories"] == ["tutorial"]


# --- Best-effort mode (no schema) ---

class TestBestEffortMode:
    """Without a vault schema, frontmatter is mapped best-effort."""

    def test_tags_extracted(self) -> None:
        transform = OntologyMapper()
        node = _make_node(frontmatter={"tags": ["a", "b"]}, note_name="N")
        [result] = transform([node])
        assert result.metadata["_ontology_meta"]["tags"] == ["a", "b"]

    def test_type_maps_to_categories(self) -> None:
        transform = OntologyMapper()
        node = _make_node(frontmatter={"type": "tutorial"}, note_name="N")
        [result] = transform([node])
        assert result.metadata["_ontology_meta"]["categories"] == ["tutorial"]

    def test_unknown_keys_to_extra(self) -> None:
        transform = OntologyMapper()
        node = _make_node(
            frontmatter={"cssclass": "wide", "custom": 42},
            note_name="N",
        )
        [result] = transform([node])
        extra = result.metadata["_ontology_meta"]["extra"]
        assert extra["cssclass"] == "wide"
        assert extra["custom"] == 42


# --- Schema validation fallback ---

class TestSchemaValidationFallback:
    """When schema validation fails, falls back to best-effort."""

    def test_fallback_on_validation_error(self) -> None:
        """A schema that might fail gracefully falls back."""

        class StrictSchema(VaultSpec):
            tags: list[str] = Field(
                json_schema_extra={"maps_to": "tags"},
            )

        # Missing required field 'tags' — Pydantic should raise.
        # But strict=False should catch and fall back.
        transform = OntologyMapper(ontology_spec_cls=StrictSchema, strict=False)
        node = _make_node(frontmatter={"random": "data"}, note_name="N")
        [result] = transform([node])
        # Should still produce _ontology_meta via best-effort.
        assert "_ontology_meta" in result.metadata


# --- Batch processing ---

class TestBatchProcessing:
    """Transform handles multiple nodes correctly."""

    def test_multiple_nodes(self) -> None:
        transform = OntologyMapper()
        nodes = [
            _make_node(frontmatter={"title": "A"}, note_name="a"),
            _make_node(note_name="b"),
            _make_node(frontmatter={"title": "C", "description": "Desc C"}, note_name="c"),
        ]
        results = transform(nodes)
        assert len(results) == 3
        assert results[0].metadata["title"] == "A"
        assert results[1].metadata["title"] == "b"
        assert results[2].metadata["title"] == "C"
        assert results[2].metadata["description"] == "Desc C"

    def test_empty_metadata_node_passed_through(self) -> None:
        transform = OntologyMapper()
        node = LlamaDocument(text="bare node")
        node.metadata = {}
        results = transform([node])
        assert len(results) == 1
