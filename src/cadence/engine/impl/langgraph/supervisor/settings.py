"""Per-node LLM and prompt configuration for the LangGraph supervisor."""

from __future__ import annotations

from pydantic import BaseModel, Field

from cadence.engine.base.supervisor_node_config import SupervisorModeNodeConfig

__all__ = [
    "SupervisorModeNodeConfig",
    "BaseSupervisorSettings",
    "LangGraphSupervisorSettings",
]

# Re-export for backward compatibility
NodeConfig = SupervisorModeNodeConfig


class BaseSupervisorSettings(BaseModel):
    """Shared settings for all supervisor orchestrators."""

    max_agent_hops: int = 10
    enabled_parallel_tool_calls: bool = True
    node_execution_timeout: int = 60
    enabled_llm_validation: bool = False
    message_context_window: int = 5
    max_context_window: int = 16_000
    enabled_auto_compact: bool = False
    autocompact: SupervisorModeNodeConfig = Field(
        default_factory=SupervisorModeNodeConfig
    )

    classifier_node: SupervisorModeNodeConfig = Field(
        default_factory=SupervisorModeNodeConfig
    )
    planner_node: SupervisorModeNodeConfig = Field(
        default_factory=SupervisorModeNodeConfig
    )
    synthesizer_node: SupervisorModeNodeConfig = Field(
        default_factory=SupervisorModeNodeConfig
    )
    validation_node: SupervisorModeNodeConfig = Field(
        default_factory=SupervisorModeNodeConfig
    )
    clarifier_node: SupervisorModeNodeConfig = Field(
        default_factory=SupervisorModeNodeConfig
    )
    responder_node: SupervisorModeNodeConfig = Field(
        default_factory=SupervisorModeNodeConfig
    )
    error_handler_node: SupervisorModeNodeConfig = Field(
        default_factory=SupervisorModeNodeConfig
    )


class LangGraphSupervisorSettings(BaseSupervisorSettings):
    """Typed settings schema for the LangGraph supervisor orchestrator."""
