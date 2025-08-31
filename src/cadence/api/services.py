"""API service initialization utilities.

Provides service container initialization for the Cadence framework API layer.
"""

from __future__ import annotations

from ..config.settings import Settings
from ..core.services.service_container import global_service_container, initialize_container


async def initialize_api(application_settings: Settings) -> None:
    """Initialize the global service container with application settings.

    Sets up infrastructure, LLM providers, plugin manager, and application services.
    """
    await initialize_container(application_settings)


__all__ = ["initialize_api", "global_service_container"]
