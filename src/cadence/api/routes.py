"""Main API Router Configuration.

This module centralizes all API endpoints by aggregating routers from different domains
(chat, plugins, system) and provides the main application router with health monitoring endpoints.
"""

from fastapi import APIRouter

from cadence.api.routers import chat, plugins, system

router = APIRouter()

router.include_router(chat.router, prefix="/chat", tags=["chat"])
router.include_router(plugins.router, prefix="/plugins", tags=["plugins"])
router.include_router(system.router, prefix="/system", tags=["system"])


@router.get("/")
async def root():
    """API root endpoint providing service information and navigation links."""
    return {"message": "Welcome to Cadence AI Framework API", "version": "1.0.5", "docs": "/docs", "health": "/health"}


@router.get("/health")
async def health_check():
    """Service health check endpoint for monitoring and load balancer health verification."""
    return {"status": "healthy", "service": "cadence-api", "version": "1.0.5"}
