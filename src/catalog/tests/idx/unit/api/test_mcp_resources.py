"""Tests for catalog.api.mcp.resources module."""

from unittest.mock import MagicMock, patch

import pytest

from catalog.api.mcp.resources import (
    _get_mime_type,
    list_resources,
    read_resource,
)
from catalog.search.service import SearchService


class TestListResources:
    """Tests for list_resources function."""

    @pytest.fixture
    def mock_service(self) -> SearchService:
        """Create mock SearchService."""
        mock_session = MagicMock()
        return SearchService(mock_session)

    def test_lists_datasets_as_resources(self, mock_service: SearchService) -> None:
        """list_resources returns datasets as catalog:// URIs."""
        mock_dataset1 = MagicMock()
        mock_dataset1.name = "vault"
        mock_dataset1.source_type = "obsidian"
        mock_dataset1.document_count = 100

        mock_dataset2 = MagicMock()
        mock_dataset2.name = "notes"
        mock_dataset2.source_type = "directory"
        mock_dataset2.document_count = 50

        mock_datasets = [mock_dataset1, mock_dataset2]

        with patch("catalog.api.mcp.resources.DatasetService") as mock_ds_cls:
            mock_ds = MagicMock()
            mock_ds.list_datasets.return_value = mock_datasets
            mock_ds_cls.return_value = mock_ds

            resources = list_resources(mock_service)

            assert len(resources) == 2

            # Check first resource
            assert resources[0]["uri"] == "catalog://vault"
            assert resources[0]["name"] == "vault"
            assert "obsidian" in resources[0]["description"]
            assert "100 documents" in resources[0]["description"]

            # Check second resource
            assert resources[1]["uri"] == "catalog://notes"
            assert resources[1]["name"] == "notes"

    def test_returns_empty_on_no_datasets(self, mock_service: SearchService) -> None:
        """list_resources returns empty list when no datasets."""
        with patch("catalog.api.mcp.resources.DatasetService") as mock_ds_cls:
            mock_ds = MagicMock()
            mock_ds.list_datasets.return_value = []
            mock_ds_cls.return_value = mock_ds

            resources = list_resources(mock_service)

            assert resources == []

    def test_handles_error(self, mock_service: SearchService) -> None:
        """list_resources returns empty list on error."""
        with patch("catalog.api.mcp.resources.DatasetService") as mock_ds_cls:
            mock_ds_cls.side_effect = Exception("DB error")

            resources = list_resources(mock_service)

            assert resources == []

    def test_resource_has_mime_type(self, mock_service: SearchService) -> None:
        """Resources have mimeType field."""
        mock_dataset = MagicMock()
        mock_dataset.name = "vault"
        mock_dataset.source_type = "obsidian"
        mock_dataset.document_count = 10
        mock_datasets = [mock_dataset]

        with patch("catalog.api.mcp.resources.DatasetService") as mock_ds_cls:
            mock_ds = MagicMock()
            mock_ds.list_datasets.return_value = mock_datasets
            mock_ds_cls.return_value = mock_ds

            resources = list_resources(mock_service)

            assert resources[0]["mimeType"] == "application/json"


