"""Cadence Framework API Package.

This package provides the complete REST API interface for the Cadence multi-agent conversation framework.
It includes FastAPI routers for chat processing, plugin management, and system monitoring,
along with service initialization for the application layer.
"""

from ..core.services.service_container import initialize_container
from .routes import router

__all__ = ["router", "initialize_container"]
