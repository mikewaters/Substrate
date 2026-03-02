"""agentlayer.settings - Shared infrastructure configuration via pydantic-settings.

Provides base settings classes and path resolution for the Substrate platform.
Domain-specific packages (catalog, etc.) extend SubstrateSettings with their own fields.

All settings use the SUBSTRATE_ prefix for environment variables.

All config/data paths (databases, vector store, cache, jobs, etc.) derive from
a single config root. The config root is chosen by environment (SUBSTRATE_ENVIRONMENT)
unless overridden by SUBSTRATE_CONFIG_ROOT or SUBSTRATE_CONFIG_ROOT_<ENV>.

When SUBSTRATE_ENVIRONMENT is set, a TOML file named after that environment
(e.g. dev.toml, prod.toml) is read from a configurable directory. Values in that
file override Pydantic defaults only; environment variables still take precedence.
"""

from __future__ import annotations

import logging
import os
import tempfile
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, InitSettingsSource, SettingsConfigDict

logger = logging.getLogger(__name__)

__all__ = [
    "DEFAULT_CONFIG_ROOTS",
    "DatabasesSettings",
    "EmbeddingSettings",
    "Environment",
    "LLMSettings",
    "LogLevel",
    "PerformanceSettings",
    "SubstrateSettings",
    "get_settings",
]


LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
Environment = Literal["dev", "prod", "test"]

# Default config root per environment when SUBSTRATE_CONFIG_ROOT / SUBSTRATE_CONFIG_ROOT_<ENV> are unset.
DEFAULT_CONFIG_ROOTS: dict[Environment, Path] = {
    "dev": Path(".cache"),
    "prod": Path("~/.substrate").expanduser(),
    "test": Path(tempfile.mkdtemp(prefix="substrate-test-")),
}


def _resolve_config_root_from_env() -> Path:
    """Resolve config root from env only (for use before Settings exists)."""
    env_raw = os.environ.get("SUBSTRATE_ENVIRONMENT", "dev")
    environment: Environment = env_raw if env_raw in ("dev", "prod", "test") else "dev"
    explicit = os.environ.get("SUBSTRATE_CONFIG_ROOT")
    if explicit:
        return Path(explicit).expanduser().resolve()
    per_env = os.environ.get(f"SUBSTRATE_CONFIG_ROOT_{environment.upper()}")
    if per_env:
        return Path(per_env).expanduser().resolve()
    root = DEFAULT_CONFIG_ROOTS[environment]
    return root.expanduser().resolve() if isinstance(root, Path) and str(root).startswith("~") else root.resolve()


def _load_environment_toml_defaults(
    settings_cls: type[BaseSettings], toml_dir: Path | None
) -> dict[str, object]:
    """Load environment-named TOML from a package directory; return dict of default overrides or empty.

    Args:
        settings_cls: The settings class requesting the TOML source.
        toml_dir: Directory containing environment TOML files. If None, returns empty.
    """
    if toml_dir is None:
        return {}
    env_raw = os.environ.get("SUBSTRATE_ENVIRONMENT", "dev")
    environment: Environment = env_raw if env_raw in ("dev", "prod", "test") else "dev"
    toml_path = toml_dir / f"{environment}.toml"
    logger.info(
        "settings environment=%s, config dir=%s, config file=%s",
        environment,
        toml_dir,
        toml_path,
    )
    if not toml_path.is_file():
        logger.info("settings config file not found, using pydantic defaults only")
        return {}
    with toml_path.open("rb") as f:
        data = tomllib.load(f)
    logger.info("settings loaded %d top-level keys from config file", len(data))
    return data


class _EnvironmentTomlSettingsSource(InitSettingsSource):
    """Settings source that overrides defaults from {toml_dir}/{environment}.toml.

    Env vars take precedence over TOML values.
    """

    def __init__(self, settings_cls: type[BaseSettings]) -> None:
        toml_dir: Path | None = getattr(settings_cls, "_toml_dir", None)
        toml_data = _load_environment_toml_defaults(settings_cls, toml_dir)
        super().__init__(settings_cls, init_kwargs=toml_data)


