"""Plugin management endpoints.

Provides plugin discovery, details retrieval, and reload functionality.
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException

from ...infrastructure.plugins.sdk_manager import SDKPluginManager
from ..schemas import PluginInfo
from ..services import global_service_container

plugins_api_router = APIRouter()


def get_plugin_manager() -> SDKPluginManager:
    """Retrieve plugin manager from global service container."""
    return global_service_container.get_plugin_manager()


@plugins_api_router.get("/plugins", response_model=List[PluginInfo])
async def list_available_plugins(plugin_manager: SDKPluginManager = Depends(get_plugin_manager)) -> List[PluginInfo]:
    """Retrieve all discovered plugins with metadata and health status."""
    discovered_plugins: List[PluginInfo] = []

    for plugin_identifier in plugin_manager.get_available_plugins():
        plugin_bundle = plugin_manager.get_plugin_bundle(plugin_identifier)
        if plugin_bundle:
            plugin_metadata = plugin_bundle.metadata
            plugin_status = "healthy" if plugin_identifier in plugin_manager.healthy_plugins else "failed"

            discovered_plugins.append(
                PluginInfo(
                    name=plugin_metadata.name,
                    version=plugin_metadata.version,
                    description=plugin_metadata.description,
                    capabilities=plugin_metadata.capabilities,
                    status=plugin_status,
                )
            )

    return discovered_plugins


@plugins_api_router.get("/plugins/{plugin_name}", response_model=PluginInfo)
async def get_plugin_details(
    plugin_name: str, plugin_manager: SDKPluginManager = Depends(get_plugin_manager)
) -> PluginInfo:
    """Retrieve detailed metadata and status for specified plugin."""
    plugin_bundle = plugin_manager.get_plugin_bundle(plugin_name)
    if not plugin_bundle:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_name}' not found in available plugins")

    plugin_metadata = plugin_bundle.metadata
    plugin_status = "healthy" if plugin_name in plugin_manager.healthy_plugins else "failed"

    return PluginInfo(
        name=plugin_metadata.name,
        version=plugin_metadata.version,
        description=plugin_metadata.description,
        capabilities=plugin_metadata.capabilities,
        status=plugin_status,
    )


@plugins_api_router.post("/plugins/reload")
async def reload_all_plugins(plugin_manager: SDKPluginManager = Depends(get_plugin_manager)) -> dict:
    """Reload all plugins and rebuild orchestrator graph."""
    try:
        plugin_manager.reload_plugins()
        try:
            orchestrator = global_service_container.get_orchestrator()
            orchestrator.rebuild_graph()
        except Exception as e:
            plugins_api_router.logger.warning(f"Failed to rebuild orchestrator graph after reload: {e}")
        return {
            "status": "success",
            "loaded": list(plugin_manager.get_available_plugins()),
            "healthy": list(plugin_manager.healthy_plugins),
            "failed": list(plugin_manager.failed_plugins),
        }
    except Exception as reload_error:
        raise HTTPException(status_code=500, detail=f"Plugin reload failed: {str(reload_error)}")


router = plugins_api_router
