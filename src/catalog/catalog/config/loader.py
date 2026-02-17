"""catalog.config.loader - Hydra-based application configuration loader.

Follows the same pattern as ``catalog.ingest.job.DatasetJob.from_yaml()``:
uses Hydra's ``compose()`` API (not ``@hydra.main()``) for YAML loading
with variable interpolation and config composition.

The loader produces ``catalog.core.settings.Settings`` instances by:
1. Loading YAML via Hydra into an ``AppConfig`` Pydantic model
2. Converting the validated config to a dict
3. Constructing a ``Settings`` instance using a custom source priority
   so that environment variables always override YAML values:
   ``env vars > YAML config > Pydantic defaults``
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agentlayer.logging import get_logger

from catalog.config.schema import AppConfig

__all__ = [
    "load_app_config",
    "load_app_config_from_file",
]

logger = get_logger(__name__)

_DEFAULT_CONFIG_DIR = Path(__file__).parent / "defaults"


def _build_settings_from_yaml(config_dict: dict[str, Any]) -> "Settings":
    """Construct a Settings instance with YAML values below env vars in priority.

    Uses ``settings_customise_sources`` to ensure the priority order is:
    ``env vars > YAML (init kwargs) > field defaults``.

    By default pydantic-settings treats init kwargs as highest priority.
    This function creates a temporary subclass that demotes init kwargs
    below environment variables.

    Args:
        config_dict: Validated config dict from AppConfig.to_settings_dict().

    Returns:
        Settings instance with correct source priority.
    """
    from pydantic_settings import BaseSettings

    from catalog.core.settings import Settings

    class _YamlBackedSettings(Settings):
        """Settings subclass that prioritizes env vars over init kwargs."""

        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: Any,
            env_settings: Any,
            dotenv_settings: Any,
            file_secret_settings: Any,
        ) -> tuple:
            # env vars first, then init kwargs (YAML values), then secrets
            return (env_settings, init_settings, dotenv_settings, file_secret_settings)

    settings = _YamlBackedSettings(**config_dict)
    settings.ensure_directories()
    return settings


def load_app_config(
    config_name: str = "default",
    config_dir: Path | None = None,
    overrides: list[str] | None = None,
) -> "Settings":
    """Load application configuration from YAML via Hydra and return Settings.

    Loads the named YAML config file using Hydra's ``compose()`` API,
    validates it into an ``AppConfig`` model, then constructs a
    ``Settings`` instance. Environment variables (``IDX_*``) always
    override YAML-supplied values.

    Args:
        config_name: Stem of the YAML file to load (without ``.yaml``).
            Defaults to ``"default"`` which loads ``defaults/default.yaml``.
        config_dir: Directory containing config files. Defaults to the
            ``defaults/`` directory shipped with this module.
        overrides: Hydra override strings, e.g. ``["log_level=DEBUG"]``.

    Returns:
        A fully-configured ``Settings`` instance.

    Raises:
        FileNotFoundError: If the resolved config directory does not exist.
    """
    from hydra import compose, initialize_config_dir
    from hydra.core.global_hydra import GlobalHydra
    from omegaconf import OmegaConf

    if config_dir is None:
        config_dir = _DEFAULT_CONFIG_DIR

    config_dir = config_dir.resolve()
    if not config_dir.exists():
        raise FileNotFoundError(f"Config directory not found: {config_dir}")

    # Clear any previous Hydra state (compose() requires a clean GlobalHydra)
    GlobalHydra.instance().clear()

    try:
        with initialize_config_dir(config_dir=str(config_dir), version_base=None):
            cfg = compose(config_name=config_name, overrides=overrides or [])

        raw = OmegaConf.to_container(cfg, resolve=True)
        logger.debug(f"Loaded Hydra config '{config_name}' from {config_dir}")

        # Validate through AppConfig to catch schema errors early
        app_config = AppConfig.model_validate(raw)
        config_dict = app_config.to_settings_dict()

        return _build_settings_from_yaml(config_dict)

    finally:
        GlobalHydra.instance().clear()


def load_app_config_from_file(
    path: Path,
    overrides: list[str] | None = None,
) -> "Settings":
    """Load application configuration from an arbitrary YAML file path.

    Convenience wrapper around :func:`load_app_config` for loading
    a specific file rather than a named config from a directory.

    Args:
        path: Absolute or relative path to a YAML config file.
        overrides: Hydra override strings.

    Returns:
        A fully-configured ``Settings`` instance.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    return load_app_config(
        config_name=path.stem,
        config_dir=path.parent,
        overrides=overrides,
    )
