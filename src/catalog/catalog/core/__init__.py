"""catalog.core - Core infrastructure (settings, logging, status)."""

#from agentlayer.logging import configure_logging, get_logger
from catalog.core.observability import configure_observability
from catalog.core.settings import Settings, get_settings
from catalog.core.status import (
                                 ComponentStatus,
                                 HealthStatus,
                                 check_database,
                                 check_health,
                                 check_vector_store,
)

__all__ = [
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
    "check_vector_store",
]
