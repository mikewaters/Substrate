"""catalog.config - Application-level Hydra configuration.

Provides YAML-driven application configuration that mirrors all settings
defined in ``catalog.core.settings``. Uses Hydra's ``compose()`` API for
variable interpolation and config composition.

Priority (highest to lowest):
    1. Environment variables (``IDX_*``)
    2. Hydra overrides (passed programmatically)
    3. YAML config file values
    4. Pydantic field defaults

Example usage::

    from catalog.config import load_app_config

    # Load default config
    settings = load_app_config()

    # Load with environment-specific overrides
    settings = load_app_config(overrides=["+environment=dev"])

    # Load from a custom config directory
    settings = load_app_config(config_dir=Path("my/configs"))
"""

from catalog.config.loader import load_app_config

__all__ = [
    "load_app_config",
]
