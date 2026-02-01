"""Tests for catalog.transform.obsidian module."""

import pytest
from llama_index.core.schema import Document as LlamaDocument

from catalog.transform.obsidian import ObsidianEnrichmentTransform


def _make_node(**metadata: object) -> LlamaDocument:
    """Helper to build a LlamaIndex Document with given metadata."""
    return LlamaDocument(text="body text", metadata=dict(metadata))


class TestTitleDerivation:
    """Title is derived with correct priority ordering."""

    @pytest.fixture
    def transform(self) -> ObsidianEnrichmentTransform:
        return ObsidianEnrichmentTransform()

    def test_frontmatter_title_wins(self, transform: ObsidianEnrichmentTransform) -> None:
        """Explicit frontmatter title takes priority over everything."""
        node = _make_node(
            frontmatter={"title": "FM Title", "aliases": ["Alias1"]},
            note_name="NoteName",
        )
        [result] = transform([node])
        assert result.metadata["title"] == "FM Title"

    def test_first_alias_when_no_title(self, transform: ObsidianEnrichmentTransform) -> None:
        """First alias is used when no frontmatter title."""
        node = _make_node(
            frontmatter={"aliases": ["Alias1", "Alias2"]},
            note_name="NoteName",
        )
        [result] = transform([node])
        assert result.metadata["title"] == "Alias1"

    def test_note_name_fallback(self, transform: ObsidianEnrichmentTransform) -> None:
        """note_name is used when no frontmatter title or aliases."""
        node = _make_node(
            frontmatter={},
            note_name="My Note Name",
        )
        [result] = transform([node])
        assert result.metadata["title"] == "My Note Name"

    def test_note_name_when_no_frontmatter(self, transform: ObsidianEnrichmentTransform) -> None:
        """note_name is used when frontmatter key is absent entirely."""
        node = _make_node(note_name="Fallback Name")
        [result] = transform([node])
        assert result.metadata["title"] == "Fallback Name"

    def test_empty_title_skipped(self, transform: ObsidianEnrichmentTransform) -> None:
        """Whitespace-only frontmatter title falls through to aliases."""
        node = _make_node(
            frontmatter={"title": "   ", "aliases": ["Good Alias"]},
            note_name="NoteName",
        )
        [result] = transform([node])
        assert result.metadata["title"] == "Good Alias"

    def test_empty_aliases_skipped(self, transform: ObsidianEnrichmentTransform) -> None:
        """Empty aliases list falls through to note_name."""
        node = _make_node(
            frontmatter={"aliases": []},
            note_name="NoteName",
        )
        [result] = transform([node])
        assert result.metadata["title"] == "NoteName"

    def test_non_string_alias_skipped(self, transform: ObsidianEnrichmentTransform) -> None:
        """Non-string first alias falls through to note_name."""
        node = _make_node(
            frontmatter={"aliases": [123, "StringAlias"]},
            note_name="NoteName",
        )
        [result] = transform([node])
        assert result.metadata["title"] == "NoteName"

    def test_title_is_stripped(self, transform: ObsidianEnrichmentTransform) -> None:
        """Derived title values are stripped of whitespace."""
        node = _make_node(
            frontmatter={"title": "  Padded Title  "},
            note_name="NoteName",
        )
        [result] = transform([node])
        assert result.metadata["title"] == "Padded Title"

    def test_no_metadata_node_not_enriched(self, transform: ObsidianEnrichmentTransform) -> None:
        """Node with empty metadata is passed through without enrichment."""
        node = LlamaDocument(text="body")
        node.metadata = {}
        results = transform([node])
        assert "title" not in results[0].metadata


