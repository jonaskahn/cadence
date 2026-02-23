"""Orchestrator plugin settings management API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from cadence.controller.schemas.orchestrator_schemas import (
    ActivatePluginVersionRequest,
    OrchestratorResponse,
    UpdatePluginSettingsRequest,
)
from cadence.middleware.authorization_middleware import require_org_admin_access
from cadence.middleware.tenant_context_middleware import TenantContext
from cadence.service.settings_service import SettingsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/orgs/{org_id}/orchestrators", tags=["orchestrators"])


@router.patch("/{instance_id}/plugin-settings", response_model=OrchestratorResponse)
async def update_plugin_settings(
    instance_id: str,
    update_request: UpdatePluginSettingsRequest,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Partial update of plugin settings (merge into existing)."""
    settings_service: SettingsService = request.app.state.settings_service
    event_publisher = getattr(request.app.state, "event_publisher", None)

    try:
        updated = await settings_service.update_orchestrator_plugin_settings(
            instance_id=instance_id,
            org_id=context.org_id,
            plugin_settings_override=update_request.plugin_settings,
            caller_id=context.user_id,
            event_publisher=event_publisher,
        )
        return OrchestratorResponse(**updated)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            f"Failed to update plugin settings for {instance_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update plugin settings",
        )


@router.put("/{instance_id}/plugin-settings/sync", response_model=OrchestratorResponse)
async def sync_plugin_settings(
    instance_id: str,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Re-fetch latest default_settings for all active plugins and overwrite plugin_settings."""
    settings_service: SettingsService = request.app.state.settings_service
    plugin_service = request.app.state.plugin_service
    event_publisher = getattr(request.app.state, "event_publisher", None)

    try:
        updated = await settings_service.sync_orchestrator_plugin_settings(
            instance_id=instance_id,
            org_id=context.org_id,
            plugin_service=plugin_service,
            caller_id=context.user_id,
            event_publisher=event_publisher,
        )
        return OrchestratorResponse(**updated)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            f"Failed to sync plugin settings for {instance_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync plugin settings",
        )


@router.post(
    "/{instance_id}/plugin-settings/activate", response_model=OrchestratorResponse
)
async def activate_plugin_version(
    instance_id: str,
    activate_request: ActivatePluginVersionRequest,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Activate a specific plugin version on an orchestrator instance."""
    settings_service: SettingsService = request.app.state.settings_service
    plugin_service = request.app.state.plugin_service
    event_publisher = getattr(request.app.state, "event_publisher", None)

    try:
        updated = await settings_service.activate_plugin_version(
            instance_id=instance_id,
            org_id=context.org_id,
            pid=activate_request.pid,
            version=activate_request.version,
            plugin_service=plugin_service,
            caller_id=context.user_id,
            event_publisher=event_publisher,
        )
        return OrchestratorResponse(**updated)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            f"Failed to activate plugin version for {instance_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate plugin version",
        )
