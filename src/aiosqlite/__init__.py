"""Minimal aiosqlite-compatible shim used for offline testing.

This implementation wraps the standard library ``sqlite3`` module and executes
blocking operations in a background thread using ``asyncio.to_thread`` so that
SQLAlchemy's async drivers can interoperate without the third-party
``aiosqlite`` dependency.
"""

from __future__ import annotations

import asyncio
import sqlite3
from asyncio import Future, Queue
from typing import Any, Callable, Optional, Sequence

# Re-export sqlite exceptions and helpers expected by SQLAlchemy's adapter.
DatabaseError = sqlite3.DatabaseError
Error = sqlite3.Error
IntegrityError = sqlite3.IntegrityError
NotSupportedError = sqlite3.NotSupportedError
OperationalError = sqlite3.OperationalError
ProgrammingError = sqlite3.ProgrammingError

sqlite_version = sqlite3.sqlite_version
sqlite_version_info = sqlite3.sqlite_version_info

PARSE_COLNAMES = sqlite3.PARSE_COLNAMES
PARSE_DECLTYPES = sqlite3.PARSE_DECLTYPES
Binary = sqlite3.Binary


async def _to_thread(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Execute ``func`` in the default thread pool."""
    return await asyncio.to_thread(func, *args, **kwargs)


class Cursor:
    """Async cursor shim."""

    def __init__(self, cursor: sqlite3.Cursor) -> None:
        self._cursor = cursor

    @property
    def description(self) -> Optional[Sequence[Any]]:
        return self._cursor.description

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    @property
    def lastrowid(self) -> int:
        return self._cursor.lastrowid

    async def execute(self, sql: str, parameters: Any | None = None) -> "Cursor":
        if parameters is None:
            await _to_thread(self._cursor.execute, sql)
        else:
            await _to_thread(self._cursor.execute, sql, parameters)
        return self

    async def executemany(self, sql: str, seq_of_parameters: Sequence[Any]) -> "Cursor":
        await _to_thread(self._cursor.executemany, sql, seq_of_parameters)
        return self

    async def fetchone(self) -> Any:
        return await _to_thread(self._cursor.fetchone)

    async def fetchmany(self, size: int | None = None) -> Sequence[Any]:
        if size is None:
            return await _to_thread(self._cursor.fetchmany)
        return await _to_thread(self._cursor.fetchmany, size)

    async def fetchall(self) -> Sequence[Any]:
        return await _to_thread(self._cursor.fetchall)

    async def close(self) -> None:
        await _to_thread(self._cursor.close)


class Connection:
    """Async connection shim compatible with aiosqlite's public API."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._tx: Queue[tuple[Future[Any], Callable[[], Any]]] = Queue()
        self._tx_worker = asyncio.create_task(self._tx_loop())
        self._closed = False
        self.daemon = True  # SQLAlchemy expects this attribute to exist.

    async def _tx_loop(self) -> None:
        while True:
            future, func = await self._tx.get()
            if future.done():
                continue
            try:
                result = await _to_thread(func)
            except Exception as exc:  # pragma: no cover - pass through
                future.set_exception(exc)
            else:
                future.set_result(result)

    async def cursor(self) -> Cursor:
        raw = await _to_thread(self._conn.cursor)
        return Cursor(raw)

    async def execute(self, sql: str, parameters: Any | None = None) -> Cursor:
        cursor = await self.cursor()
        await cursor.execute(sql, parameters)
        return cursor

    async def executemany(self, sql: str, seq_of_parameters: Sequence[Any]) -> Cursor:
        cursor = await self.cursor()
        await cursor.executemany(sql, seq_of_parameters)
        return cursor

    async def commit(self) -> None:
        await _to_thread(self._conn.commit)

    async def rollback(self) -> None:
        await _to_thread(self._conn.rollback)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await _to_thread(self._conn.close)
        self._tx_worker.cancel()
        with contextlib.suppress(Exception):
            await self._tx_worker

    async def create_function(self, *args: Any, **kwargs: Any) -> None:
        await _to_thread(self._conn.create_function, *args, **kwargs)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._conn, item)

    async def __aenter__(self) -> "Connection":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if exc_type:
            await self.rollback()
        else:
            await self.commit()
        await self.close()


async def connect(*args: Any, **kwargs: Any) -> Connection:
    """Create an async connection to SQLite."""
    conn = await _to_thread(sqlite3.connect, *args, **kwargs)
    conn.row_factory = kwargs.get("row_factory", conn.row_factory)
    connection = Connection(conn)
    return connection


__all__ = [
    "connect",
    "Connection",
    "Cursor",
    "DatabaseError",
    "Error",
    "IntegrityError",
    "NotSupportedError",
    "OperationalError",
    "ProgrammingError",
    "sqlite_version",
    "sqlite_version_info",
    "PARSE_COLNAMES",
    "PARSE_DECLTYPES",
    "Binary",
]
