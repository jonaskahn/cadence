"""Per-node LLM and prompt configuration for the LangGraph supervisor."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class NodeConfig(BaseModel):
    """Configuration for a single supervisor node.

    Attributes:
        llm_config_id: FK → OrganizationLLMConfig.id (must belong to same org).
            If None, falls back to the instance-level default_llm_config_id.
        prompt_override: Replaces the default SupervisorPrompts constant for this
            node. Must contain the same {placeholder} slots as the default prompt.
    """

    llm_config_id: Optional[int] = None
    model_name: Optional[str] = None
    prompt_override: Optional[str] = None


class LangGraphSupervisorSettings(BaseModel):
    """Typed settings schema for the LangGraph supervisor orchestrator.

    Scalar fields mirror the legacy SupervisorMode defaults. Per-node configs
    allow independent LLM selection and prompt overrides for each node in the
    7-node supervisor workflow.
    """

    # Behaviour
    max_agent_hops: int = 10
    parallel_tool_calls: bool = True
    invoke_timeout: int = 60
    use_llm_validation: bool = False
    supervisor_timeout: int = 60

    # Per-node configs (all default to no override → fall back to instance default)
    supervisor_node: NodeConfig = Field(default_factory=NodeConfig)
    synthesizer_node: NodeConfig = Field(default_factory=NodeConfig)
    validation_node: NodeConfig = Field(default_factory=NodeConfig)
    facilitator_node: NodeConfig = Field(default_factory=NodeConfig)
    conversational_node: NodeConfig = Field(default_factory=NodeConfig)
    error_handler_node: NodeConfig = Field(default_factory=NodeConfig)
