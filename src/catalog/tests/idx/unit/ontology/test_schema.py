"""Tests for catalog.ontology.schema — DocumentMeta dataclass."""

import pytest

from catalog.ontology.schema import DocumentMeta


class TestDocumentMetaToDict:
    """to_dict() produces compact output, omitting None/empty values."""

    def test_empty_meta_produces_empty_dict(self) -> None:
        meta = DocumentMeta()
        assert meta.to_dict() == {}

    def test_title_only(self) -> None:
        meta = DocumentMeta(title="Hello")
        assert meta.to_dict() == {"title": "Hello"}

    def test_all_fields_populated(self) -> None:
        meta = DocumentMeta(
            title="T",
            description="D",
            tags=["a", "b"],
            categories=["c"],
            author="Me",
            extra={"cssclass": "wide"},
        )
        result = meta.to_dict()
        assert result == {
            "title": "T",
            "description": "D",
            "tags": ["a", "b"],
            "categories": ["c"],
            "author": "Me",
            "extra": {"cssclass": "wide"},
        }

    def test_empty_lists_omitted(self) -> None:
        meta = DocumentMeta(title="T", tags=[], categories=[])
        assert meta.to_dict() == {"title": "T"}

    def test_empty_extra_omitted(self) -> None:
        meta = DocumentMeta(title="T", extra={})
        assert "extra" not in meta.to_dict()

    def test_none_fields_omitted(self) -> None:
        meta = DocumentMeta(tags=["x"])
        result = meta.to_dict()
        assert "title" not in result
        assert "description" not in result
        assert "author" not in result
        assert result == {"tags": ["x"]}


class TestDocumentMetaFromDict:
    """from_dict() round-trips correctly."""

    def test_empty_dict(self) -> None:
        meta = DocumentMeta.from_dict({})
        assert meta.title is None
        assert meta.tags == []
        assert meta.extra == {}

    def test_full_round_trip(self) -> None:
        original = DocumentMeta(
            title="T",
            description="D",
            tags=["a"],
            categories=["b"],
            author="A",
            extra={"k": "v"},
        )
        restored = DocumentMeta.from_dict(original.to_dict())
        assert restored == original

    def test_missing_keys_get_defaults(self) -> None:
        meta = DocumentMeta.from_dict({"title": "Only Title"})
        assert meta.title == "Only Title"
        assert meta.description is None
        assert meta.tags == []
        assert meta.categories == []
        assert meta.author is None
        assert meta.extra == {}

    def test_round_trip_empty_meta(self) -> None:
        original = DocumentMeta()
        restored = DocumentMeta.from_dict(original.to_dict())
        assert restored == original
