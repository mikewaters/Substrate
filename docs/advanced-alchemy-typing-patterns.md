# Advanced Alchemy: Notable Typing Patterns

This note catalogs less-common typing approaches used across the codebase, beyond the basic `ModelT` repository generic.

## 1) Compatibility typing via `@dataclass_transform`

Used to keep static typing useful even when optional libraries are not installed.

Where:

- `advanced_alchemy/service/_typing.py`
  - `StructLike` with `@dataclass_transform()`
  - `AttrsLike` with `@dataclass_transform()`
  - runtime import shims for pydantic, msgspec, attrs, cattrs, Litestar DTO

Why it is notable:

- It allows a consistent typed API over optional dependencies.
- Editors and type checkers can still reason about model-like objects, even with fallback stubs.

Tradeoff:

- More internal complexity and some necessary casts/ignores around dynamic imports.

## 2) Broad `TypeGuard` narrowing for polymorphic service inputs

Used to safely process many schema/input shapes at runtime while preserving static narrowing.

Where:

- `advanced_alchemy/service/typing.py`
  - `is_dto_data`, `is_pydantic_model`, `is_msgspec_struct`, `is_attrs_instance`, `is_schema_or_dict`, etc.

Why it is notable:

- The service layer can accept dicts, ORM models, DTO wrappers, Pydantic models, msgspec structs, and attrs instances.
- `TypeGuard` functions let the code narrow those unions explicitly before serialization/conversion.

Tradeoff:

- Requires maintaining many small predicate functions.

## 3) Input-shape-dependent overload APIs

Used where return type should vary based on the input type.

Where:

- `advanced_alchemy/service/typing.py`
  - multiple `@overload` signatures for `schema_dump(...)`
- `advanced_alchemy/repository/_util.py`
  - multiple `@overload` signatures for `_apply_filters(...)` by statement type

Why it is notable:

- Produces better call-site type inference than a single coarse union signature.

Tradeoff:

- Overloads can be verbose and may need pyright/mypy accommodations for edge cases.

## 4) `ParamSpec`-preserving async/sync adapters

Used to keep wrapped function signatures and return typing intact for adapters.

Where:

- `advanced_alchemy/utils/sync_tools.py`
  - `run_`, `await_`, `async_`, `ensure_async_`

Why it is notable:

- Wrappers preserve argument types (`*args`, `**kwargs`) and concrete return types rather than degrading to `Callable[..., Any]`.

Tradeoff:

- Complex control flow around event loop handling still needs runtime safeguards.

## 5) `TypeIs` for sync/async branch refinement

Used for precise branch narrowing when behavior diverges between sync and async resources.

Where:

- `advanced_alchemy/alembic/utils.py`
  - `_is_sync(engine) -> TypeIs[Engine]`
  - `_is_sync(session) -> TypeIs[AbstractContextManager[Session]]`

Why it is notable:

- Branches become type-safe without repetitive casts.

Tradeoff:

- Requires newer typing constructs and careful predicate correctness.

## 6) Repository type variables with defaults

Used for service/repository generic ergonomics.

Where:

- `advanced_alchemy/repository/typing.py`
  - `SQLAlchemySyncRepositoryT = TypeVar(..., default="Any")`
  - `SQLAlchemyAsyncRepositoryT = TypeVar(..., default="Any")`

Why it is notable:

- Supports better generic specialization while keeping convenient defaults.

Tradeoff:

- Some type checkers historically had uneven support for defaulted type variables.

## 7) `Self` for subclass-accurate APIs and registries

Used where class-returning methods should preserve concrete subclass type.

Where:

- `advanced_alchemy/mixins/unique.py`
  - methods returning `Self`
- `advanced_alchemy/repository/memory/_sync.py`
  - `__database_registry__: dict[type[Self], ...]`

Why it is notable:

- Subclasses keep precise return types and class-keyed registries stay typed.

Tradeoff:

- Depends on `typing_extensions` in older Python/tooling environments.

## 8) Runtime-checkable protocols as architectural contracts

Used to define structural interfaces for models and data containers.

Where:

- `advanced_alchemy/base.py`
  - `ModelProtocol`
- `advanced_alchemy/utils/dataclass.py`
  - `DataclassProtocol`

Why it is notable:

- Encourages duck typing with explicit contracts, not rigid inheritance.

Tradeoff:

- Protocol compliance may still need runtime discipline for dynamic objects.

## Suggested mental model

Advanced Alchemy uses a layered typing strategy:

1. Structural contracts (`Protocol`, `TypeGuard`) for flexible inputs.
2. Generic propagation (`TypeVar`, `Self`, overloads) for strong API inference.
3. Compatibility shims (`dataclass_transform` stubs) to keep types stable across optional dependencies.

This is why the codebase supports highly dynamic runtime behavior while retaining useful static guarantees.
