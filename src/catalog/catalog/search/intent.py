"""catalog.search.intent - Deterministic query intent classifier.

Classifies search queries as informational or navigational using rule-based
heuristics. Used to route BM25 heading weights and RRF fusion weights
for heading-bias mitigation.

Navigational queries target specific documents by name/title.
Informational queries seek topical content matches.

Example usage:
    from catalog.search.intent import classify_intent

    intent = classify_intent("how does async work in python")
    # -> "informational"

    intent = classify_intent('"Project Plan Q4"')
    # -> "navigational"

    intent = classify_intent("PROJ-1234")
    # -> "navigational"
"""

import re
from typing import Literal

from agentlayer.logging import get_logger

__all__ = ["QueryIntent", "classify_intent"]

logger = get_logger(__name__)

QueryIntent = Literal["informational", "navigational"]

# Patterns indicating navigational intent
_QUOTED_RE = re.compile(r'^".*"$|^\'.*\'$')
_JIRA_STYLE_RE = re.compile(r"^[A-Z]+-\d+$")
_CAMEL_CASE_RE = re.compile(r"[a-z][A-Z]")
_PATH_LIKE_RE = re.compile(r"[/\\]|\.md$|\.py$|\.txt$|\.json$|\.yaml$|\.yml$|\.toml$")


def classify_intent(query: str) -> QueryIntent:
    """Classify a search query as informational or navigational.

    Uses rule-based heuristics to determine whether the user is looking
    for a specific document (navigational) or topical information
    (informational).

    Navigational signals:
    - Quoted strings (exact title lookup)
    - Short queries with CamelCase or ALL_CAPS tokens
    - JIRA-style identifiers (PROJ-1234)
    - Path-like patterns (slashes, file extensions)

    Args:
        query: The raw search query string.

    Returns:
        "navigational" or "informational".
    """
    stripped = query.strip()

    # Quoted string = navigational (exact title lookup)
    if _QUOTED_RE.match(stripped):
        logger.debug(f"Intent: navigational (quoted) for '{stripped[:40]}'")
        return "navigational"

    tokens = stripped.split()

    # Path-like patterns
    if _PATH_LIKE_RE.search(stripped):
        logger.debug(f"Intent: navigational (path-like) for '{stripped[:40]}'")
        return "navigational"

    # Short query heuristics (1-3 tokens)
    if len(tokens) <= 3:
        for token in tokens:
            # JIRA-style: PROJ-1234
            if _JIRA_STYLE_RE.match(token):
                logger.debug(f"Intent: navigational (JIRA-style) for '{stripped[:40]}'")
                return "navigational"
            # CamelCase
            if _CAMEL_CASE_RE.search(token) and not token.islower():
                logger.debug(f"Intent: navigational (CamelCase) for '{stripped[:40]}'")
                return "navigational"
            # ALL_CAPS token (likely an acronym or identifier)
            if token.isupper() and len(token) >= 2:
                logger.debug(f"Intent: navigational (ALL_CAPS) for '{stripped[:40]}'")
                return "navigational"

    logger.debug(f"Intent: informational for '{stripped[:40]}'")
    return "informational"
