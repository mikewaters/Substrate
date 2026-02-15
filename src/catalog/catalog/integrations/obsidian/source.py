from __future__ import annotations

from datetime import datetime
from functools import cached_property
from pathlib import Path
from typing import Dict, Any

from llama_index.core import Document
from llama_index.core.node_parser import MarkdownNodeParser
from pydantic import model_validator

from catalog.ingest.sources import BaseSource, DatasetSourceConfig
from catalog.ontology import OntologyMappingSpec
from catalog.integrations.obsidian.reader import ObsidianVaultReader, logger, ObsidianMarkdownNormalize
from catalog.integrations.obsidian.transforms import LinkResolutionTransform


class ObsidianVaultSource(BaseSource):
    """Populates a Dataset from an Obsidian vault."""
    type_name = "obsidian"

    def __init__(
            self, path: str | Path,
            ontology_spec: type[OntologyMappingSpec] | None = None,
            if_modified_since: datetime | None = None,
        ) -> None:
        """Initialize Obsidian vault source.

        Args:
            path: Path to the Obsidian vault root directory.
                Must contain a .obsidian subdirectory.
            ontology_spec: Optional OntologyMappingSpec subclass for frontmatter mapping.
            if_modified_since: If set, only ingest files modified at or after
                this timestamp.

        Raises:
            ValueError: If the path is not a valid Obsidian vault.
        """
        self.path = Path(path).resolve()
        self.ontology_spec = ontology_spec
        self.reader = ObsidianVaultReader(input_dir=self.path)

        if if_modified_since is not None:
            ts = if_modified_since.timestamp()
            self.reader.input_files = sorted(
                (
                    p
                    for p in self.path.rglob("*.md")
                    if p.stat().st_mtime >= ts
                ),
                key=lambda p: str(p),
            )
            logger.info(
                f"Filtered to {len(self.reader.input_files)} files "
                f"modified since {if_modified_since}"
            )

        logger.debug(f"Initialized ObsidianVaultSource for vault: {self.path}")

    def transforms(self, dataset_id: int) -> list[type]:
        """Get the list of transforms to apply for this source.

        Returns:
            Tuple of List of TransformComponent subclasses.
            [0] is pre-persist, [1] is post-persist
        """
        parser = MarkdownNodeParser(
            include_metadata=True,
            include_prev_next_rel=True,
            header_path_separator=" / ",
        )
        transforms = [
                LinkResolutionTransform(dataset_id=dataset_id),
                ObsidianMarkdownNormalize(),
                parser,

            ]


        return transforms

    @cached_property
    def documents(self) -> list[Document]:
        """Load and return all documents from the Obsidian vault."""
        logger.info(f"Loading documents from Obsidian vault at: {self.path}")
        docs = self.reader.load_data()
        return docs


class SourceObsidianConfig(DatasetSourceConfig):
    """Configuration for Obsidian vault ingestion.

    Attributes:
        source_path: Path to the Obsidian vault.
        dataset_name: Name for the dataset (will be normalized).
        force: If True, reprocess all documents even if unchanged.
        ontology_spec: Optional VaultSpec subclass for typed frontmatter mapping.
    """
    type_name: str = "obsidian"
    ontology_spec: type[OntologyMappingSpec] | None = None
    @model_validator(mode="after")
    def validate_source_path(self) -> "SourceObsidianConfig":
        """Validate that the given path is a valid Obsidian vault."""
        if not self.source_path.exists():
            raise ValueError(f"Vault path does not exist: {self.source_path}")

        if not self.source_path.is_dir():
            raise ValueError(f"Vault path is not a directory: {self.source_path}")

        obsidian_dir = self.source_path / ".obsidian"
        if not obsidian_dir.is_dir():
            raise ValueError(
                f"Not a valid Obsidian vault (missing .obsidian directory): {self.source_path}"
            )
        return self

    @model_validator(mode='before')
    def post_update(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Auto-set dataset_name from source_path if not provided."""
        if values.get('source_path', False):
            if not values.get('dataset_name', False):
                values['dataset_name'] = values['source_path'].name

        return values
