"""Orchestrator instance management API endpoints.

Provides CRUD endpoints for managing orchestrator instances including
creation with tier support, configuration updates, load/unload, and
plugin settings management.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from cadence.middleware.authorization_middleware import require_org_admin_access
from cadence.middleware.tenant_context_middleware import TenantContext
from cadence.service.settings_service import SettingsService

logger = logging.getLogger(__name__)


def _validate_orchestrator_access(
    instance: Optional[Dict],
    instance_id: str,
    org_id: str,
) -> None:
    """Validate instance exists, is not deleted, and belongs to org.

    Args:
        instance: Instance dict from settings service, or None if not found
        instance_id: Instance ID for error messages
        org_id: Organization ID that must own the instance

    Raises:
        HTTPException: 404 if not found, 410 if deleted, 403 if wrong org
    """
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Instance {instance_id} not found",
        )
    if instance["status"] == "is_deleted":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=f"Instance {instance_id} has been deleted",
        )
    if instance["org_id"] != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this instance",
        )


router = APIRouter(prefix="/api/orgs/{org_id}/orchestrators", tags=["orchestrators"])

engine_router = APIRouter(prefix="/api/engine", tags=["engine"])


@engine_router.get("/supervisor/prompts")
async def get_supervisor_default_prompts() -> Dict[str, str]:
    """Return default prompt templates for each supervisor node."""
    from cadence.engine.impl.langgraph.supervisor.prompts import SupervisorPrompts

    return {
        "supervisor_node": SupervisorPrompts.SUPERVISOR,
        "synthesizer_node": SupervisorPrompts.SYNTHESIZER,
        "validation_node": SupervisorPrompts.VALIDATION,
        "facilitator_node": SupervisorPrompts.FACILITATOR,
        "conversational_node": SupervisorPrompts.CONVERSATIONAL,
        "error_handler_node": SupervisorPrompts.ERROR_HANDLER,
    }


class CreateOrchestratorRequest(BaseModel):
    """Create orchestrator instance request."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Instance name",
    )
    framework_type: str = Field(
        ...,
        pattern="^(langgraph|openai_agents|google_adk)$",
        description="Orchestration framework — immutable after creation",
    )
    mode: str = Field(
        ...,
        pattern="^(supervisor|coordinator|handoff)$",
        description="Orchestration mode — immutable after creation",
    )
    active_plugin_ids: List[str] = Field(
        ...,
        min_length=1,
        description=("List of plugin IDs to activate."),
    )
    tier: str = Field(
        default="cold",
        pattern="^(hot|warm|cold)$",
        description="Pool tier — hot instances are loaded immediately",
    )
    config: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Mutable instance-specific configuration (Tier 4 settings)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "customer-support",
                "framework_type": "langgraph",
                "mode": "supervisor",
                "active_plugin_ids": ["00000000-0000-0000-0000-000000000001"],
                "tier": "cold",
                "config": {
                    "default_llm_config_id": 1,
                    "mode_config": {
                        "max_agent_hops": 10,
                        "parallel_tool_calls": True,
                        "invoke_timeout": 60,
                        "supervisor_timeout": 60,
                        "use_llm_validation": False,
                    },
                },
            }
        }


class UpdateOrchestratorConfigRequest(BaseModel):
    """Update orchestrator configuration request."""

    config: Dict[str, Any] = Field(..., description="New mutable configuration")


class UpdateOrchestratorStatusRequest(BaseModel):
    """Update orchestrator status request."""

    status: str = Field(
        ...,
        pattern="^(active|suspended)$",
        description="New status — use DELETE endpoint for soft-delete",
    )


class LoadOrchestratorRequest(BaseModel):
    """Manual load orchestrator request."""

    tier: str = Field(
        default="hot",
        pattern="^(hot|warm|cold)$",
        description="Target tier for loading",
    )


class UpdatePluginSettingsRequest(BaseModel):
    """Partial update of plugin settings."""

    plugin_settings: Dict[str, Any] = Field(
        ...,
        description="Map of pid -> {id, name, settings: [{key, name, value}]} to merge into existing plugin_settings",
    )


class ActivatePluginVersionRequest(BaseModel):
    """Activate a specific plugin version on an orchestrator instance."""

    pid: str = Field(
        ..., description="Plugin identifier (reverse-domain, e.g. com.example.search)"
    )
    version: str = Field(..., description="Plugin version to activate (e.g. 2.0.0)")


