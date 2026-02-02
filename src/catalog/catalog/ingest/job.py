"""catalog.ingest.job - YAML-driven ingestion job configuration.

Defines Pydantic models for parameterized ingestion jobs loaded from YAML
files via Hydra. A DatasetJob captures source, embedding, and pipeline
caching settings, and can produce the corresponding IngestObsidianConfig
and embedding model.

Example YAML::

    source:
      type: obsidian
      source_path: /Users/mike/Obsidian/MyVault
      vault_schema: catalog.integrations.obsidian.vault_schema.VaultSchema

    embedding:
      backend: mlx
      model_name: mlx-community/all-MiniLM-L6-v2-bf16
      batch_size: 32

    pipeline:
      cache_enabled: true
      docstore_strategy: upserts

Example usage::

    job = DatasetJob.from_yaml(Path("configs/my_vault.yaml"))
    config = job.to_ingest_config()
    embed_model = job.create_embed_model()
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from agentlayer.logging import get_logger

if TYPE_CHECKING:
    from llama_index.core.embeddings import BaseEmbedding

    from catalog.integrations.obsidian import IngestObsidianConfig

__all__ = [
    "DatasetJob",
    "EmbeddingConfig",
    "PipelineConfig",
    "SourceConfig",
]

logger = get_logger(__name__)


def _import_class(dotted_path: str) -> type:
    """Import a class from a dotted path string.

    Follows the same pattern as Hydra's ``_target_`` resolution and
    Django's ``import_string()``.

    Args:
        dotted_path: Fully-qualified class path, e.g.
            ``"catalog.integrations.obsidian.vault_schema.VaultSchema"``.

    Returns:
        The resolved class.

    Raises:
        ImportError: If the module cannot be imported.
        AttributeError: If the class is not found in the module.
    """
    module_path, _, class_name = dotted_path.rpartition(".")
    if not module_path:
        raise ImportError(f"Invalid dotted path (no module): {dotted_path}")
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


class SourceConfig(BaseModel):
    """Source configuration for a dataset job."""

    type: Literal["obsidian"] = "obsidian"
    source_path: Path
    dataset_name: str | None = None
    vault_schema: str | None = None
    force: bool = False

    def resolve_vault_schema(self) -> type | None:
        """Resolve the vault_schema dotted path to an actual class.

        Returns:
            The resolved class, or None if vault_schema is not set.
        """
        if self.vault_schema is None:
            return None
        return _import_class(self.vault_schema)


class EmbeddingConfig(BaseModel):
    """Embedding model configuration for a dataset job."""

    backend: Literal["mlx", "huggingface"] = "mlx"
    model_name: str = "mlx-community/all-MiniLM-L6-v2-bf16"
    batch_size: int = 32


class PipelineConfig(BaseModel):
    """Pipeline caching configuration."""

    #cache_enabled: bool = True
    #docstore_strategy: Literal["upserts", "duplicates_only", "upserts_and_delete"] = "upserts"
    splitter_chunk_size: int = 768
    splitter_chunk_overlap: int = 96

class DatasetJob(BaseModel):
    """Top-level configuration for an ingestion job.

    Loaded from a YAML file via :meth:`from_yaml`, validates into typed
    sub-models, and provides conversion methods to produce the objects
    needed by :class:`DatasetIngestPipeline`.
    """

    source: SourceConfig
    embedding: EmbeddingConfig | None = None
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)

    @classmethod
    def from_yaml(cls, path: Path) -> DatasetJob:
        """Load a DatasetJob from a YAML file via Hydra compose.

        Uses Hydra's ``compose()`` API for variable interpolation and
        config composition without requiring ``@hydra.main()``.

        Args:
            path: Path to the YAML configuration file.

        Returns:
            Validated DatasetJob instance.

        Raises:
            FileNotFoundError: If the YAML file does not exist.
            ValidationError: If the YAML contents fail Pydantic validation.
        """
        from hydra import compose, initialize_config_dir
        from omegaconf import OmegaConf

        path = path.resolve()
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        config_dir = str(path.parent)
        config_name = path.stem

        with initialize_config_dir(config_dir=config_dir, version_base=None):
            cfg = compose(config_name=config_name)

        raw = OmegaConf.to_container(cfg, resolve=True)
        return cls.model_validate(raw)

    def to_ingest_config(self) -> IngestObsidianConfig:
        """Convert to an IngestObsidianConfig.

        Resolves ``vault_schema`` from dotted path to the actual class
        and derives ``dataset_name`` from the vault folder name if not
        explicitly set.

        Returns:
            IngestObsidianConfig ready for use with DatasetIngestPipeline.
        """
        from catalog.integrations.obsidian import IngestObsidianConfig

        dataset_name = self.source.dataset_name or self.source.source_path.name
        vault_schema_cls = self.source.resolve_vault_schema()

        return IngestObsidianConfig(
            source_path=self.source.source_path,
            dataset_name=dataset_name,
            force=self.source.force,
            vault_schema=vault_schema_cls,
        )

    def create_embed_model(self) -> BaseEmbedding:
        """Create an embedding model from this job's config.

        When the ``embedding`` section is omitted from the YAML config,
        falls back to the application-level settings via
        :func:`catalog.embedding.get_embed_model`.

        Returns:
            A LlamaIndex BaseEmbedding instance.
        """
        if self.embedding is None:
            from catalog.embedding import get_embed_model

            logger.debug("No job-level embedding config; using application settings")
            return get_embed_model()

        cfg = self.embedding

        if cfg.backend == "mlx":
            from catalog.embedding.mlx import MLXEmbedding

            logger.debug(f"Loading MLX embedding model: {cfg.model_name}")
            return MLXEmbedding(
                model_name=cfg.model_name,
                embed_batch_size=cfg.batch_size,
            )
        else:
            from llama_index.embeddings.huggingface import HuggingFaceEmbedding

            logger.debug(f"Loading HuggingFace embedding model: {cfg.model_name}")
            return HuggingFaceEmbedding(
                model_name=cfg.model_name,
                embed_batch_size=cfg.batch_size,
            )
