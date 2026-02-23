"""Supervisor mode specification.

In supervisor mode, a central supervisor agent has access to all plugin tools
and decides which tools to call based on user queries.
"""

from typing import TYPE_CHECKING, Any, Dict, Optional

from cadence.constants import Framework
from cadence.engine.modes.orchestrator_base import OrchestratorMode

if TYPE_CHECKING:
    pass


class SupervisorMode(OrchestratorMode):
    """Supervisor orchestration mode configuration.

    The supervisor has all plugin tools bound to a single model and decides
    which tools to call in response to user queries. Tool execution happens
    in a dedicated tool node, then control returns to the supervisor.

    Configuration:
        max_agent_hops: Maximum number of supervisor iterations (default: 10)
        enabled_parallel_tool_calls: Allow parallel tool execution (default: True)
        node_execution_timeout: Timeout in seconds for all node LLM/tool calls (default: 60)
        enabled_llm_validation: Use LLM to validate tool results (default: False)
        classifier_node / planner_node / synthesizer_node / validation_node /
        clarifier_node / responder_node / error_handler_node: Per-node NodeConfig overrides
    """

    def __init__(self, framework: Framework, config: Optional[Dict[str, Any]] = None):
        defaults: Dict[str, Any] = {
            "max_agent_hops": 10,
            "enabled_parallel_tool_calls": True,
            "node_execution_timeout": 60,
            "enabled_llm_validation": False,
            "enabled_auto_compact": False,
        }
        safe_config = {k: v for k, v in (config or {}).items() if v is not None}
        merged_config = {**defaults, **safe_config}
        super().__init__(
            mode_name="supervisor", framework=framework, config=merged_config
        )

        self.max_agent_hops: int = merged_config["max_agent_hops"]
        self.enabled_parallel_tool_calls: bool = merged_config[
            "enabled_parallel_tool_calls"
        ]
        self.node_execution_timeout: int = merged_config["node_execution_timeout"]
        self.enabled_llm_validation: bool = merged_config["enabled_llm_validation"]
        self.enabled_auto_compact: bool = merged_config["enabled_auto_compact"]

        if framework == Framework.LANGGRAPH:
            from cadence.engine.impl.langgraph.supervisor.settings import (
                LangGraphSupervisorSettings,
            )

            self.settings: Optional[LangGraphSupervisorSettings] = (
                LangGraphSupervisorSettings.model_validate(merged_config)
            )
        elif framework == Framework.GOOGLE_ADK:
            from cadence.engine.impl.google_adk.supervisor.settings import (
                GoogleADKSupervisorSettings,
            )

            self.settings = GoogleADKSupervisorSettings.model_validate(merged_config)
        else:
            self.settings = None