class OrchestratorResponse(BaseModel):
    """Orchestrator instance response."""

    instance_id: str
    org_id: str
    name: str
    framework_type: str
    mode: str
    status: str
    config: Dict[str, Any]
    tier: str = "cold"
    plugin_settings: Dict[str, Any] = {}
    config_hash: Optional[str] = None
    created_at: str
    updated_at: str


@router.post(
    "",
    response_model=OrchestratorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Orchestrator Instance",
)
async def create_orchestrator(
    create_request: CreateOrchestratorRequest,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Create new orchestrator instance.

    Builds plugin_settings from catalog defaults and computes config_hash.
    If tier='hot', publishes a load event to RabbitMQ.

    Args:
        create_request: Instance configuration including name, framework_type, mode, plugins, and tier
        request: FastAPI request
        context: org_admin or sys_admin context

    Returns:
        Created orchestrator instance

    Raises:
        HTTPException: 500 if creation fails
    """
    settings_service: SettingsService = request.app.state.settings_service
    plugin_service = request.app.state.plugin_service
    event_publisher = getattr(request.app.state, "event_publisher", None)

    try:
        created_instance = await settings_service.create_orchestrator_instance(
            org_id=context.org_id,
            framework_type=create_request.framework_type,
            mode=create_request.mode,
            active_plugin_ids=create_request.active_plugin_ids,
            tier=create_request.tier,
            name=create_request.name,
            extra_config=create_request.config,
            plugin_service=plugin_service,
            caller_id=context.user_id,
            event_publisher=event_publisher,
        )
        return OrchestratorResponse(**created_instance)

    except Exception as e:
        logger.error(f"Failed to create orchestrator: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create orchestrator instance",
        )


@router.get("", response_model=List[OrchestratorResponse])
async def list_orchestrators(
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """List all orchestrator instances for this organization.

    Args:
        request: FastAPI request
        context: org_admin or sys_admin context

    Returns:
        List of orchestrator instances

    Raises:
        HTTPException: 500 if retrieval fails
    """
    settings_service: SettingsService = request.app.state.settings_service

    try:
        instances = await settings_service.list_instances_for_org(context.org_id)
        return [OrchestratorResponse(**instance) for instance in instances]
    except Exception as e:
        logger.error(f"Failed to list orchestrators: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list orchestrator instances",
        )


@router.get("/{instance_id}", response_model=OrchestratorResponse)
async def get_orchestrator(
    instance_id: str,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Get orchestrator instance details.

    Args:
        instance_id: Instance identifier
        request: FastAPI request
        context: org_admin or sys_admin context

    Returns:
        Orchestrator instance details

    Raises:
        HTTPException: 403 if access denied, 404 if not found, 410 if deleted, 500 on failure
    """
    settings_service: SettingsService = request.app.state.settings_service

    try:
        instance = await settings_service.get_instance_config(instance_id)
        _validate_orchestrator_access(instance, instance_id, context.org_id)

        return OrchestratorResponse(**instance)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get orchestrator: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve orchestrator instance",
        )


@router.patch("/{instance_id}/config", response_model=OrchestratorResponse)
async def update_orchestrator_config(
    instance_id: str,
    update_request: UpdateOrchestratorConfigRequest,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Update orchestrator configuration.

    Recomputes config_hash and publishes orchestrator.reload event.

    Args:
        instance_id: Instance identifier
        update_request: New configuration dict
        request: FastAPI request
        context: org_admin or sys_admin context

    Returns:
        Updated orchestrator instance

    Raises:
        HTTPException: 422 if config is invalid, 500 on failure
    """
    settings_service: SettingsService = request.app.state.settings_service
    event_publisher = getattr(request.app.state, "event_publisher", None)

    try:
        updated = await settings_service.update_orchestrator_config(
            instance_id=instance_id,
            org_id=context.org_id,
            new_config=update_request.config,
            caller_id=context.user_id,
            event_publisher=event_publisher,
        )
        logger.info(f"Orchestrator {instance_id} configuration updated")
        return OrchestratorResponse(**updated)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to update orchestrator config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update orchestrator configuration",
        )


@router.patch("/{instance_id}/status", response_model=OrchestratorResponse)
async def update_orchestrator_status(
    instance_id: str,
    status_request: UpdateOrchestratorStatusRequest,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Update orchestrator status (active or suspended).

    Args:
        instance_id: Instance identifier
        status_request: New status value
        request: FastAPI request
        context: org_admin or sys_admin context

    Returns:
        Updated orchestrator instance

    Raises:
        HTTPException: 403 if access denied, 404 if not found, 410 if deleted, 500 on failure
    """
    settings_service: SettingsService = request.app.state.settings_service

    try:
        instance = await settings_service.get_instance_config(instance_id)
        _validate_orchestrator_access(instance, instance_id, context.org_id)

        updated = await settings_service.update_instance_status(
            instance_id, status_request.status, caller_id=context.user_id
        )

        logger.info(
            f"Orchestrator {instance_id} status updated to {status_request.status}"
        )
        return OrchestratorResponse(**updated)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update orchestrator status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update orchestrator status",
        )


