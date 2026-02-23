"""Orchestrator instance CRUD API endpoints."""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status

from cadence.constants.framework import (
    FRAMEWORK_SUPPORTED_MODES,
    FRAMEWORK_SUPPORTED_PROVIDERS,
    Framework,
)
from cadence.controller.schemas.orchestrator_schemas import (
    CreateOrchestratorRequest,
    GraphDefinitionResponse,
    OrchestratorResponse,
    UpdateOrchestratorConfigRequest,
    UpdateOrchestratorMetadataRequest,
    UpdateOrchestratorStatusRequest,
    extract_llm_config_ids,
    validate_orchestrator_access,
)
from cadence.middleware.authorization_middleware import require_org_admin_access
from cadence.middleware.tenant_context_middleware import TenantContext
from cadence.service.settings_service import SettingsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/orgs/{org_id}/orchestrators", tags=["orchestrators"])


def _check_is_ready(pool, instance_id: str) -> bool:
    hot_tier = pool.hot_tier
    return instance_id in hot_tier and hot_tier[instance_id].is_ready


async def _validate_framework_mode(framework_type: str, mode: str) -> None:
    """Raise 422 if mode is not supported by framework."""
    try:
        framework = Framework(framework_type)
    except ValueError:
        return
    supported_modes = FRAMEWORK_SUPPORTED_MODES.get(framework, frozenset())
    if mode not in supported_modes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Mode '{mode}' is not supported by framework '{framework_type}'",
        )


async def _validate_llm_configs_for_framework(
    tenant_service, framework_type: str, config: dict
) -> None:
    """Raise 422 if any LLM config ID in config uses a provider incompatible with framework."""
    try:
        framework = Framework(framework_type)
    except ValueError:
        return
    supported_providers = FRAMEWORK_SUPPORTED_PROVIDERS.get(framework)
    if supported_providers is None:
        return
    for config_id in extract_llm_config_ids(config):
        llm_config = await tenant_service.get_llm_config_by_id(config_id)
        if not llm_config or getattr(llm_config, "is_deleted", False):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"LLM config {config_id} not found",
            )
        if llm_config.provider not in supported_providers:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"LLM config {config_id} uses provider '{llm_config.provider}' "
                    f"which is not supported by framework '{framework_type}'"
                ),
            )


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
    """Create new orchestrator instance."""
    settings_service: SettingsService = request.app.state.settings_service
    plugin_service = request.app.state.plugin_service
    event_publisher = getattr(request.app.state, "event_publisher", None)

    await _validate_framework_mode(create_request.framework_type, create_request.mode)
    tenant_service = request.app.state.tenant_service
    await _validate_llm_configs_for_framework(
        tenant_service, create_request.framework_type, create_request.config or {}
    )

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
    """List all orchestrator instances for this organization."""
    settings_service: SettingsService = request.app.state.settings_service
    pool = request.app.state.orchestrator_pool

    try:
        instances = await settings_service.list_instances_for_org(context.org_id)
        return [
            OrchestratorResponse(
                **instance, is_ready=_check_is_ready(pool, instance["instance_id"])
            )
            for instance in instances
        ]
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
    """Get orchestrator instance details."""
    settings_service: SettingsService = request.app.state.settings_service
    pool = request.app.state.orchestrator_pool

    try:
        instance = await settings_service.get_instance_config(instance_id)
        validate_orchestrator_access(instance, instance_id, context.org_id)
        return OrchestratorResponse(
            **instance, is_ready=_check_is_ready(pool, instance_id)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get orchestrator: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve orchestrator instance",
        )


@router.patch("/{instance_id}", response_model=OrchestratorResponse)
async def update_orchestrator_metadata(
    instance_id: str,
    update_request: UpdateOrchestratorMetadataRequest,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Update orchestrator name, tier, and/or default LLM config."""
    settings_service: SettingsService = request.app.state.settings_service

    try:
        if update_request.default_llm_config_id is not None:
            instance = await settings_service.get_instance_config(instance_id)
            validate_orchestrator_access(instance, instance_id, context.org_id)
            tenant_service = request.app.state.tenant_service
            await _validate_llm_configs_for_framework(
                tenant_service,
                instance["framework_type"],
                {"default_llm_config_id": update_request.default_llm_config_id},
            )
        updated = await settings_service.update_orchestrator_metadata(
            instance_id=instance_id,
            org_id=context.org_id,
            name=update_request.name,
            tier=update_request.tier,
            default_llm_config_id=update_request.default_llm_config_id,
            caller_id=context.user_id,
        )
        logger.info(f"Orchestrator {instance_id} metadata updated")
        return OrchestratorResponse(**updated)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to update orchestrator metadata: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update orchestrator metadata",
        )


@router.patch("/{instance_id}/config", response_model=OrchestratorResponse)
async def update_orchestrator_config(
    instance_id: str,
    update_request: UpdateOrchestratorConfigRequest,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Update orchestrator configuration."""
    settings_service: SettingsService = request.app.state.settings_service
    event_publisher = getattr(request.app.state, "event_publisher", None)

    try:
        instance = await settings_service.get_instance_config(instance_id)
        validate_orchestrator_access(instance, instance_id, context.org_id)
        tenant_service = request.app.state.tenant_service
        await _validate_llm_configs_for_framework(
            tenant_service, instance["framework_type"], update_request.config
        )
        updated = await settings_service.update_orchestrator_config(
            instance_id=instance_id,
            org_id=context.org_id,
            new_config=update_request.config,
            caller_id=context.user_id,
            event_publisher=event_publisher,
        )
        logger.info(f"Orchestrator {instance_id} configuration updated")
        return OrchestratorResponse(**updated)

    except HTTPException:
        raise
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
    """Update orchestrator status (active or suspended)."""
    settings_service: SettingsService = request.app.state.settings_service

    try:
        instance = await settings_service.get_instance_config(instance_id)
        validate_orchestrator_access(instance, instance_id, context.org_id)

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


@router.get("/{instance_id}/graph", response_model=GraphDefinitionResponse)
async def get_orchestrator_graph(
    instance_id: str,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Get graph visualization definition for a loaded orchestrator instance."""
    settings_service: SettingsService = request.app.state.settings_service
    pool = request.app.state.orchestrator_pool

    try:
        instance = await settings_service.get_instance_config(instance_id)
        validate_orchestrator_access(instance, instance_id, context.org_id)
    except HTTPException:
        raise

    try:
        orchestrator = await pool.get(instance_id)
        mermaid = (
            orchestrator.get_graph_mermaid()
            if hasattr(orchestrator, "get_graph_mermaid")
            else None
        )
        return GraphDefinitionResponse(mermaid=mermaid, is_ready=orchestrator.is_ready)
    except ValueError:
        return GraphDefinitionResponse(mermaid=None, is_ready=False)
    except Exception as e:
        logger.error(f"Failed to get graph for {instance_id}: {e}", exc_info=True)
        return GraphDefinitionResponse(mermaid=None, is_ready=False)


@router.delete("/{instance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_orchestrator(
    instance_id: str,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Soft-delete orchestrator instance."""
    settings_service: SettingsService = request.app.state.settings_service

    try:
        instance = await settings_service.get_instance_config(instance_id)
        validate_orchestrator_access(instance, instance_id, context.org_id)

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
