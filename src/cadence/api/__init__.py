"""API package for Cadence framework.

Provides FastAPI router and service initialization for the multi-agent conversation system.
"""

from ..core.services.service_container import initialize_container
from .routes import router

__all__ = ["router", "initialize_container"]
