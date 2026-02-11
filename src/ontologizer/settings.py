"""Application settings using Pydantic.

This module defines the configuration schema for the ontology system,
including database connection settings, logging, and feature flags.
"""

import logging
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class SQLiteDatabaseSettings(BaseSettings):
    """High-level database configuration.

    Infrastructure concerns (pooling, WAL mode, etc.) are handled by
    Advanced-Alchemy's EngineConfig in database/config.py.
    """

    db_path: Path = Field(
        default=Path(".data/ontology.db"),
        description="Path to the SQLite database file",
    )
    echo: bool = Field(
        default=False,
        description="Echo SQL statements to stdout (for debugging)",
    )

    @property
    def connection_string(self) -> str:
        """Generate SQLAlchemy connection string for Advanced-Alchemy.

        Returns:
            Connection string in the format: sqlite+aiosqlite:///path/to/db
        """
        return f"sqlite+aiosqlite:///{self.db_path}"


DatabaseSettings = SQLiteDatabaseSettings


class LoggingSettings(BaseModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    structured: bool = True


class LLMSettings(BaseSettings):
    """LLM configuration for document classification."

    Supports both remote providers (Anthropic, OpenAI) and local OpenAI-compatible
    endpoints (LM Studio, vLLM, Ollama, etc.).
    """

    model_config = SettingsConfigDict(
        env_prefix="substrate_llm_",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Model selection: "openai-compatible" or "anthropic"
    provider: Literal["openai-compatible", "anthropic"] = "anthropic"

    # Model name (e.g., "gpt-4", "claude-sonnet-4-20250514", "neural-chat-7b")
    model_name: str = "claude-sonnet-4-20250514"

    # OpenAI-compatible endpoint URL (for local models)
    # Examples: http://localhost:1234/v1, http://localhost:8000/v1
    openai_base_url: str | None = None

    # API key for the endpoint (can be dummy for local models)
    api_key: str | None = None

    # Temperature for generation (0.0-2.0)
    temperature: float = 0.7

    # Max tokens for responses
    max_tokens: int = 2048


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="substrate_",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    environment: Literal["dev", "test", "production"] = "production"

    def configure_logging(self) -> None:
        """Configure Python logging based on settings."""
        if self.logging.structured:
            from ontologizer.utils.logging import configure_json_logging

            configure_json_logging(level=self.logging.level)
        else:
            logging.basicConfig(
                level=getattr(logging, self.logging.level),
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            )


# Global settings instance
_settings: Settings | None = None


def get_settings(reload: bool = False) -> Settings:
    """Get the global settings instance.

    Args:
        reload: If True, reload settings from environment/files

    Returns:
        Settings instance
    """
    global _settings

    if _settings is None or reload:
        _settings = Settings()
        _settings.configure_logging()
        logger.info(
            f"Settings loaded: environment={_settings.environment}, "
            f"db_path={_settings.database.db_path}, "
            f"echo={_settings.database.echo}"
        )

    return _settings


# class DatabaseSettings(BaseSettings):
#     """Database configuration settings."""

#     model_config = SettingsConfigDict(env_prefix="ONTOLOGY_DB_")

#     # Database path - defaults to .data/ontology.db in project root
#     db_path: Path = Field(
#         default=Path(".data/ontology.db"),
#         description="Path to the SQLite database file",
#     )

#     # Connection pool settings
#     pool_size: int = Field(
#         default=5,
#         description="Number of connections to maintain in the pool",
#     )

#     max_overflow: int = Field(
#         default=10,
#         description="Maximum number of connections that can be created beyond pool_size",
#     )

#     pool_timeout: int = Field(
#         default=30,
#         description="Timeout in seconds for getting a connection from the pool",
#     )

#     # WAL mode for better concurrency
#     enable_wal: bool = Field(
#         default=True,
#         description="Enable Write-Ahead Logging for better concurrency",
#     )

#     # Echo SQL for debugging
#     echo: bool = Field(
#         default=True,
#         description="Echo SQL statements to stdout (for debugging)",
#     )

#     @property
#     def url(self) -> str:
#         """Generate SQLAlchemy database URL."""
#         return f"sqlite:///{self.db_path}"


# class LoggingSettings(BaseSettings):
#     """Logging configuration settings."""

#     model_config = SettingsConfigDict(env_prefix="ONTOLOGY_LOG_")

#     level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
#         default="INFO",
#         description="Logging level",
#     )

#     structured: bool = Field(
#         default=True,
#         description="Emit logs in JSON format when True.",
#     )
