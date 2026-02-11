"""Utilities for selecting and loading dataset files.

These helpers keep the dataset discovery and loading logic close to the
existing loader code so that user interfaces (such as CLI scripts) can remain
thin and focused on presentation concerns.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from collections.abc import Sequence
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ontologizer.relational.database import get_async_session_factory
from ontologizer.loader.loader import DatasetLoaderError, load_yaml_dataset

logger = logging.getLogger(__name__)

# Directory containing the default dataset fixtures.
DEFAULT_DATA_DIRECTORY = Path(__file__).resolve().parent / "data"


@dataclass(slots=True)
class DatasetLoadStatus:
    """Result of attempting to load a dataset file."""

    path: Path
    success: bool
    summary: dict[str, Any] | None = None
    error: str | None = None


def list_dataset_files(directory: str | Path | None = None) -> list[Path]:
    """Return all YAML dataset files in the given directory, sorted by name."""
    base_dir = Path(directory) if directory is not None else DEFAULT_DATA_DIRECTORY

    if not base_dir.exists():
        raise FileNotFoundError(f"Dataset directory does not exist: {base_dir}")

    if not base_dir.is_dir():
        raise NotADirectoryError(f"Expected a directory of datasets: {base_dir}")

    yaml_suffixes = {".yaml", ".yml"}
    files = sorted(
        p for p in base_dir.iterdir() if p.is_file() and p.suffix in yaml_suffixes
    )
    logger.debug("Discovered %d dataset files in %s", len(files), base_dir)
    return files


async def load_selected_datasets(
    paths: Sequence[str | Path],
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> list[DatasetLoadStatus]:
    """Load the selected dataset files and return per-file results."""
    if not paths:
        return []

    # Ensure database tables exist before loading any datasets
    from sqlalchemy import create_engine
    from ontologizer.settings import get_settings
    from ontologizer.relational.database import Base

    settings = get_settings()
    sync_url = settings.database.connection_string.replace("sqlite+aiosqlite", "sqlite")
    sync_engine = create_engine(sync_url)
    logger.info("Creating database tables if they don't exist...")
    Base.metadata.create_all(sync_engine)
    sync_engine.dispose()
    logger.info("Database tables ready")

    normalized_paths = [_resolve_dataset_path(path) for path in paths]
    results: list[DatasetLoadStatus] = []

    factory = session_factory or get_async_session_factory()

    for dataset_path in normalized_paths:
        async with factory() as session:
            try:
                logger.info("Loading dataset %s", dataset_path)
                summary = await load_yaml_dataset(dataset_path, session)
            except FileNotFoundError as exc:
                logger.error("Dataset file missing: %s", dataset_path)
                results.append(
                    DatasetLoadStatus(
                        path=dataset_path,
                        success=False,
                        summary=None,
                        error=str(exc),
                    )
                )
            except DatasetLoaderError as exc:
                await _safe_rollback(session)
                logger.exception("Dataset loader failure for %s", dataset_path)
                results.append(
                    DatasetLoadStatus(
                        path=dataset_path,
                        success=False,
                        summary=None,
                        error=str(exc),
                    )
                )
            except Exception as exc:  # pragma: no cover - defensive fallback
                await _safe_rollback(session)
                logger.exception("Unexpected error while loading %s", dataset_path)
                results.append(
                    DatasetLoadStatus(
                        path=dataset_path,
                        success=False,
                        summary=None,
                        error=str(exc),
                    )
                )
            else:
                results.append(
                    DatasetLoadStatus(
                        path=dataset_path,
                        success=True,
                        summary=summary,
                        error=None,
                    )
                )
                await _safe_commit(session)

    return results


async def _safe_commit(session: AsyncSession) -> None:
    """Commit the session while ignoring deliberate transaction absence."""
    try:
        await session.commit()
    except Exception:  # pragma: no cover - defensive, mirrors loader semantics
        logger.debug("Commit failed; attempting rollback")
        await session.rollback()
        raise


async def _safe_rollback(session: AsyncSession) -> None:
    """Rollback the session if possible."""
    try:
        await session.rollback()
    except Exception:  # pragma: no cover - defensive
        logger.warning("Rollback failed for session", exc_info=True)


def _resolve_dataset_path(path: str | Path) -> Path:
    """Resolve dataset path strings relative to the default directory."""
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    return (DEFAULT_DATA_DIRECTORY / candidate).resolve()


__all__ = [
    "DEFAULT_DATA_DIRECTORY",
    "DatasetLoadStatus",
    "DatasetLoaderError",
    "list_dataset_files",
    "load_selected_datasets",
]
