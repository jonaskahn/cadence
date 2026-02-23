"""Orchestrator lifecycle (load/unload) API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from cadence.controller.schemas.orchestrator_schemas import (
    LoadOrchestratorRequest,
    validate_orchestrator_access,
)
from cadence.middleware.authorization_middleware import require_org_admin_access
from cadence.middleware.tenant_context_middleware import TenantContext
from cadence.service.settings_service import SettingsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/orgs/{org_id}/orchestrators", tags=["orchestrators"])


@router.post("/{instance_id}/load", status_code=status.HTTP_202_ACCEPTED)
async def load_orchestrator(
    instance_id: str,
    load_request: LoadOrchestratorRequest = None,
    request: Request = None,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Fire-and-forget: publish orchestrator.load event."""
    settings_service: SettingsService = request.app.state.settings_service

    try:
        instance = await settings_service.get_instance_config(instance_id)
        validate_orchestrator_access(instance, instance_id, context.org_id)

        tier = (load_request.tier if load_request else None) or instance.get(
            "tier", "hot"
        )

        event_publisher = getattr(request.app.state, "event_publisher", None)
        if event_publisher:
            await event_publisher.publish_load(
                instance_id=instance_id,
                org_id=context.org_id,
                tier=tier,
            )
        else:
            logger.warning("No event_publisher available — load event not published")

        return {"message": "Load event published", "instance_id": instance_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to publish load event for {instance_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to publish load event",
        )


@router.post("/{instance_id}/unload", status_code=status.HTTP_202_ACCEPTED)
async def unload_orchestrator(
    instance_id: str,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Fire-and-forget: publish orchestrator.unload event."""
    settings_service: SettingsService = request.app.state.settings_service

    try:
        instance = await settings_service.get_instance_config(instance_id)
        validate_orchestrator_access(instance, instance_id, context.org_id)

        event_publisher = getattr(request.app.state, "event_publisher", None)
        if event_publisher:
            await event_publisher.publish_unload(instance_id=instance_id)
        else:
            logger.warning("No event_publisher available — unload event not published")

        return {"message": "Unload event published", "instance_id": instance_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to publish unload event for {instance_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to publish unload event",
        )
