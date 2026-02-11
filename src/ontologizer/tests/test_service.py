"""Tests for the ontology service layer."""

from __future__ import annotations

import pytest
import pytest_asyncio
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column

from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from src.ontologizer.service import ReadService, Service, QueryService

# 1. Models and Schemas


class Base(DeclarativeBase):
    pass


class Todo(Base):
    __tablename__ = "todo"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    done: Mapped[bool] = mapped_column(default=False)


class TodoSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    done: bool


# 2. Services


class TodoRepository(SQLAlchemyAsyncRepository[Todo]):
    """Todo repository."""

    model_type = Todo


class TodoReadService(ReadService[Todo]):
    """Todo read service."""

    repository_type = TodoRepository
    schema_type = TodoSchema


class TodoService(Service[Todo]):
    """Todo service."""

    repository_type = TodoRepository
    schema_type = TodoSchema


class TodoQueryService(QueryService):
    """Todo query service for testing."""

    schema_type = TodoSchema

    async def get_by_title(self, title: str) -> Todo | None:
        """Get a todo by title."""
        statement = select(Todo).where(Todo.title == title)
        return await self.repository.get_one_or_none(statement=statement)


class WrappedTodoQueryService(TodoQueryService):
    """A query service that has a custom method whitelisted."""

    _CONVERT_TO_SCHEMA_WHITELIST = ["get_by_title"]


# 3. Fixtures


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    """In-memory SQLite session."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    async with Session() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def todo_read_service(session: AsyncSession) -> TodoReadService:
    """Todo read service fixture."""
    return TodoReadService(session=session)


@pytest_asyncio.fixture
async def todo_service(session: AsyncSession) -> TodoService:
    """Todo service fixture."""
    return TodoService(session=session)


@pytest_asyncio.fixture
async def todo_query_service(session: AsyncSession) -> TodoQueryService:
    """Todo query service fixture."""
    return TodoQueryService(session=session)


@pytest_asyncio.fixture
async def wrapped_todo_query_service(session: AsyncSession) -> WrappedTodoQueryService:
    """Wrapped todo query service fixture."""
    return WrappedTodoQueryService(session=session)


# 4. Tests


@pytest.mark.asyncio
async def test_get_returns_schema(todo_service: TodoService) -> None:
    """Test that get() returns a Pydantic schema."""
    todo = await todo_service.create(Todo(title="test"))
    assert isinstance(todo, TodoSchema)

    retrieved_todo = await todo_service.get(todo.id)
    assert isinstance(retrieved_todo, TodoSchema)


@pytest.mark.asyncio
async def test_list_returns_schema_list(todo_service: TodoService) -> None:
    """Test that list() returns a list of Pydantic schemas."""
    await todo_service.create(Todo(title="test1"))
    await todo_service.create(Todo(title="test2"))

    todos = await todo_service.list()
    assert isinstance(todos, list)
    assert len(todos) == 2
    assert all(isinstance(t, TodoSchema) for t in todos)


@pytest.mark.asyncio
async def test_list_and_count_returns_schema_list(todo_service: TodoService) -> None:
    """Test that list_and_count() returns a tuple with a list of schemas."""
    await todo_service.create(Todo(title="test1"))
    await todo_service.create(Todo(title="test2"))

    todos, count = await todo_service.list_and_count()
    assert isinstance(todos, list)
    assert count == 2
    assert all(isinstance(t, TodoSchema) for t in todos)


@pytest.mark.asyncio
async def test_create_returns_schema(todo_service: TodoService) -> None:
    """Test that create() returns a Pydantic schema."""
    todo = await todo_service.create(Todo(title="test"))
    assert isinstance(todo, TodoSchema)


@pytest.mark.asyncio
async def test_update_returns_schema(todo_service: TodoService) -> None:
    """Test that update() returns a Pydantic schema."""
    todo = await todo_service.create(Todo(title="test"))
    updated_todo = await todo_service.update(Todo(id=todo.id, title="updated"))
    assert isinstance(updated_todo, TodoSchema)
    assert updated_todo.title == "updated"


@pytest.mark.asyncio
async def test_delete_returns_schema(todo_service: TodoService) -> None:
    """Test that delete() returns a Pydantic schema."""
    todo = await todo_service.create(Todo(title="test"))
    deleted_todo = await todo_service.delete(todo.id)
    assert isinstance(deleted_todo, TodoSchema)


@pytest.mark.asyncio
async def test_query_service_returns_orm_instance(
    todo_query_service: TodoQueryService,
    session: AsyncSession,
) -> None:
    """Test that a custom query service method returns an ORM instance by default."""
    # Use session directly to add test data
    session.add(Todo(title="test_query"))
    await session.commit()

    todo = await todo_query_service.get_by_title("test_query")
    assert isinstance(todo, Todo)


@pytest.mark.asyncio
async def test_wrapped_query_service_returns_schema(
    wrapped_todo_query_service: WrappedTodoQueryService,
    session: AsyncSession,
) -> None:
    """Test that a whitelisted custom method returns a Pydantic schema."""
    # Use session directly to add test data
    session.add(Todo(title="test_wrapped_query"))
    await session.commit()

    todo = await wrapped_todo_query_service.get_by_title("test_wrapped_query")
    assert isinstance(todo, TodoSchema)
