"""FastAPI REST API for ontology.

This module provides HTTP endpoints for taxonomy and topic management,
including CRUD operations, search, and hierarchy traversal.
"""

from ontology.api.app import app, create_app

__all__ = ["app", "create_app"]
