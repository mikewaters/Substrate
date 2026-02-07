"""Pydantic schemas for Heptabase export ingestion configuration."""

from typing import Any, Dict

from pydantic import model_validator

from catalog.ingest.sources import DatasetSourceConfig


class SourceHeptabaseConfig(DatasetSourceConfig):
    """Configuration for Heptabase export ingestion.

    Attributes:
        source_path: Path to the Heptabase export directory.
        dataset_name: Name for the dataset (will be normalized).
        force: If True, reprocess all documents even if unchanged.
        vault_schema: Optional VaultSchema subclass for typed frontmatter mapping.
    """

    type_name: str = "heptabase"
    vault_schema: type | None = None

    @model_validator(mode="after")
    def validate_source_path(self) -> "SourceHeptabaseConfig":
        """Validate that the given path is a plausible Heptabase export."""
        if not self.source_path.exists():
            raise ValueError(f"Export path does not exist: {self.source_path}")

        if not self.source_path.is_dir():
            raise ValueError(f"Export path is not a directory: {self.source_path}")

        return self

    @model_validator(mode="before")
    def post_update(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Auto-set dataset_name from source_path if not provided."""
        if values.get("source_path", False):
            if not values.get("dataset_name", False):
                values["dataset_name"] = values["source_path"].name
        return values