class TestDescriptionDerivation:
    """Description is derived with correct priority ordering."""

    @pytest.fixture
    def transform(self) -> ObsidianEnrichmentTransform:
        return ObsidianEnrichmentTransform()

    def test_frontmatter_description_wins(self, transform: ObsidianEnrichmentTransform) -> None:
        """Explicit frontmatter description takes priority."""
        node = _make_node(
            frontmatter={"description": "FM Desc"},
            summary="Summary text",
            note_name="N",
        )
        [result] = transform([node])
        assert result.metadata["description"] == "FM Desc"

    def test_summary_fallback(self, transform: ObsidianEnrichmentTransform) -> None:
        """Summary key is used when no frontmatter description."""
        node = _make_node(
            frontmatter={},
            summary="Summary text",
            note_name="N",
        )
        [result] = transform([node])
        assert result.metadata["description"] == "Summary text"

    def test_none_when_nothing_available(self, transform: ObsidianEnrichmentTransform) -> None:
        """Description is None when no sources are available."""
        node = _make_node(frontmatter={}, note_name="N")
        [result] = transform([node])
        assert result.metadata["description"] is None

    def test_empty_description_skipped(self, transform: ObsidianEnrichmentTransform) -> None:
        """Whitespace-only frontmatter description falls through."""
        node = _make_node(
            frontmatter={"description": "   "},
            summary="Good Summary",
            note_name="N",
        )
        [result] = transform([node])
        assert result.metadata["description"] == "Good Summary"

    def test_custom_summary_key(self) -> None:
        """Custom summary_key is respected."""
        transform = ObsidianEnrichmentTransform(summary_key="ai_summary")
        node = _make_node(
            frontmatter={},
            ai_summary="AI-generated summary",
            note_name="N",
        )
        [result] = transform([node])
        assert result.metadata["description"] == "AI-generated summary"


class TestLinkNormalization:
    """Wikilinks and backlinks are normalized into prefixed keys."""

    @pytest.fixture
    def transform(self) -> ObsidianEnrichmentTransform:
        return ObsidianEnrichmentTransform()

    def test_wikilinks_normalized(self, transform: ObsidianEnrichmentTransform) -> None:
        """Wikilinks are copied to _obsidian_wikilinks."""
        links = ["Page A", "Page B"]
        node = _make_node(wikilinks=links, note_name="N")
        [result] = transform([node])
        assert result.metadata["_obsidian_wikilinks"] == links

    def test_backlinks_normalized(self, transform: ObsidianEnrichmentTransform) -> None:
        """Backlinks are copied to _obsidian_backlinks."""
        links = ["Referring Page"]
        node = _make_node(backlinks=links, note_name="N")
        [result] = transform([node])
        assert result.metadata["_obsidian_backlinks"] == links

    def test_no_links_no_keys(self, transform: ObsidianEnrichmentTransform) -> None:
        """When no links present, prefixed keys are not added."""
        node = _make_node(note_name="N")
        [result] = transform([node])
        assert "_obsidian_wikilinks" not in result.metadata
        assert "_obsidian_backlinks" not in result.metadata

    def test_non_list_links_ignored(self, transform: ObsidianEnrichmentTransform) -> None:
        """Non-list wikilinks/backlinks values are ignored."""
        node = _make_node(wikilinks="not a list", backlinks=42, note_name="N")
        [result] = transform([node])
        assert "_obsidian_wikilinks" not in result.metadata
        assert "_obsidian_backlinks" not in result.metadata


class TestCustomKeys:
    """Custom key configuration works correctly."""

    def test_custom_title_key(self) -> None:
        """Custom title_key writes to the configured key."""
        transform = ObsidianEnrichmentTransform(title_key="derived_title")
        node = _make_node(note_name="My Note")
        [result] = transform([node])
        assert result.metadata["derived_title"] == "My Note"
        assert "title" not in result.metadata

    def test_custom_description_key(self) -> None:
        """Custom description_key writes to the configured key."""
        transform = ObsidianEnrichmentTransform(description_key="derived_desc")
        node = _make_node(
            frontmatter={"description": "Hello"},
            note_name="N",
        )
        [result] = transform([node])
        assert result.metadata["derived_desc"] == "Hello"

    def test_custom_frontmatter_key(self) -> None:
        """Custom frontmatter_key reads from the configured key."""
        transform = ObsidianEnrichmentTransform(frontmatter_key="fm")
        node = _make_node(
            fm={"title": "Custom FM Title"},
            note_name="Fallback",
        )
        [result] = transform([node])
        assert result.metadata["title"] == "Custom FM Title"


class TestMultipleNodes:
    """Transform processes multiple nodes correctly."""

    def test_batch_processing(self) -> None:
        """All nodes in a batch are enriched."""
        transform = ObsidianEnrichmentTransform()
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

    def test_empty_metadata_node_skipped(self) -> None:
        """Nodes with no metadata are passed through without error."""
        transform = ObsidianEnrichmentTransform()
        node = LlamaDocument(text="bare node")
        # Force empty metadata (LlamaIndex sets {} by default)
        node.metadata = {}
        results = transform([node])
        assert len(results) == 1
