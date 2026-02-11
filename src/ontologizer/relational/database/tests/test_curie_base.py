"""Tests for CURIE-based ORM base class.

This module tests the CURIEBase class and CURIEPrimaryKey mixin,
verifying that models using CURIE IDs (string primary keys) work correctly
with proper audit columns (created_at, updated_at).
"""

import pytest
from datetime import datetime, UTC
from sqlalchemy import create_engine, select, inspect
from sqlalchemy.orm import Session, Mapped, mapped_column
from sqlalchemy import String

from ontologizer.relational.database.models.curie import Base, CURIEBase


class TestModel(CURIEBase):
    """Test model using CURIEBase for testing purposes."""

    __tablename__ = "test_curie_model"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)


@pytest.fixture
def in_memory_engine():
    """Create an in-memory SQLite engine for isolated testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(in_memory_engine):
    """Provide a database session for each test."""
    with Session(in_memory_engine) as session:
        yield session
        session.rollback()


class TestCURIEPrimaryKey:
    """Test the CURIEPrimaryKey mixin behavior."""

    def test_table_has_id_column(self, in_memory_engine):
        """Verify that models using CURIEBase have an 'id' column."""
        inspector = inspect(in_memory_engine)
        columns = {
            col["name"]: col for col in inspector.get_columns("test_curie_model")
        }

        assert "id" in columns
        assert columns["id"]["type"].length == 255
        assert columns["id"]["primary_key"]  # Can be True or 1 depending on database
        assert columns["id"]["nullable"] is False

    def test_id_column_is_string_type(self, db_session):
        """Verify that the id column accepts string values (CURIE format)."""
        test_obj = TestModel(id="test:12345", name="Test Object")
        db_session.add(test_obj)
        db_session.commit()

        result = db_session.execute(
            select(TestModel).where(TestModel.id == "test:12345")
        ).scalar_one()

        assert result.id == "test:12345"
        assert isinstance(result.id, str)

    def test_id_must_be_unique(self, db_session):
        """Verify that duplicate IDs raise an integrity error."""
        obj1 = TestModel(id="test:duplicate", name="First")
        obj2 = TestModel(id="test:duplicate", name="Second")

        db_session.add(obj1)
        db_session.commit()

        db_session.add(obj2)
        with pytest.raises(Exception):  # SQLAlchemy will raise IntegrityError
            db_session.commit()

    def test_id_cannot_be_null(self, db_session):
        """Verify that id field cannot be null."""
        test_obj = TestModel(name="Test without ID")
        # id should be required - attempting to commit without it should fail
        db_session.add(test_obj)
        with pytest.raises(Exception):  # Will raise an error due to NOT NULL constraint
            db_session.commit()


class TestCURIEBaseAuditColumns:
    """Test the audit column functionality from AuditColumns mixin."""

    def test_table_has_audit_columns(self, in_memory_engine):
        """Verify that models have created_at and updated_at columns."""
        inspector = inspect(in_memory_engine)
        columns = {col["name"] for col in inspector.get_columns("test_curie_model")}

        assert "created_at" in columns
        assert "updated_at" in columns

    def test_created_at_set_on_insert(self, db_session):
        """Verify that created_at is automatically set when inserting."""
        before = datetime.now(UTC)

        test_obj = TestModel(id="test:audit001", name="Audit Test")
        db_session.add(test_obj)
        db_session.commit()

        after = datetime.now(UTC)

        result = db_session.execute(
            select(TestModel).where(TestModel.id == "test:audit001")
        ).scalar_one()

        assert result.created_at is not None
        assert before <= result.created_at <= after

    def test_updated_at_set_on_insert(self, db_session):
        """Verify that updated_at is automatically set when inserting."""
        before = datetime.now(UTC)

        test_obj = TestModel(id="test:audit002", name="Update Test")
        db_session.add(test_obj)
        db_session.commit()

        after = datetime.now(UTC)

        result = db_session.execute(
            select(TestModel).where(TestModel.id == "test:audit002")
        ).scalar_one()

        assert result.updated_at is not None
        assert before <= result.updated_at <= after

    def test_updated_at_changes_on_update(self, db_session):
        """Verify that updated_at is updated when the record is modified."""
        test_obj = TestModel(id="test:audit003", name="Original Name")
        db_session.add(test_obj)
        db_session.commit()

        original_updated = test_obj.updated_at

        # Update the object
        test_obj.name = "Modified Name"
        db_session.commit()

        # Refresh from database
        db_session.refresh(test_obj)

        assert test_obj.updated_at > original_updated
        assert test_obj.name == "Modified Name"

    def test_created_at_does_not_change_on_update(self, db_session):
        """Verify that created_at remains constant after updates."""
        test_obj = TestModel(id="test:audit004", name="Original Name")
        db_session.add(test_obj)
        db_session.commit()

        original_created = test_obj.created_at

        # Update the object
        test_obj.name = "Modified Name"
        db_session.commit()

        # Refresh from database
        db_session.refresh(test_obj)

        assert test_obj.created_at == original_created


class TestCURIEBaseCRUD:
    """Test basic CRUD operations with CURIEBase models."""

    def test_create_and_read(self, db_session):
        """Test creating and reading a CURIE-based model."""
        test_obj = TestModel(
            id="test:crud001", name="CRUD Test", description="Testing CRUD operations"
        )
        db_session.add(test_obj)
        db_session.commit()

        result = db_session.execute(
            select(TestModel).where(TestModel.id == "test:crud001")
        ).scalar_one()

        assert result.id == "test:crud001"
        assert result.name == "CRUD Test"
        assert result.description == "Testing CRUD operations"

    def test_update(self, db_session):
        """Test updating a CURIE-based model."""
        test_obj = TestModel(
            id="test:crud002", name="Original", description="Original description"
        )
        db_session.add(test_obj)
        db_session.commit()

        # Update
        test_obj.name = "Updated"
        test_obj.description = "Updated description"
        db_session.commit()

        # Verify
        result = db_session.execute(
            select(TestModel).where(TestModel.id == "test:crud002")
        ).scalar_one()

        assert result.name == "Updated"
        assert result.description == "Updated description"

    def test_delete(self, db_session):
        """Test deleting a CURIE-based model."""
        test_obj = TestModel(id="test:crud003", name="To Be Deleted")
        db_session.add(test_obj)
        db_session.commit()

        # Delete
        db_session.delete(test_obj)
        db_session.commit()

        # Verify deletion
        result = db_session.execute(
            select(TestModel).where(TestModel.id == "test:crud003")
        ).scalar_one_or_none()

        assert result is None

    def test_query_multiple_records(self, db_session):
        """Test querying multiple CURIE-based records."""
        objects = [
            TestModel(id=f"test:multi{i:03d}", name=f"Object {i}") for i in range(5)
        ]
        db_session.add_all(objects)
        db_session.commit()

        results = db_session.execute(select(TestModel)).scalars().all()

        assert len(results) >= 5  # At least our 5 objects
        ids = {r.id for r in results}
        for i in range(5):
            assert f"test:multi{i:03d}" in ids


class TestCURIEFormat:
    """Test that CURIE format IDs work correctly."""

    def test_various_curie_formats(self, db_session):
        """Test that different CURIE format IDs are accepted."""
        test_cases = [
            "prefix:12345",
            "namespace:id123",
            "domain:resource/path",
            "schema:entity-name",
            "db:uuid-style-id-abc123",
        ]

        for curie_id in test_cases:
            obj = TestModel(id=curie_id, name=f"Test for {curie_id}")
            db_session.add(obj)

        db_session.commit()

        # Verify all were created
        for curie_id in test_cases:
            result = db_session.execute(
                select(TestModel).where(TestModel.id == curie_id)
            ).scalar_one()
            assert result.id == curie_id

    def test_long_curie_within_limit(self, db_session):
        """Test that CURIE IDs up to 255 characters work."""
        long_id = "prefix:" + "a" * 240  # Total length close to 255

        test_obj = TestModel(id=long_id, name="Long CURIE test")
        db_session.add(test_obj)
        db_session.commit()

        result = db_session.execute(
            select(TestModel).where(TestModel.id == long_id)
        ).scalar_one()

        assert result.id == long_id
        assert len(result.id) <= 255
