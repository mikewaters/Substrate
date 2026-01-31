"""Tests for OpenAPI specification validation."""

import pytest
from fastapi.testclient import TestClient

from ontology.api.app import create_app


class TestOpenAPISpec:
    """Test cases for OpenAPI specification."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_app()
        return TestClient(app)

    def test_openapi_json_endpoint(self, client):
        """Test that OpenAPI JSON endpoint is accessible."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        spec = response.json()
        assert "openapi" in spec
        assert "info" in spec
        assert "paths" in spec

    def test_docs_endpoint(self, client):
        """Test that Swagger UI is accessible."""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "swagger" in response.text.lower()

    def test_redoc_endpoint(self, client):
        """Test that ReDoc UI is accessible."""
        response = client.get("/redoc")
        assert response.status_code == 200
        assert "redoc" in response.text.lower()
