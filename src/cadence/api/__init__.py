"""API package for Cadence framework.

Provides FastAPI router and service initialization for the multi-agent conversation system.
"""

from .routes import router
from ..core.services.service_container import initialize_container

__all__ = ["router", "initialize_container"]
