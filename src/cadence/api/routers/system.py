"""System Monitoring and Health Check API Endpoints.

This router provides comprehensive system monitoring capabilities including overall health status,
plugin health information, and lightweight health checks for load balancers and monitoring systems.
It enables administrators to monitor the operational status of the entire Cadence framework.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ...infrastructure.plugins.sdk_manager import SDKPluginManager
from ..schemas import SystemStatus
from ..services import global_service_container

system_api_router = APIRouter()


def get_plugin_manager() -> SDKPluginManager:
    """Dependency injection function to retrieve the plugin manager from the global service container."""
    return global_service_container.get_plugin_manager()


@system_api_router.get("/status", response_model=SystemStatus)
async def get_comprehensive_system_status(
    plugin_manager: SDKPluginManager = Depends(get_plugin_manager),
) -> SystemStatus:
    """Retrieve comprehensive system status and operational health information.

    Provides a complete overview of the system including plugin health status,
    available services, and system metrics for comprehensive monitoring and diagnostics.
    """
    return SystemStatus(
        status="operational",
        available_plugins=plugin_manager.get_available_plugins(),
        healthy_plugins=list(plugin_manager.healthy_plugins),
        failed_plugins=list(plugin_manager.failed_plugins),
        total_sessions=0,
    )


@system_api_router.get("/health")
async def simple_health_check() -> dict:
    """Retrieve lightweight health status for load balancers and basic monitoring.

    Returns a minimal health response suitable for load balancer health checks
    and basic system availability monitoring without detailed system information.
    """
    return {"status": "healthy"}


router = system_api_router
