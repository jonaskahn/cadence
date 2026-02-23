"""System plugin management API endpoints (admin-only).

Provides CRUD operations for the system-wide plugin catalog.
All endpoints require sys_admin role.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel

from cadence.controller.schemas.validators import validate_plugin_file
from cadence.infrastructure.persistence.postgresql.models import SystemPlugin
from cadence.middleware.authorization_middleware import require_sys_admin
from cadence.middleware.tenant_context_middleware import TenantContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/plugins", tags=["admin"])


class SystemPluginResponse(BaseModel):
    """System plugin response model."""

    id: str
    pid: str
    version: str
    name: str
    description: Optional[str] = None
    tag: Optional[str] = None
    is_latest: bool
    s3_path: Optional[str] = None
    default_settings: Dict[str, Any] = {}
    capabilities: List[Any] = []
    agent_type: str
    stateless: bool
    is_active: bool


@router.get(
    "",
    response_model=List[SystemPluginResponse],
    dependencies=[Depends(require_sys_admin)],
)
async def list_system_plugins(request: Request, tag: Optional[str] = None):
    """List all system plugins, optionally filtered by tag.

    Args:
        request: FastAPI request
        tag: Optional tag filter

    Returns:
        List of system plugin metadata
    """
    system_plugin_repo = request.app.state.system_plugin_repo

    try:
        plugins = await system_plugin_repo.list_all(tag=tag)
        return [_to_response(p) for p in plugins]
    except Exception as e:
        logger.error(f"Failed to list system plugins: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list system plugins",
        )


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_system_plugin(
    file: UploadFile = File(...),
    request: Request = None,
    tenant_context: TenantContext = Depends(require_sys_admin),
):
    """Upload a system plugin package.

    Args:
        file: Plugin zip file
        request: FastAPI request
        tenant_context: Tenant context from JWT

    Returns:
        Upload confirmation with pid and version
    """
    validate_plugin_file(file)

    try:
        zip_bytes = await file.read()
        plugin_service = request.app.state.plugin_service

        plugin = await plugin_service.upload_system_plugin(
            zip_bytes=zip_bytes,
            caller_id=tenant_context.user_id,
        )

        logger.info(f"System plugin uploaded: {plugin.pid} v{plugin.version}")

        return {
            "message": "System plugin uploaded successfully",
            "id": str(plugin.id),
            "pid": plugin.pid,
            "version": plugin.version,
            "is_latest": plugin.is_latest,
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to upload system plugin: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload system plugin package",
        )


@router.get(
    "/{plugin_id}",
    response_model=SystemPluginResponse,
    dependencies=[Depends(require_sys_admin)],
)
async def get_system_plugin(plugin_id: str, request: Request):
    """Get a system plugin by ID.

    Args:
        plugin_id: Plugin database ID
        request: FastAPI request

    Returns:
        System plugin details
    """
    system_plugin_repo = request.app.state.system_plugin_repo

    try:
        plugin = await system_plugin_repo.get_by_id(plugin_id)
        if not plugin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"System plugin {plugin_id} not found",
            )
        return _to_response(plugin)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get system plugin {plugin_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve system plugin",
        )


@router.delete("/{plugin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def soft_delete_system_plugin(
    plugin_id: str,
    request: Request,
    tenant_context: TenantContext = Depends(require_sys_admin),
):
    """Soft-delete a system plugin (sets is_active=False).

    Args:
        plugin_id: Plugin database ID
        request: FastAPI request
        tenant_context: Tenant context from JWT
    """
    system_plugin_repo = request.app.state.system_plugin_repo

    try:
        deleted = await system_plugin_repo.soft_delete(
            plugin_id=plugin_id,
            caller_id=tenant_context.user_id,
        )
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"System plugin {plugin_id} not found",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete system plugin {plugin_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete system plugin",
        )


def _to_response(plugin: SystemPlugin) -> SystemPluginResponse:
    """Build a SystemPluginResponse from an ORM plugin object.

    Args:
        plugin: ORM plugin object

    Returns:
        SystemPluginResponse with all fields populated
    """
    return SystemPluginResponse(
        id=str(plugin.id),
        pid=plugin.pid,
        version=plugin.version,
        name=plugin.name,
        description=plugin.description,
        tag=plugin.tag,
        is_latest=plugin.is_latest,
        s3_path=plugin.s3_path,
        default_settings=plugin.default_settings or {},
        capabilities=plugin.capabilities or [],
        agent_type=plugin.agent_type,
        stateless=plugin.stateless,
        is_active=plugin.is_active,
    )
