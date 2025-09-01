"""API routes aggregation for Cadence framework.

Centralizes all API endpoints and provides router initialization for the FastAPI application.
"""

from fastapi import APIRouter

from cadence.api.routers import chat, plugins, system
from cadence.config.settings import Settings

router = APIRouter()

router.include_router(chat.router, prefix="/chat", tags=["chat"])
router.include_router(plugins.router, prefix="/plugins", tags=["plugins"])
router.include_router(system.router, prefix="/system", tags=["system"])


@router.get("/")
async def root():
    """API root endpoint with service information."""
    return {"message": "Welcome to Cadence AI Framework API", "version": "1.0.3", "docs": "/docs", "health": "/health"}


@router.get("/health")
async def health_check():
    """Service health check for monitoring systems."""
    return {"status": "healthy", "service": "cadence-api", "version": "1.0.3"}


async def initialize_api(settings: Settings) -> None:
    """Initialize API dependencies and service container."""
    pass
