"""Coordinator mode configuration.

In coordinator mode, a central routing agent decides which plugin agent to invoke
based on the user query. The coordinator has routing tools to transfer control
to plugin agents or synthesize the final response.
"""

from typing import Any, Dict, Optional

from cadence.engine.constants import (
    DEFAULT_CONSECUTIVE_ROUTE_LIMIT,
    DEFAULT_INVOKE_TIMEOUT,
    DEFAULT_MAX_AGENT_HOPS,
)
from cadence.engine.modes.mode_base import OrchestratorMode


class CoordinatorMode(OrchestratorMode):
    """Coordinator mode configuration.

    Attributes:
        max_agent_hops: Maximum number of agent routing decisions
        consecutive_agent_route_limit: Max consecutive routes to same agent
        invoke_timeout: Timeout for agent invocation in seconds
        parallel_tool_calls: Allow parallel tool execution within agents
        allowed_coordinator_terminate: Allow coordinator to terminate early
    """

    def __init__(self, mode_name: str, config: Optional[Dict[str, Any]] = None):
        """Initialize coordinator mode configuration.

        Args:
            config: Configuration dictionary
        """
        super().__init__(mode_name, config)
        config = config or {}

        self.max_agent_hops = config.get("max_agent_hops", DEFAULT_MAX_AGENT_HOPS)
        self.consecutive_agent_route_limit = config.get(
            "consecutive_agent_route_limit", DEFAULT_CONSECUTIVE_ROUTE_LIMIT
        )
        self.invoke_timeout = config.get("invoke_timeout", DEFAULT_INVOKE_TIMEOUT)
        self.parallel_tool_calls = config.get("parallel_tool_calls", False)
        self.allowed_coordinator_terminate = config.get(
            "allowed_coordinator_terminate", True
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary.

        Returns:
            Configuration as dict
        """
        return {
            "mode": self.mode_name,
            "max_agent_hops": self.max_agent_hops,
            "consecutive_agent_route_limit": self.consecutive_agent_route_limit,
            "invoke_timeout": self.invoke_timeout,
            "parallel_tool_calls": self.parallel_tool_calls,
            "allowed_coordinator_terminate": self.allowed_coordinator_terminate,
        }

    def validate(self) -> bool:
        """Validate configuration.

        Returns:
            True if valid

        Raises:
            ValueError: If configuration is invalid
        """
        if self.max_agent_hops < 1:
            raise ValueError("max_agent_hops must be >= 1")

        if self.consecutive_agent_route_limit < 1:
            raise ValueError("consecutive_agent_route_limit must be >= 1")

        if self.invoke_timeout < 1:
            raise ValueError("invoke_timeout must be >= 1")

        return True
