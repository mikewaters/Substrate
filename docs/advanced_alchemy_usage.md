# Advanced Alchemy Usage Guide

This document provides a detailed overview of the services and repositories available in `advanced-alchemy`.

## Repositories

This section covers the repository classes from `advanced_alchemy/repository/_async.py`. The repository layer is responsible for direct database interaction.

### `SQLAlchemyAsyncRepository`

An async SQLAlchemy repository implementation that provides a complete set of operations for interacting with a database.

#### Methods

- **`add(self, data: ModelT, ...) -> ModelT`**
  > Adds a model instance to the database session.

- **`add_many(self, data: list[ModelT], ...) -> Sequence[ModelT]`**
  > Adds multiple model instances to the database session.

- **`count(self, *filters, **kwargs) -> int`**
  > Returns a count of records that match the given filters.

- **`delete(self, item_id: Any, ...) -> ModelT`**
  > Deletes a model instance identified by its ID.

- **`delete_many(self, item_ids: list[Any], ...) -> Sequence[ModelT]`**
  > Deletes multiple instances identified by their IDs.

- **`delete_where(self, *filters, **kwargs) -> Sequence[ModelT]`**
  > Deletes instances matching the given filters.

- **`exists(self, *filters, **kwargs) -> bool`**
  > Checks if any instance matches the given filters.

- **`get(self, item_id: Any, ...) -> ModelT`**
  > Retrieves a single instance by its ID. Raises `NotFoundError` if not found.

- **`get_one(self, *filters, **kwargs) -> ModelT`**
  > Retrieves a single instance matching the filters. Raises `NotFoundError` if not found.

- **`get_one_or_none(self, *filters, **kwargs) -> ModelT | None`**
  > Retrieves a single instance matching the filters, or `None` if not found.

- **`get_or_upsert(self, *filters, **kwargs) -> tuple[ModelT, bool]`**
  > Retrieves an instance or creates it if it doesn't exist.

- **`get_and_update(self, *filters, **kwargs) -> tuple[ModelT, bool]`**
  > Retrieves an instance and updates it if the new data is different.

- **`list(self, *filters, **kwargs) -> list[ModelT]`**
  > Retrieves a list of instances matching the filters.

- **`list_and_count(self, *filters, **kwargs) -> tuple[list[ModelT], int]`**
  > Retrieves a list of instances and the total count of matching records.

- **`update(self, data: ModelT, ...) -> ModelT`**
  > Updates an instance with the attribute values from `data`.

- **`update_many(self, data: list[ModelT], ...) -> list[ModelT]`**
  > Updates multiple instances in a bulk operation.

- **`upsert(self, data: ModelT, ...) -> ModelT`**
  > Performs an "update or insert" operation.

- **`upsert_many(self, data: list[ModelT], ...) -> list[ModelT]`**
  > Performs a bulk "update or insert" operation.

### `SQLAlchemyAsyncSlugRepository`

Inherits from `SQLAlchemyAsyncRepository` and adds methods for slug-based operations.

- **`get_by_slug(self, slug: str, ...) -> ModelT | None`**
  > Retrieves a model instance by its `slug` attribute.

- **`get_available_slug(self, value_to_slugify: str, ...) -> str`**
  > Generates a unique, database-safe slug from a given string.

---

## Services

This section covers the service classes from `advanced_alchemy/service/_async.py`. The service layer acts as a wrapper around the repository, adding business logic and data transformation.

*Note: If a method's description does not include a **Wrapper Logic** section, it can be assumed to be a direct pass-through to the repository method of the same name.*

### `SQLAlchemyAsyncRepositoryReadService`

A read-only service object that operates on a repository.

#### Methods

- **`count(self, *filters, **kwargs) -> int`**
  > Count of records returned by a query.
  >
  > **Calls Repository Method:** `count()`

- **`exists(self, *filters, **kwargs) -> bool`**
  > Wraps the repository's `exists` operation.
  >
  > **Calls Repository Method:** `exists()`

- **`get(self, item_id: Any, ...) -> ModelT`**
  > Wraps the repository's `get` operation.
  >
  > **Calls Repository Method:** `get()`

- **`get_one(self, *filters, **kwargs) -> ModelT`**
  > Wraps the repository's `get_one` operation.
  >
  > **Calls Repository Method:** `get_one()`

