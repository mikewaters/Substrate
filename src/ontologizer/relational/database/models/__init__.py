"""SQLAlchemy ORM models for the ontology database.

This module exports all database models and the declarative base.
"""

from typing import Any
from ontologizer.relational.database.models.curie import CURIEBase, Base, IdBase

JSONDict = dict[str, Any]

__all__ = ["CURIEBase", "Base", "IdBase", "JSONDict"]
