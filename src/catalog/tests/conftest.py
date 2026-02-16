"""Suite-wide test isolation for catalog paths.

Prevents accidental reads/writes to the real ``~/.idx`` tree during tests.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


_REAL_HOME = Path(os.path.expanduser("~")).resolve()
_REAL_IDX_ROOT = (_REAL_HOME / ".idx").resolve()

_TEST_HOME = Path(tempfile.mkdtemp(prefix="catalog-tests-home-")).resolve()
_TEST_IDX_ROOT = (_TEST_HOME / ".idx").resolve()
_TEST_IDX_ROOT.mkdir(parents=True, exist_ok=True)

# Apply environment isolation as soon as this conftest is imported so any module
# import-time settings resolution still targets test-only paths. All paths derive
# from config_root; setting SUBSTRATE_CONFIG_ROOT and SUBSTRATE_ENVIRONMENT=test ensures
# catalog uses the test tree.
os.environ["HOME"] = str(_TEST_HOME)
os.environ["SUBSTRATE_ENVIRONMENT"] = "test"
os.environ["SUBSTRATE_CONFIG_ROOT"] = str(_TEST_IDX_ROOT)


def _is_within(candidate: Path, parent: Path) -> bool:
    """Return True when candidate is inside parent."""
    try:
        candidate.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


@pytest.fixture(scope="session", autouse=True)
def _guard_against_real_idx_paths() -> None:
    """Fail fast if resolved catalog paths target real ~/.idx."""
    from catalog.core.settings import get_settings

    get_settings.cache_clear()
    settings = get_settings()

    paths = [
        settings.databases.catalog_path.expanduser(),
        settings.databases.content_path.expanduser(),
        settings.vector_store_path.expanduser(),
        settings.cache_path.expanduser(),
        settings.job_config_path.expanduser(),
        settings.zvec.index_path.expanduser(),
    ]
    for path in paths:
        if _is_within(path, _REAL_IDX_ROOT):
            raise RuntimeError(
                "Catalog tests resolved a path under real ~/.idx, which is forbidden: "
                f"{path}"
            )

    yield

    get_settings.cache_clear()
