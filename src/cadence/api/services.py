"""API Service Layer Initialization.

This module provides the service container initialization functionality for the Cadence framework API.
It handles the setup of infrastructure components, LLM providers, plugin management,
and application services required for the API to function properly.
"""

from __future__ import annotations

from ..config.settings import Settings
from ..core.services.service_container import global_service_container, initialize_container


async def initialize_api(application_settings: Settings) -> None:
    """Initialize the global service container with application configuration.

    Sets up the complete service infrastructure including database connections,
    LLM provider configurations, plugin manager initialization, and application services.
    This function must be called before the API can process any requests.
    """
    await initialize_container(application_settings)


__all__ = ["initialize_api", "global_service_container"]
