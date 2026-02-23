"""Supervisor mode specification.

In supervisor mode, a central supervisor agent has access to all plugin tools
and decides which tools to call based on user queries.
"""

from typing import TYPE_CHECKING, Any, Dict, Optional

from cadence.engine.modes.mode_base import OrchestratorMode

if TYPE_CHECKING:
    pass


class SupervisorMode(OrchestratorMode):
    """Supervisor orchestration mode configuration.

    The supervisor has all plugin tools bound to a single model and decides
    which tools to call in response to user queries. Tool execution happens
    in a dedicated tool node, then control returns to the supervisor.

    Configuration:
        max_agent_hops: Maximum number of supervisor iterations (default: 10)
        parallel_tool_calls: Allow parallel tool execution (default: True)
        invoke_timeout: Timeout in seconds for tool execution (default: 60)
        use_llm_validation: Use LLM to validate tool results (default: False)
        enable_synthesizer: Use synthesizer for final response (default: True)
        enable_facilitator: Route to facilitator when intent unclear (default: True)
        enable_conversational: Route to conversational for context queries (default: True)
        supervisor_timeout: Timeout in seconds for supervisor LLM call (default: 60)
        supervisor_node / synthesizer_node / validation_node / facilitator_node /
        conversational_node / error_handler_node: Per-node NodeConfig overrides
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # Local import breaks the circular dependency:
        # supervisor_mode → supervisor.settings → supervisor/__init__ → core → modes → supervisor_mode
        from cadence.engine.impl.langgraph.supervisor.settings import (
            LangGraphSupervisorSettings,
        )

        defaults: Dict[str, Any] = {
            "max_agent_hops": 10,
            "parallel_tool_calls": True,
            "invoke_timeout": 60,
            "use_llm_validation": False,
            "supervisor_timeout": 60,
        }
        merged_config = {**defaults, **(config or {})}
        super().__init__(mode_name="supervisor", config=merged_config)
        self.settings: LangGraphSupervisorSettings = (
            LangGraphSupervisorSettings.model_validate(merged_config)
        )

    @property
    def max_agent_hops(self) -> int:
        return self.settings.max_agent_hops

    @property
    def parallel_tool_calls(self) -> bool:
        return self.settings.parallel_tool_calls

    @property
    def invoke_timeout(self) -> int:
        return self.settings.invoke_timeout

    @property
    def use_llm_validation(self) -> bool:
        return self.settings.use_llm_validation

    @property
    def supervisor_timeout(self) -> int:
        return self.settings.supervisor_timeout
