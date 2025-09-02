"""Plugin Management API Endpoints.

This router provides comprehensive plugin discovery, monitoring, and management functionality.
It allows administrators to view plugin status, retrieve detailed information about available plugins,
and reload the entire plugin system when updates are deployed.
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from ...infrastructure.plugins.sdk_manager import SDKPluginManager
from ...infrastructure.plugins.upload_manager import PluginUploadManager, PluginUploadResult
from ..schemas import PluginInfo
from ..services import global_service_container

plugins_api_router = APIRouter()


def get_plugin_manager() -> SDKPluginManager:
    """Dependency injection function to retrieve the plugin manager from the global service container."""
    return global_service_container.get_plugin_manager()


def get_upload_manager() -> PluginUploadManager:
    """Dependency injection function to retrieve the upload manager."""
    plugin_manager = global_service_container.get_plugin_manager()
    return PluginUploadManager(plugin_manager)


@plugins_api_router.get("/plugins", response_model=List[PluginInfo])
async def list_available_plugins(plugin_manager: SDKPluginManager = Depends(get_plugin_manager)) -> List[PluginInfo]:
    """Retrieve comprehensive information about all discovered plugins in the system.

    Returns a list of all plugins with their metadata, capabilities, and current health status
    for system monitoring and administration purposes.
    """
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
                    source=plugin_manager.get_plugin_source(plugin_metadata.name),
                )
            )

    return discovered_plugins


@plugins_api_router.get("/plugins/{plugin_name}", response_model=PluginInfo)
async def get_plugin_details(
    plugin_name: str, plugin_manager: SDKPluginManager = Depends(get_plugin_manager)
) -> PluginInfo:
    """Retrieve detailed metadata and operational status for a specific plugin.

    Provides comprehensive information about a single plugin including its capabilities,
    version details, and current health status for troubleshooting and monitoring.
    """
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
    """Reload the entire plugin system and rebuild the orchestrator graph.

    This endpoint triggers a complete plugin reload, which is useful after deploying
    new plugin versions or when troubleshooting plugin-related issues. The orchestrator
    graph is automatically rebuilt to incorporate any changes.
    """
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


@plugins_api_router.post("/plugins/upload")
async def upload_plugin(
    file: UploadFile = File(...),
    force_overwrite: bool = Form(default=False),
    upload_manager: PluginUploadManager = Depends(get_upload_manager),
) -> JSONResponse:
    """Upload a plugin package as a ZIP file.

    This endpoint accepts plugin packages in ZIP format with the naming convention:
    name-version.zip (e.g., my_plugin-1.0.0.zip)

    The plugin will be validated, extracted, and automatically loaded into the system.
    """
    try:
        result = upload_manager.upload_plugin(file, force_overwrite)

        if result.success:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": result.message,
                    "plugin_name": result.plugin_name,
                    "plugin_version": result.plugin_version,
                    "details": result.details,
                },
            )
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": result.message,
                    "plugin_name": result.plugin_name,
                    "plugin_version": result.plugin_version,
                    "details": result.details,
                },
            )
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": f"Upload failed: {str(e)}"})


router = plugins_api_router
