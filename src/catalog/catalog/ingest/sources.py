"""Source factories for dataset ingestion.

Provides registration mechanisms for integrations to define their own
source types and config factories.
"""

from functools import singledispatch
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from catalog.ingest.job import SourceConfig

__all__ = [
    "BaseSource",
    "create_ingest_config",
    "create_reader",
    "create_source",
    "register_ingest_config_factory",
]


class BaseSource:
    """Base class for document sources."""

    def documents(self):
        pass

    def transforms(self):
        pass


# Registry: source_type string -> factory function
_ingest_config_factories: dict[str, Callable[["SourceConfig"], Any]] = {}


def register_ingest_config_factory(source_type: str):
    """Decorator for integrations to register their ingest config factory.

    The factory function receives a SourceConfig and returns the
    integration-specific DatasetIngestConfig subclass.

    Args:
        source_type: The string type identifier (e.g., "obsidian", "directory").

    Example:
        @register_ingest_config_factory("obsidian")
        def create_obsidian_ingest_config(source_config: SourceConfig) -> IngestObsidianConfig:
            ...
    """

    def decorator(func: Callable[["SourceConfig"], Any]) -> Callable[["SourceConfig"], Any]:
        _ingest_config_factories[source_type] = func
        return func

    return decorator


def create_ingest_config(source_config: "SourceConfig") -> Any:
    """Create an integration-specific ingest config from a generic SourceConfig.

    Looks up the factory function by source_config.type and invokes it.
    Lazy-imports source modules to ensure all factories are registered.

    Args:
        source_config: Generic source configuration from YAML job file.

    Returns:
        Integration-specific DatasetIngestConfig subclass instance.

    Raises:
        TypeError: If no factory is registered for the source type.
    """
    # Trigger registration of all source factories
    import catalog.ingest.directory  # noqa: F401
    import catalog.integrations  # noqa: F401

    factory = _ingest_config_factories.get(source_config.type)
    if factory is None:
        raise TypeError(
            f"Unknown source type: {source_config.type!r}. "
            f"Available: {list(_ingest_config_factories.keys())}"
        )
    return factory(source_config)


@singledispatch
def create_source(config):
    """Create a source from an ingest config. Dispatches on config type."""
    raise TypeError(f"Unsupported config type: {type(config)}")


@singledispatch
def create_reader(config):
    """Create a reader from an ingest config. Dispatches on config type."""
    raise TypeError(f"Unsupported config type: {type(config)}")