class TestReadResource:
    """Tests for read_resource function."""

    @pytest.fixture
    def mock_service(self) -> SearchService:
        """Create mock SearchService."""
        mock_session = MagicMock()
        return SearchService(mock_session)

    def test_invalid_uri_scheme(self, mock_service: SearchService) -> None:
        """read_resource raises on invalid URI scheme."""
        with pytest.raises(ValueError, match="Invalid URI scheme"):
            read_resource(mock_service, "http://example.com")

    def test_empty_path(self, mock_service: SearchService) -> None:
        """read_resource raises on empty path."""
        with pytest.raises(ValueError, match="Empty catalog URI path"):
            read_resource(mock_service, "catalog://")

    def test_read_dataset_listing(self, mock_service: SearchService) -> None:
        """read_resource returns document listing for dataset URI."""
        mock_dataset = MagicMock()
        mock_dataset.id = 1
        mock_dataset.name = "vault"
        mock_dataset.source_type = "obsidian"

        mock_doc1 = MagicMock()
        mock_doc1.path = "a.md"
        mock_doc1.title = "A"

        mock_doc2 = MagicMock()
        mock_doc2.path = "b.md"
        mock_doc2.title = "B"

        mock_docs = [mock_doc1, mock_doc2]

        with patch("catalog.api.mcp.resources.DatasetService") as mock_ds_cls:
            mock_ds = MagicMock()
            mock_ds.get_dataset_by_name.return_value = mock_dataset
            mock_ds.list_documents.return_value = mock_docs
            mock_ds_cls.return_value = mock_ds

            contents = read_resource(mock_service, "catalog://vault")

            assert len(contents) == 1
            assert contents[0]["uri"] == "catalog://vault"
            assert contents[0]["mimeType"] == "application/json"

            # Parse JSON content
            import json
            data = json.loads(contents[0]["text"])
            assert data["dataset"] == "vault"
            assert data["document_count"] == 2
            assert len(data["documents"]) == 2

    def test_read_specific_document(self, mock_service: SearchService) -> None:
        """read_resource returns document content for path URI."""
        mock_dataset = MagicMock()
        mock_dataset.id = 1
        mock_dataset.name = "vault"
        mock_doc = MagicMock()
        mock_doc.body = "# Test Document\n\nContent here."

        with patch("catalog.api.mcp.resources.DatasetService") as mock_ds_cls:
            mock_ds = MagicMock()
            mock_ds.get_dataset_by_name.return_value = mock_dataset
            mock_ds.get_document_by_path.return_value = mock_doc
            mock_ds_cls.return_value = mock_ds

            contents = read_resource(mock_service, "catalog://vault/notes/test.md")

            assert len(contents) == 1
            assert contents[0]["uri"] == "catalog://vault/notes/test.md"
            assert contents[0]["text"] == "# Test Document\n\nContent here."
            assert contents[0]["mimeType"] == "text/markdown"

    def test_dataset_not_found(self, mock_service: SearchService) -> None:
        """read_resource returns error for missing dataset."""
        with patch("catalog.api.mcp.resources.DatasetService") as mock_ds_cls:
            mock_ds = MagicMock()
            mock_ds.get_dataset_by_name.side_effect = Exception("Not found")
            mock_ds_cls.return_value = mock_ds

            contents = read_resource(mock_service, "catalog://unknown")

            assert len(contents) == 1
            assert "not found" in contents[0]["text"].lower()

    def test_document_not_found(self, mock_service: SearchService) -> None:
        """read_resource returns error for missing document."""
        mock_dataset = MagicMock()
        mock_dataset.id = 1
        mock_dataset.name = "vault"

        with patch("catalog.api.mcp.resources.DatasetService") as mock_ds_cls:
            mock_ds = MagicMock()
            mock_ds.get_dataset_by_name.return_value = mock_dataset
            mock_ds.get_document_by_path.side_effect = Exception("Not found")
            mock_ds_cls.return_value = mock_ds

            contents = read_resource(mock_service, "catalog://vault/missing.md")

            assert len(contents) == 1
            assert "not found" in contents[0]["text"].lower()


class TestGetMimeType:
    """Tests for _get_mime_type helper."""

    def test_markdown_file(self) -> None:
        """Returns text/markdown for .md files."""
        assert _get_mime_type("notes.md") == "text/markdown"
        assert _get_mime_type("path/to/README.MD") == "text/markdown"

    def test_text_file(self) -> None:
        """Returns text/plain for .txt files."""
        assert _get_mime_type("notes.txt") == "text/plain"

    def test_json_file(self) -> None:
        """Returns application/json for .json files."""
        assert _get_mime_type("config.json") == "application/json"

    def test_yaml_file(self) -> None:
        """Returns text/yaml for .yaml/.yml files."""
        assert _get_mime_type("config.yaml") == "text/yaml"
        assert _get_mime_type("config.yml") == "text/yaml"

    def test_html_file(self) -> None:
        """Returns text/html for .html/.htm files."""
        assert _get_mime_type("page.html") == "text/html"
        assert _get_mime_type("page.htm") == "text/html"

    def test_xml_file(self) -> None:
        """Returns application/xml for .xml files."""
        assert _get_mime_type("data.xml") == "application/xml"

    def test_python_file(self) -> None:
        """Returns text/x-python for .py files."""
        assert _get_mime_type("script.py") == "text/x-python"

    def test_javascript_file(self) -> None:
        """Returns text/javascript for .js files."""
        assert _get_mime_type("app.js") == "text/javascript"

    def test_typescript_file(self) -> None:
        """Returns text/typescript for .ts files."""
        assert _get_mime_type("app.ts") == "text/typescript"

    def test_css_file(self) -> None:
        """Returns text/css for .css files."""
        assert _get_mime_type("styles.css") == "text/css"

    def test_unknown_extension(self) -> None:
        """Returns text/plain for unknown extensions."""
        assert _get_mime_type("file.xyz") == "text/plain"
        assert _get_mime_type("noextension") == "text/plain"

    def test_case_insensitive(self) -> None:
        """Extension matching is case-insensitive."""
        assert _get_mime_type("README.MD") == "text/markdown"
        assert _get_mime_type("CONFIG.JSON") == "application/json"
