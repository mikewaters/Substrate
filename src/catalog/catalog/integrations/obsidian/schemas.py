"""Pydantic schemas for Obsidian vault ingestion configuration."""

from pathlib import Path
from typing import Any, Dict

from pydantic import BaseModel, model_validator

from catalog.ingest.schemas import DatasetIngestConfig


class IngestObsidianConfig(DatasetIngestConfig):
    """Configuration for Obsidian vault ingestion.

    Attributes:
        source_path: Path to the Obsidian vault.
        dataset_name: Name for the dataset (will be normalized).
        force: If True, reprocess all documents even if unchanged.
        vault_schema: Optional VaultSchema subclass for typed frontmatter mapping.
    """
    type_name: str = "obsidian"
    vault_schema: type | None = None
    @model_validator(mode="after")
    def validate_source_path(self) -> "IngestObsidianConfig":
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