class PerformanceSettings(BaseSettings):
    """Default performance settings for batch processing and concurrency."""

    model_config = SettingsConfigDict(
        env_prefix="SUBSTRATE_",
        extra="ignore",
    )

    batch_size: int = Field(
        default=100,
        ge=1,
        description="Default batch size for document processing",
    )
    concurrency: int = Field(
        default=4,
        ge=1,
        description="Default concurrency level for parallel operations",
    )
    embedding_batch_size: int = Field(
        default=32,
        ge=1,
        description="Batch size for embedding generation (deprecated: use embedding.batch_size)",
    )
    chunk_max_bytes: int = Field(
        default=2048,
        ge=256,
        description="Maximum bytes per chunk for embedding",
    )
    chunk_min_bytes: int = Field(
        default=128,
        ge=1,
        description="Minimum bytes per chunk (fragments smaller than this are merged)",
    )


class DatabasesSettings(BaseSettings):
    """Multi-database configuration for separate catalog and content storage.

    The catalog database stores metadata, FTS indexes, and resource hierarchy.
    The content database stores document bodies and large text content.
    """

    model_config = SettingsConfigDict(
        env_prefix="SUBSTRATE_DATABASES_",
        extra="ignore",
    )

    catalog_path: Path | None = Field(
        default=None,
        description="Path to the catalog SQLite database (default: config_root / 'catalog.db')",
    )
    content_path: Path | None = Field(
        default=None,
        description="Path to the content SQLite database (default: config_root / 'content.db')",
    )


class EmbeddingSettings(BaseSettings):
    """Embedding configuration for vector generation.

    Controls which embedding backend to use and model configuration.
    Supports MLX (Apple Silicon) and HuggingFace backends.
    """

    model_config = SettingsConfigDict(
        env_prefix="SUBSTRATE_EMBEDDING_",
        extra="ignore",
    )

    backend: Literal["mlx", "huggingface"] = Field(
        default="mlx",
        description="Embedding backend: 'mlx' for Apple Silicon, 'huggingface' for general",
    )
    model_name: str = Field(
        default="mlx-community/all-MiniLM-L6-v2-bf16",
        description="Name or path of the embedding model",
    )
    batch_size: int = Field(
        default=32,
        ge=1,
        description="Batch size for embedding generation",
    )
    embedding_dim: int = Field(
        default=384,
        ge=1,
        description="Embedding vector dimension (384 for MiniLM-L6-v2)",
    )


class LLMSettings(BaseSettings):
    """LLM configuration for generative tasks (reranking, query expansion).

    Controls the local generative model used by MLXProvider. Must be an
    autoregressive model supported by mlx-lm (not BERT/cross-encoder).
    """

    model_config = SettingsConfigDict(
        env_prefix="SUBSTRATE_LLM_",
        extra="ignore",
    )

    backend: Literal["mlx"] = Field(
        default="mlx",
        description="LLM backend: 'mlx' for Apple Silicon local inference",
    )
    model_name: str = Field(
        default="mlx-community/Llama-3.2-1B-Instruct-4bit",
        description="Name or path of the generative LLM (must be autoregressive, not BERT)",
    )


