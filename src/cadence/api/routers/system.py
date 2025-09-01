"""System monitoring endpoints.

Provides system health status and monitoring functionality.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ...infrastructure.plugins.sdk_manager import SDKPluginManager
from ..schemas import SystemStatus
from ..services import global_service_container

system_api_router = APIRouter()


def get_plugin_manager() -> SDKPluginManager:
    """Retrieve plugin manager from global service container."""
    return global_service_container.get_plugin_manager()


@system_api_router.get("/status", response_model=SystemStatus)
async def get_comprehensive_system_status(
    plugin_manager: SDKPluginManager = Depends(get_plugin_manager),
) -> SystemStatus:
    """Retrieve comprehensive system status and plugin health information."""
    return SystemStatus(
        status="operational",
        available_plugins=plugin_manager.get_available_plugins(),
        healthy_plugins=list(plugin_manager.healthy_plugins),
        failed_plugins=list(plugin_manager.failed_plugins),
        total_sessions=0,
    )


@system_api_router.get("/health")
async def simple_health_check() -> dict:
    """Retrieve lightweight health status for load balancers."""
    return {"status": "healthy"}


router = system_api_router
