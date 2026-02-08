"""Behave environment hooks for catalog BDD scenarios."""

from __future__ import annotations

import os
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from sqlalchemy.orm import sessionmaker

from catalog.store.database import Base, create_engine_for_path
from catalog.store.fts import create_fts_table


def before_all(context: Any) -> None:
    """Create a shared temporary directory for BDD scenario assets."""
    context._tmpdir = TemporaryDirectory()
    context.tmpdir = context._tmpdir.name


def after_all(context: Any) -> None:
    """Clean up the shared temporary directory."""
    tmpdir = getattr(context, "_tmpdir", None)
    if tmpdir is not None:
        tmpdir.cleanup()


def scenario_db_path(tmpdir: str, scenario_name: str) -> Path:
    """Build a deterministic database path for the scenario."""
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "-", scenario_name).strip("-").lower()
    if not safe_name:
        safe_name = "scenario"
    return Path(tmpdir) / f"{safe_name}.db"


def prepare_scenario_database(context: Any, scenario: Any) -> None:
    """Create a fresh SQLite database with FTS tables for the scenario."""
    db_path = scenario_db_path(context.tmpdir, scenario.name)
    if db_path.exists():
        db_path.unlink()
    engine = create_engine_for_path(db_path)
    Base.metadata.create_all(engine)
    create_fts_table(engine)
    context.session_factory = sessionmaker(bind=engine, expire_on_commit=False)


def before_scenario(context: Any, scenario: Any) -> None:
    """Skip scenarios unless explicitly enabled via an environment flag."""
    if "skip" in getattr(scenario, "tags", []):
        scenario.skip("Scenario is tagged as skip.")
        return
    if os.environ.get("CATALOG_BDD_ENABLE") != "1":
        scenario.skip(
            "BDD scenarios are disabled by default. "
            "Set CATALOG_BDD_ENABLE=1 to run them."
        )
        return
    prepare_scenario_database(context, scenario)
