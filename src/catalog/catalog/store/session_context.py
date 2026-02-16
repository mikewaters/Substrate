"""catalog.store.session_context - Ambient session registry via ContextVars.

Provides a thread-safe, async-compatible ambient session for SQLAlchemy.
Components can access the current session without explicit plumbing.

Example usage:
    from catalog.store.session_context import current_session, use_session
    from catalog.store.database import get_session

    # Set ambient session at entry point
    with get_session() as session:
        with use_session(session):
            # Repositories/managers find session automatically
            repo = DocumentRepository()  # Uses ambient session
            doc = repo.get_by_id(1)

    # Or get the session directly
    with get_session() as session:
        with use_session(session):
            sess = current_session()
            sess.execute(...)

    # In workers (threads or processes) where no session is set:
    with session_or_new() as session:
        # session is either the ambient one or a new one for this block
        repo = DocumentRepository()
        ...
"""

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

__all__ = [
    "current_session",
    "use_session",
    "session_or_new",
    "clear_session",
    "SessionNotSetError",
]

# The ambient session ContextVar
_current_session: ContextVar["Session | None"] = ContextVar(
    "idx_current_session", default=None
)


class SessionNotSetError(RuntimeError):
    """Raised when accessing ambient session before it's set."""

    def __init__(self, *args: object) -> None:
        if not args:
            args = (
                "No ambient session set. Use 'with use_session(session):' or "
                "pass session explicitly to the constructor.",
            )
        super().__init__(*args)


def current_session() -> "Session":
    """Get the current ambient session.

    Returns:
        The SQLAlchemy Session for the current context.

    Raises:
        SessionNotSetError: If no ambient session is set.

    Example:
        with get_session() as session:
            with use_session(session):
                sess = current_session()
                sess.add(some_model)
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

    Example:
        with get_session() as session:
            with use_session(session):
                # session is now ambient
                repo = DocumentRepository()
                doc = repo.get_by_id(1)
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

    Example:
        with session_or_new() as session:
            repo = DocumentRepository()
            repo.add(...)
    """
    session = _current_session.get()
    if session is not None:
        yield session
        return
    from catalog.store.database import get_session

    with get_session() as session:
        with use_session(session):
            yield session


def clear_session() -> None:
    """Clear the ambient session.

    This is primarily useful in tests to ensure a clean state.
    In production code, prefer using `use_session()` as a context
    manager which automatically clears on exit.

    Example:
        clear_session()  # Ensure no ambient session
        with pytest.raises(SessionNotSetError):
            current_session()
    """
    _current_session.set(None)
