"""Main API Router Configuration."""

from fastapi import APIRouter

from .routers import chat, plugins, system

router = APIRouter()

router.include_router(chat.router, prefix="/chat", tags=["chat", "obsolete"])
router.include_router(chat.router, prefix="/conversation", tags=["conversation", "chat"])
router.include_router(plugins.router, prefix="/plugins", tags=["plugins"])
router.include_router(system.router, prefix="/system", tags=["system"])


@router.get("/")
async def root():
    """API root endpoint providing service information and navigation links."""
    return {"message": "Welcome to Cadence AI Framework API", "version": "1.3.0", "docs": "/docs", "health": "/health"}


@router.get("/health")
async def health_check():
    """Service health check endpoint for monitoring and load balancer health verification."""
    return {"status": "healthy", "service": "cadence-api", "version": "1.3.0"}