@router.delete("/{instance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_orchestrator(
    instance_id: str,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Soft-delete orchestrator instance (sets status to 'deleted').

    Args:
        instance_id: Instance identifier
        request: FastAPI request
        context: org_admin or sys_admin context

    Raises:
        HTTPException: 403 if access denied, 404 if not found, 410 if already deleted, 500 on failure
    """
    settings_service: SettingsService = request.app.state.settings_service

    try:
        instance = await settings_service.get_instance_config(instance_id)
        _validate_orchestrator_access(instance, instance_id, context.org_id)

        await settings_service.delete_instance(instance_id)
        logger.info(f"Orchestrator {instance_id} soft-deleted")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete orchestrator: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete orchestrator instance",
        )


@router.post("/{instance_id}/load", status_code=status.HTTP_202_ACCEPTED)
async def load_orchestrator(
    instance_id: str,
    load_request: LoadOrchestratorRequest = None,
    request: Request = None,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Fire-and-forget: publish orchestrator.load event.

    Args:
        instance_id: Instance ID
        load_request: Optional load parameters (tier)
        request: FastAPI request
        context: Tenant context from JWT

    Returns:
        202 Accepted
    """
    settings_service: SettingsService = request.app.state.settings_service

    try:
        instance = await settings_service.get_instance_config(instance_id)
        _validate_orchestrator_access(instance, instance_id, context.org_id)

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
    """Fire-and-forget: publish orchestrator.unload event.

    Args:
        instance_id: Instance ID
        request: FastAPI request
        context: Tenant context from JWT

    Returns:
        202 Accepted
    """
    settings_service: SettingsService = request.app.state.settings_service

    try:
        instance = await settings_service.get_instance_config(instance_id)
        _validate_orchestrator_access(instance, instance_id, context.org_id)

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


@router.patch("/{instance_id}/plugin-settings", response_model=OrchestratorResponse)
async def update_plugin_settings(
    instance_id: str,
    update_request: UpdatePluginSettingsRequest,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Partial update of plugin settings (merge into existing).

    Recomputes config_hash and publishes reload event if instance is hot.

    Args:
        instance_id: Instance identifier
        update_request: Plugin settings override map (pid -> {key: value})
        request: FastAPI request
        context: org_admin or sys_admin context

    Returns:
        Updated orchestrator instance

    Raises:
        HTTPException: 422 if settings are invalid, 500 on failure
    """
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
    """Re-fetch latest default_settings for all active plugins and overwrite plugin_settings.

    User customizations are lost. Recomputes config_hash and publishes reload if hot.

    Args:
        instance_id: Instance identifier
        request: FastAPI request
        context: org_admin or sys_admin context

    Returns:
        Updated orchestrator instance with synced plugin settings

    Raises:
        HTTPException: 422 if sync fails validation, 500 on failure
    """
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
    """Activate a specific plugin version on an orchestrator instance.

    If the target version has no existing settings entry, settings are
    auto-migrated from the currently active version: matching keys are
    copied, new keys are set to catalog defaults, removed keys are omitted.

    If the instance is hot-tier, a reload event is published.

    Args:
        instance_id: Instance identifier
        activate_request: Plugin PID and target version
        request: FastAPI request
        context: org_admin or sys_admin context

    Returns:
        Updated orchestrator instance

    Raises:
        HTTPException: 422 if validation fails, 500 on failure
    """
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