class SubstrateSettings(BaseSettings):
    """Base settings for Substrate platform packages.

    Handles environment detection, config root resolution, database paths,
    and shared infrastructure settings. Domain-specific packages should
    subclass this and add their own fields.

    Subclasses can set ``_toml_dir`` to a directory containing environment
    TOML files (e.g. dev.toml) for per-environment defaults.
    """

    _toml_dir: ClassVar[Path | None] = None

    model_config = SettingsConfigDict(
        env_prefix="SUBSTRATE_",
        env_nested_delimiter="__",
        extra="ignore",
        validate_default=True,
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: InitSettingsSource,
        env_settings: object,
        dotenv_settings: object,
        file_secret_settings: object,
    ) -> tuple[object, ...]:
        """Env and dotenv before TOML so env vars override environment file defaults."""
        toml_source = _EnvironmentTomlSettingsSource(settings_cls)
        return (init_settings, env_settings, dotenv_settings, toml_source, file_secret_settings)

    environment: Environment = Field(
        default="dev",
        description="Application environment: dev, prod, or test",
    )
    config_root: Path | None = Field(
        default=None,
        description="Root directory for all config and data; derived from environment if unset",
    )

    # Multi-database configuration
    databases: DatabasesSettings = Field(
        default_factory=DatabasesSettings,
        description="Multi-database paths for catalog and content separation",
    )

    # Derived paths
    vector_store_path: Path | None = Field(
        default=None,
        description="Path to LlamaIndex persist directory (default: config_root / 'vector_store')",
    )
    cache_path: Path | None = Field(
        default=None,
        description="Path to cache directory for temporary files (default: config_root / 'cache')",
    )
    job_config_path: Path | None = Field(
        default=None,
        description="Path to job configuration files (default: config_root / 'jobs')",
    )
    env_config_path: Path | None = Field(
        default=None,
        description="Path to environment configuration files (default: config_root / 'environments')",
    )

    # Logging
    log_level: LogLevel = Field(
        default="INFO",
        description="Logging level for the library",
    )

    # Embedding
    embedding: EmbeddingSettings = Field(
        default_factory=EmbeddingSettings,
        description="Embedding model configuration",
    )

    # LLM
    llm: LLMSettings = Field(
        default_factory=LLMSettings,
        description="LLM model configuration",
    )

    # Performance
    performance: PerformanceSettings = Field(
        default_factory=PerformanceSettings,
        description="Default performance settings",
    )

    @model_validator(mode="after")
    def _resolve_config_root_and_derived_paths(self) -> SubstrateSettings:
        """Resolve config_root from environment and fill derived path defaults."""
        root: Path
        source: str
        if self.config_root is not None:
            root = Path(self.config_root).expanduser().resolve()
            source = "SUBSTRATE_CONFIG_ROOT"
        else:
            per_env = os.environ.get(f"SUBSTRATE_CONFIG_ROOT_{self.environment.upper()}")
            if per_env:
                root = Path(per_env).expanduser().resolve()
                source = f"SUBSTRATE_CONFIG_ROOT_{self.environment.upper()}"
            else:
                root = DEFAULT_CONFIG_ROOTS[self.environment].resolve()
                source = f"default for environment={self.environment!r}"
        self.config_root = root
        logger.info(
            "settings environment=%s, config_root=%s (from %s)",
            self.environment,
            root,
            source,
        )

        if self.vector_store_path is None:
            self.vector_store_path = root / "vector_store"
        else:
            self.vector_store_path = Path(self.vector_store_path).expanduser().resolve()
        if self.cache_path is None:
            self.cache_path = root / "cache"
        else:
            self.cache_path = Path(self.cache_path).expanduser().resolve()
        if self.job_config_path is None:
            self.job_config_path = root / "jobs"
        else:
            self.job_config_path = Path(self.job_config_path).expanduser().resolve()
        if self.env_config_path is None:
            self.env_config_path = root / "environments"
        else:
            self.env_config_path = Path(self.env_config_path).expanduser().resolve()

        if self.databases.catalog_path is None:
            self.databases.catalog_path = root / "catalog.db"
        else:
            self.databases.catalog_path = Path(self.databases.catalog_path).expanduser().resolve()
        if self.databases.content_path is None:
            self.databases.content_path = root / "content.db"
        else:
            self.databases.content_path = Path(self.databases.content_path).expanduser().resolve()

        return self

    def ensure_directories(self) -> None:
        """Ensure that required directories exist.

        Creates config_root and the parent directories for database paths,
        vector_store_path, cache_path, and job_config_path if they do not exist.
        """
        assert self.config_root is not None
        assert self.vector_store_path is not None
        assert self.cache_path is not None
        assert self.databases.catalog_path is not None
        assert self.databases.content_path is not None
        self.config_root.mkdir(parents=True, exist_ok=True)
        self.databases.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        self.databases.content_path.parent.mkdir(parents=True, exist_ok=True)
        self.vector_store_path.mkdir(parents=True, exist_ok=True)
        self.cache_path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> SubstrateSettings:
    """Get the singleton SubstrateSettings instance.

    Returns a cached SubstrateSettings instance, creating it on first call.
    Domain-specific packages should override this with their own settings class.

    Returns:
        The singleton SubstrateSettings instance.
    """
    settings = SubstrateSettings()
    settings.ensure_directories()
    return settings
