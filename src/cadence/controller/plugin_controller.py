"""Plugin management API endpoints (org-scoped).

Provides listing (system + org combined), org plugin upload, soft-delete,
and settings schema retrieval.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel

from cadence.controller.schemas.validators import validate_plugin_file
from cadence.middleware.authorization_middleware import (
    require_org_admin_access,
    require_org_member,
)
from cadence.middleware.tenant_context_middleware import TenantContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/orgs/{org_id}/plugins", tags=["plugins"])


class PluginMetadataResponse(BaseModel):
    """Plugin metadata response.

    Attributes:
        id: Database primary key
        pid: Reverse-domain plugin identifier
        name: Plugin name
        version: Plugin version
        description: Plugin description
        tag: Free-form search tag
        is_latest: Whether this is the latest version
        capabilities: List of capabilities
        agent_type: Agent type (specialized/general)
        stateless: Whether plugin is stateless
        source: Plugin source (system/org)
        default_settings: Default settings keyed by field name
    """

    id: str
    pid: str
    name: str
    version: str
    description: str
    tag: Optional[str] = None
    is_latest: bool
    capabilities: List[str]
    agent_type: str
    stateless: bool
    source: str
    default_settings: Dict[str, Any] = {}


class PluginSettingSchema(BaseModel):
    """Plugin setting schema definition."""

    key: str
    name: str
    type: str
    default: Any
    description: str
    required: bool
    sensitive: bool


@router.get("", response_model=List[PluginMetadataResponse])
async def list_plugins(
    request: Request,
    tag: Optional[str] = None,
    context: TenantContext = Depends(require_org_member),
):
    """List all available plugins for tenant (system + org combined).

    Args:
        request: FastAPI request
        tag: Optional tag filter
        context: Tenant context from JWT

    Returns:
        List of plugin metadata
    """
    plugin_service = request.app.state.plugin_service

    try:
        plugins = await plugin_service.list_available(context.org_id, tag=tag)
        return [PluginMetadataResponse(**p) for p in plugins]

    except Exception as e:
        logger.error(f"Failed to list plugins: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list available plugins",
        )


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_org_plugin(
    file: UploadFile = File(...),
    request: Request = None,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Upload an org-specific plugin package.

    Args:
        file: Plugin zip file
        request: FastAPI request
        context: Tenant context from JWT

    Returns:
        Upload confirmation with pid and version
    """
    validate_plugin_file(file)

    try:
        zip_bytes = await file.read()
        plugin_service = request.app.state.plugin_service

        plugin = await plugin_service.upload_org_plugin(
            org_id=context.org_id,
            zip_bytes=zip_bytes,
            caller_id=context.user_id,
        )

        logger.info(
            f"Org plugin uploaded: {context.org_id}/{plugin.pid} v{plugin.version}"
        )

        return {
            "message": "Plugin uploaded successfully",
            "id": str(plugin.id),
            "pid": plugin.pid,
            "version": plugin.version,
            "org_id": context.org_id,
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to upload org plugin: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload plugin package",
        )


@router.delete("/{plugin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_org_plugin(
    plugin_id: str,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Soft-delete an org plugin.

    Args:
        plugin_id: Plugin database ID
        request: FastAPI request
        context: Tenant context from JWT

    Raises:
        HTTPException: 404 if plugin not found, 500 on failure
    """
    plugin_service = request.app.state.plugin_service

    try:
        deleted = await plugin_service.delete_org_plugin(
            org_id=context.org_id,
            plugin_id=plugin_id,
            caller_id=context.user_id,
        )
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Plugin {plugin_id} not found in your organization",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete org plugin {plugin_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete plugin",
        )


@router.get("/{plugin_pid}/settings-schema", response_model=List[PluginSettingSchema])
async def get_plugin_settings_schema(
    plugin_pid: str,
    request: Request,
    context: TenantContext = Depends(require_org_member),
):
    """Get plugin settings schema for dynamic UI generation.

    Args:
        plugin_pid: Reverse-domain plugin identifier
        request: FastAPI request
        context: Tenant context from JWT

    Returns:
        Plugin settings schema
    """
    plugin_service = request.app.state.plugin_service

    try:
        schema = plugin_service.get_settings_schema(
            plugin_pid,
            context.org_id,
        )

        if not schema:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Settings schema not found for plugin {plugin_pid}",
            )

        return [PluginSettingSchema(**setting) for setting in schema]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get plugin settings schema: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve plugin settings schema",
        )
