# Advanced Alchemy Typing: `ModelT` vs `model_type`

This note explains how typing works in `advanced_alchemy/repository/_sync.py`.

## Core idea

`ModelT` is a generic type variable used by static type checkers.
`model_type` is the concrete model class used at runtime.

You need both:

- `ModelT` gives editor and type-checker guarantees across repository APIs.
- `model_type` is what SQLAlchemy queries and runtime checks actually use.

## Where `ModelT` comes from

`ModelT` is defined in `advanced_alchemy/repository/typing.py` as:

- `TypeVar("ModelT", bound="base.ModelProtocol")`

That means `ModelT` must satisfy the model protocol expected by Advanced Alchemy.

## How `_sync.py` uses it

The sync repository classes are generic in `ModelT`:

- `SQLAlchemySyncRepositoryProtocol[ModelT]`
- `SQLAlchemySyncRepository[ModelT]`

Method signatures then stay consistent, for example:

- `add(data: ModelT) -> ModelT`
- `get(...) -> ModelT`
- `statement: Select[tuple[ModelT]]`

## Runtime behavior comes from `model_type`

At runtime, the repository uses `self.model_type` (a real class object), for example:

- `select(self.model_type)`
- `isinstance(value, self.model_type)`
- `get_instrumented_attr(self.model_type, field_name)`

So the generic parameter itself is not used for runtime dispatch.

## Practical usage pattern

```python
class AuthorSyncRepository(SQLAlchemySyncRepository[UUIDAuthor]):
    model_type = UUIDAuthor
```

- `SQLAlchemySyncRepository[UUIDAuthor]` informs static typing.
- `model_type = UUIDAuthor` provides the runtime model class.

## Mental model

Treat this as a two-layer contract:

1. Compile-time: `ModelT` keeps all repository method types aligned.
2. Runtime: `model_type` drives SQLAlchemy operations and object checks.
