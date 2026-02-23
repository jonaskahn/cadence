"""Pydantic schemas and shared helpers for orchestrator management API."""

from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from pydantic import BaseModel, Field


class CreateOrchestratorRequest(BaseModel):
    """Create orchestrator instance request."""

    name: str = Field(
        ...,
        min_length=10,
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
        description="List of plugin IDs to activate.",
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


class GraphDefinitionResponse(BaseModel):
    """Graph visualization definition for a loaded orchestrator."""

    mermaid: Optional[str] = None
    is_ready: bool


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
    is_ready: bool = False
    created_at: str
    updated_at: str


class UpdateOrchestratorMetadataRequest(BaseModel):
    """Update orchestrator metadata (name, tier, default LLM config)."""

    name: Optional[str] = Field(None, min_length=10, max_length=200)
    tier: Optional[str] = Field(None, pattern="^(hot|warm|cold)$")
    default_llm_config_id: Optional[int] = None


def extract_llm_config_ids(config: dict) -> list[int]:
    """Extract all LLM config IDs from a config dict (top-level + per-node)."""
    llm_config_ids = []
    if config.get("default_llm_config_id"):
        llm_config_ids.append(int(config["default_llm_config_id"]))
    mode_config = config.get("mode_config", {})
    for node_key in [
        "classifier_node",
        "planner_node",
        "synthesizer_node",
        "validation_node",
        "clarifier_node",
        "responder_node",
        "error_handler_node",
    ]:
        node_config = mode_config.get(node_key, {})
        if isinstance(node_config, dict) and node_config.get("llm_config_id"):
            llm_config_ids.append(int(node_config["llm_config_id"]))
    return list(set(llm_config_ids))


def validate_orchestrator_access(
    instance: Optional[Dict],
    instance_id: str,
    org_id: str,
) -> None:
    """Validate instance exists, is not deleted, and belongs to org.

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