- **`get_one_or_none(self, *filters, **kwargs) -> ModelT | None`**
  > Wraps the repository's `get_one_or_none` operation.
  >
  > **Calls Repository Method:** `get_one_or_none()`

- **`list(self, *filters, **kwargs) -> Sequence[ModelT]`**
  > Wraps the repository's `list` operation.
  >
  > **Calls Repository Method:** `list()`

- **`list_and_count(self, *filters, **kwargs) -> tuple[Sequence[ModelT], int]`**
  > Wraps the repository's `list_and_count` operation.
  >
  > **Calls Repository Method:** `list_and_count()`

### `SQLAlchemyAsyncRepositoryService`

Inherits from `SQLAlchemyAsyncRepositoryReadService` and adds write operations.

#### Methods

- **`create(self, data: ModelDictT[ModelT], ...) -> ModelT`**
  > Wraps the repository's instance creation.
  >
  > **Calls Repository Method:** `add()`
  > 
  > **Wrapper Logic:** Before calling the repository, this method converts the input `data` (which can be a dictionary, a Pydantic model, or another DTO) into a SQLAlchemy model instance using the `to_model()` method.

- **`create_many(self, data: BulkModelDictT[ModelT], ...) -> Sequence[ModelT]`**
  > Wraps the repository's bulk instance creation.
  >
  > **Calls Repository Method:** `add_many()`
  > 
  > **Wrapper Logic:** Converts each item in the input list `data` into a SQLAlchemy model instance before passing the list to the repository.

- **`update(self, data: ModelDictT[ModelT], ...) -> ModelT`**
  > Wraps the repository's update operation.
  >
  > **Calls Repository Methods:** `get()` and `update()`
  > 
  > **Wrapper Logic:** This method adds significant logic. It first converts the input `data` to a model. If an `item_id` is provided, it fetches the existing instance from the database using `get()`. It then carefully copies the attributes from the input data onto the existing instance. This ensures that database-managed fields and relationships are preserved, enabling partial updates. Finally, it calls the repository's `update()` method.

- **`update_many(self, data: BulkModelDictT[ModelT], ...) -> Sequence[ModelT]`**
  > Wraps the repository's bulk instance update.
  >
  > **Calls Repository Method:** `update_many()`
  > 
  > **Wrapper Logic:** Converts each item in the input list `data` into a SQLAlchemy model instance before passing the list to the repository for a bulk update.

- **`upsert(self, data: ModelDictT[ModelT], ...) -> ModelT`**
  > Wraps the repository's `upsert` operation.
  >
  > **Calls Repository Method:** `upsert()`
  > 
  > **Wrapper Logic:** Converts the input `data` to a model instance and identifies the item's ID before passing it to the repository.

- **`upsert_many(self, data: BulkModelDictT[ModelT], ...) -> Sequence[ModelT]`**
  > Wraps the repository's bulk `upsert` operation.
  >
  > **Calls Repository Method:** `upsert_many()`
  > 
  > **Wrapper Logic:** Converts each item in the input list `data` into a SQLAlchemy model instance before the bulk upsert operation.

- **`get_or_upsert(self, *filters, **kwargs) -> tuple[ModelT, bool]`**
  > Wraps the repository's `get_or_upsert` operation.
  >
  > **Calls Repository Method:** `get_or_upsert()`
  > 
  > **Wrapper Logic:** Converts the input keyword arguments into a validated model instance before calling the repository, ensuring the data is in the correct shape.

- **`get_and_update(self, *filters, **kwargs) -> tuple[ModelT, bool]`**
  > Wraps the repository's `get_and_update` operation.
  >
  > **Calls Repository Method:** `get_and_update()`
  > 
  > **Wrapper Logic:** Converts the input keyword arguments into a validated model instance before calling the repository.

- **`delete(self, item_id: Any, ...) -> ModelT`**
  > Wraps the repository's `delete` operation.
  >
  > **Calls Repository Method:** `delete()`

- **`delete_many(self, item_ids: list[Any], ...) -> Sequence[ModelT]`**
  > Wraps the repository's bulk `delete_many` operation.
  >
  > **Calls Repository Method:** `delete_many()`

- **`delete_where(self, *filters, **kwargs) -> Sequence[ModelT]`**
  > Wraps the repository's `delete_where` operation.
  >
  > **Calls Repository Method:** `delete_where()`
