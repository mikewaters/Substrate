"""agentlayer.session - Ambient session registry via ContextVars.

Provides a thread-safe, async-compatible ambient session for SQLAlchemy.
Components can access the current session without explicit plumbing.

Domain-specific packages must call ``register_session_factory()`` to provide
a session factory before ``session_or_new()`` can create sessions automatically.

Example usage:
    from agentlayer.session import current_session, use_session, register_session_factory

    # Register a factory at app startup
    register_session_factory(my_get_session)

    # Set ambient session at entry point
    with my_get_session() as session:
        with use_session(session):
            sess = current_session()
            sess.execute(...)

    # In workers where no session is set:
    with session_or_new() as session:
        # session is either the ambient one or a new one for this block
        ...
"""

from collections.abc import Callable, Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

__all__ = [
    "SessionNotSetError",
    "clear_session",
    "current_session",
    "register_session_factory",
    "session_or_new",
    "use_session",
]

# The ambient session ContextVar
_current_session: ContextVar["Session | None"] = ContextVar(
    "substrate_current_session", default=None
)

# Registerable session factory for session_or_new()
_session_factory: ContextVar[Callable | None] = ContextVar("_session_factory", default=None)


class SessionNotSetError(RuntimeError):
    """Raised when accessing ambient session before it's set."""

    def __init__(self, *args: object) -> None:
        if not args:
            args = (
                "No ambient session set. Use 'with use_session(session):' or "
                "pass session explicitly to the constructor.",
            )
        super().__init__(*args)


def register_session_factory(factory: Callable) -> None:
    """Register a session factory for use by ``session_or_new()``.

    The factory should be a context manager that yields a SQLAlchemy Session.

    Args:
        factory: A callable context manager yielding a Session.
    """
    _session_factory.set(factory)


def current_session() -> "Session":
    """Get the current ambient session.

    Returns:
        The SQLAlchemy Session for the current context.

    Raises:
        SessionNotSetError: If no ambient session is set.
    """
    session = _current_session.get()
    if session is None:
        raise SessionNotSetError()
    return session


@contextmanager
def use_session(session: "Session") -> Generator[None, None, None]:
    """Set the ambient session for the current context.

    This is a context manager that sets the ambient session for the
    duration of the block. Nested calls are supported - the inner
    session takes precedence and the outer is restored on exit.

    Args:
        session: The SQLAlchemy session to make ambient.

    Yields:
        None
    """
    token = _current_session.set(session)
    try:
        yield
    finally:
        _current_session.reset(token)


@contextmanager
def session_or_new() -> Generator["Session", None, None]:
    """Use the ambient session if set; otherwise create one for this block.

    Call this at the start of code that may run in a worker (thread or
    process) where the ambient session might not be set. In the main
    thread with use_session() already active, the existing session is
    yielded and not closed. In workers, a new session is created and
    set as ambient for the block, then closed on exit.

    Yields:
        The ambient session if set, otherwise a new session (owned by
        this context manager; do not close it yourself).

    Raises:
        RuntimeError: If no session factory is registered and no ambient session exists.
    """
    session = _current_session.get()
    if session is not None:
        yield session
        return
    factory = _session_factory.get()
    if factory is None:
        raise RuntimeError(
            "No session factory registered. Call register_session_factory() first."
        )
    with factory() as session:
        with use_session(session):
            yield session


def clear_session() -> None:
    """Clear the ambient session.

    Primarily useful in tests to ensure a clean state.
    In production code, prefer using ``use_session()`` as a context
    manager which automatically clears on exit.
    """
    _current_session.set(None)
