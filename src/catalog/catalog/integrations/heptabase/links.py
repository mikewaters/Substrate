"""catalog.integrations.heptabase.links - Heptabase link extraction utilities.

Pure functions for extracting internal links from Heptabase markdown format.
No integration-level dependencies.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List
from urllib.parse import unquote

__all__ = [
    "extract_heptabase_links",
]

# Matches [display text](./relative-path) where the target starts with ./
_HEPTABASE_LINK_RE = re.compile(r"\[([^\]]*)\]\(\./([^)]+)\)")


def extract_heptabase_links(text: str) -> List[str]:
    """Extract Heptabase internal links from text.

    Matches patterns like:
        - [Note name.md](./Note name.md)
        - [Display text](./some/path.md)

    The ``./`` prefix distinguishes internal vault links from external URLs.
    The note name is derived by stripping the ``.md`` extension from the
    target path's filename component.

    Args:
        text: Document text to extract links from.

    Returns:
        List of unique link target names (note stems, without .md extension).
    """
    matches = _HEPTABASE_LINK_RE.findall(text)
    links = []
    for _display, target in matches:
        # URL-decode (e.g., LifeOS%20Utilities.md -> LifeOS Utilities.md)
        target = unquote(target)
        # Strip fragment identifiers (e.g., Note.md#section -> Note.md)
        target = target.split("#", 1)[0]
        # Get the filename stem (strip .md and any directory components)
        stem = Path(target).stem
        links.append(stem)
    return list(set(links))
