"""catalog.core - Core infrastructure (settings, logging, status)."""

#from agentlayer.logging import configure_logging, get_logger
from agentlayer.observability import configure_observability
from agentlayer.pipeline import BasePipeline
from catalog.core.settings import Settings, get_settings
from catalog.core.status import (
                                 ComponentStatus,
                                 HealthStatus,
                                 check_database,
                                 check_health,
)

__all__ = [
    "BasePipeline",
    "Settings",
    #"configure_logging",
    "configure_observability",
    #"get_logger",
    "get_settings",
    # Status
    "ComponentStatus",
    "HealthStatus",
    "check_database",
    "check_health",
]
