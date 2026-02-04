"""Local directory source reader.

Enumerates files from a directory, filtering by glob patterns,
and produces LlamaIndex Documents for the ingestion pipeline.
"""

from __future__ import annotations

from functools import cached_property
from pathlib import Path

from agentlayer.logging import get_logger
from llama_index.core import Document, SimpleDirectoryReader

from typing import TYPE_CHECKING

from catalog.ingest.sources import (
    BaseSource,
    create_reader,
    create_source,
    register_ingest_config_factory,
)
from catalog.ingest.schemas import IngestDirectoryConfig

if TYPE_CHECKING:
    from catalog.ingest.job import SourceConfig

logger = get_logger(__name__)


@register_ingest_config_factory("directory")
def create_directory_ingest_config(source_config: "SourceConfig") -> IngestDirectoryConfig:
    """Create IngestDirectoryConfig from generic SourceConfig.

    Interprets directory-specific options:
        - patterns: List of glob patterns (default: ["**/*.md"]).
        - encoding: File encoding (default: "utf-8").

    Args:
        source_config: Generic source configuration from YAML job file.

    Returns:
        IngestDirectoryConfig instance ready for create_source().
    """
    return IngestDirectoryConfig(
        source_path=source_config.source_path,
        dataset_name=source_config.dataset_name or source_config.source_path.name,
        force=source_config.force,
        patterns=source_config.options.get("patterns", ["**/*.md"]),
        encoding=source_config.options.get("encoding", "utf-8"),
    )


@create_source.register
def _(config: IngestDirectoryConfig):
    return DirectorySource(
        config.source_path,
        patterns=config.patterns,
        encoding=config.encoding,
    )


@create_reader.register
def _(config: IngestDirectoryConfig):
    return SimpleDirectoryReader(
        config.source_path,
        patterns=config.patterns,
        encoding=config.encoding,
    )
class DirectorySource(BaseSource):
    """Source that reads files from a local directory via SimpleDirectoryReader.

    Wraps LlamaIndex's SimpleDirectoryReader, adding glob-pattern
    filtering and relative_path metadata for PersistenceTransform.

    Example:
        source = DirectorySource(
            Path("/path/to/docs"),
            patterns=["**/*.md", "**/*.txt"],
        )
        for doc in source.documents:
            print(doc.metadata["relative_path"])
    """

    type_name = "directory"

    def __init__(
        self,
        path: Path,
        patterns: list[str] | None = None,
        *,
        encoding: str = "utf-8",
    ) -> None:
        """Initialize directory source.

        Args:
            path: Root directory to scan for documents.
            patterns: Glob patterns for matching files.
                Use ``!`` prefix for exclusion patterns.
                Defaults to ``["**/*.md"]``.
            encoding: File encoding to use.  Defaults to utf-8.
        """
        self.path = path.resolve()
        self._encoding = encoding
        self._raw_patterns = patterns or ["**/*.md"]

        # Separate include and exclude patterns
        self._includes = [p for p in self._raw_patterns if not p.startswith("!")]
        self._excludes = [p[1:] for p in self._raw_patterns if p.startswith("!")]

    # ------------------------------------------------------------------
    # Interface expected by DatasetIngestPipeline
    # ------------------------------------------------------------------

    @cached_property
    def documents(self) -> list[Document]:
        """Load all matching files as LlamaIndex Documents."""
        all_docs: list[Document] = []
        seen_paths: set[Path] = set()

        for pattern in self._includes:
            for file_path in sorted(self.path.glob(pattern)):
                if not file_path.is_file():
                    continue
                if file_path in seen_paths:
                    continue
                rel = file_path.relative_to(self.path)
                if self._is_excluded(str(rel)):
                    continue
                seen_paths.add(file_path)

                try:
                    text = file_path.read_text(encoding=self._encoding)
                except (UnicodeDecodeError, PermissionError, OSError) as exc:
                    logger.warning(f"Skipping unreadable file {file_path}: {exc}")
                    continue

                doc = Document(
                    text=text,
                    metadata={
                        "relative_path": str(rel),
                        "file_path": str(file_path),
                        "file_name": file_path.name,
                    },
                )
                doc.id_ = str(rel)
                all_docs.append(doc)

        logger.info(f"DirectorySource loaded {len(all_docs)} documents from {self.path}")
        return all_docs

    def get_transforms(self, dataset_id: int):
        """Return (pre_persist, post_persist) transform lists.

        Directory sources have no source-specific transforms.
        """
        return ([], [])

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def validate(path: Path) -> None:
        """Validate that the given path is a valid directory."""
        if not path.exists():
            raise ValueError(f"Directory path does not exist: {path}")
        if not path.is_dir():
            raise ValueError(f"Path is not a directory: {path}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_excluded(self, rel_path: str) -> bool:
        """Check if a relative path matches any exclusion pattern."""
        if not self._excludes:
            return False
        p = Path(rel_path)
        return any(p.match(pat) for pat in self._excludes)


__all__ = ["DirectorySource"]
