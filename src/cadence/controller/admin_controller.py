"""Administrative API endpoints.

This module provides admin-only endpoints for global settings management,
system health monitoring, and orchestrator pool statistics.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from cadence.middleware.authorization_middleware import require_sys_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


class GlobalSettingResponse(BaseModel):
    """Global setting response (Tier 2).

    Attributes:
        key: Setting key
        value: Setting value
        value_type: Value type
        description: Setting description
    """

    key: str
    value: Any
    value_type: str
    description: str


class UpdateGlobalSettingRequest(BaseModel):
    """Update global setting request.

    Attributes:
        value: New value
    """

    value: Any = Field(..., description="New setting value")


class HealthCheckResponse(BaseModel):
    """Health check response for single instance.

    Attributes:
        instance_id: Instance ID
        framework_type: Framework type
        mode: Orchestration mode
        is_ready: Whether instance is ready
        plugin_count: Number of active plugins
        plugins: List of plugin names
    """

    instance_id: str
    framework_type: str
    mode: str
    is_ready: bool
    plugin_count: int
    plugins: list[str]


class PoolStatsResponse(BaseModel):
    """Orchestrator pool statistics response.

    Attributes:
        total_instances: Total instances in pool
        hot_tier_count: Instances in Hot tier
        warm_tier_count: Instances in Warm tier
        cold_tier_count: Instances in Cold tier
        shared_model_count: Shared model instances
        shared_bundle_count: Shared plugin bundles
        memory_estimate_mb: Estimated memory usage
    """

    total_instances: int
    hot_tier_count: int
    warm_tier_count: int = 0
    cold_tier_count: int = 0
    shared_model_count: int = 0
    shared_bundle_count: int = 0
    memory_estimate_mb: float


@router.get(
    path="/settings",
    response_model=list[GlobalSettingResponse],
    dependencies=[Depends(require_sys_admin)],
)
async def list_global_settings(request: Request):
    """List all global settings (Tier 2).

    Args:
        request: FastAPI request

    Returns:
        List of global settings

    Raises:
        HTTPException: If operation fails
    """
    settings_service = request.app.state.settings_service

    try:
        settings = await settings_service.list_global_settings()
        return [GlobalSettingResponse(**s) for s in settings]

    except Exception as e:
        logger.error(f"Failed to list global settings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list global settings",
        )


@router.patch(
    "/settings/{key}",
    response_model=GlobalSettingResponse,
    dependencies=[Depends(require_sys_admin)],
)
async def update_global_setting(
    key: str, update_request: UpdateGlobalSettingRequest, request: Request
):
    """Update global setting (Tier 2).

    Args:
        key: Setting key
        update_request: New value
        request: FastAPI request

    Returns:
        Updated setting

    Raises:
        HTTPException: If operation fails
    """
    settings_service = request.app.state.settings_service

    try:
        setting = await settings_service.update_global_setting(
            key=key,
            value=update_request.value,
        )

        if not setting:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Setting {key} not found",
            )

        event_publisher = getattr(request.app.state, "event_publisher", None)
        if event_publisher is not None:
            try:
                await event_publisher.publish_global_settings_changed()
            except Exception as pub_err:
                logger.warning(
                    f"Failed to publish global settings changed event: {pub_err}"
                )

        return GlobalSettingResponse(**setting)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update global setting: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update global setting",
        )


@router.get(
    "/health",
    response_model=list[HealthCheckResponse],
    dependencies=[Depends(require_sys_admin)],
)
async def health_check_all(request: Request):
    """Health check for all orchestrator instances.

    Args:
        request: FastAPI request

    Returns:
        List of instance health statuses

    Raises:
        HTTPException: If operation fails
    """
    orchestrator_pool = request.app.state.orchestrator_pool

    try:
        health_results = await orchestrator_pool.health_check_all()

        return [
            HealthCheckResponse(
                instance_id=instance_id,
                framework_type=health.get("framework_type", "unknown"),
                mode=health.get("mode", "unknown"),
                is_ready=health.get("is_ready", False),
                plugin_count=health.get("plugin_count", 0),
                plugins=health.get("plugins", []),
            )
            for instance_id, health in health_results.items()
        ]

    except Exception as e:
        logger.error(f"Failed to perform health check: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to perform health check",
        )


@router.get(
    "/pool/stats",
    response_model=PoolStatsResponse,
    dependencies=[Depends(require_sys_admin)],
)
async def get_pool_stats(request: Request):
    """Get orchestrator pool statistics.

    Args:
        request: FastAPI request

    Returns:
        Pool statistics

    Raises:
        HTTPException: If operation fails
    """
    orchestrator_pool = request.app.state.orchestrator_pool

    try:
        stats = orchestrator_pool.get_stats()

        return PoolStatsResponse(
            total_instances=stats.get("total_instances", 0),
            hot_tier_count=stats.get("hot_tier_count", 0),
            warm_tier_count=stats.get("warm_tier_count", 0),
            cold_tier_count=stats.get("cold_tier_count", 0),
            shared_model_count=stats.get("shared_model_count", 0),
            shared_bundle_count=stats.get("shared_bundle_count", 0),
            memory_estimate_mb=stats.get("memory_estimate_mb", 0.0),
        )

    except Exception as e:
        logger.error(f"Failed to get pool stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve pool statistics",
        )
