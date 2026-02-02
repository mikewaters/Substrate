"""catalog.source - Source management.

Abstractions for reading, parsing, and extracting from dataset sources.
"""

from catalog.ingest.directory import DirectorySource

__all__ = [
    "DirectorySource",
]
