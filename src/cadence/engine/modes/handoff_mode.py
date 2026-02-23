"""Handoff mode configuration.

In handoff mode, plugin agents work as peers and can transfer control to each other
directly without a central coordinator. Each agent has handoff tools to transfer
to other agents.
"""

from typing import Any, Dict, Optional

from cadence.engine.constants import DEFAULT_INVOKE_TIMEOUT, DEFAULT_MAX_HANDOFFS
from cadence.engine.modes.mode_base import OrchestratorMode


class HandoffMode(OrchestratorMode):
    """Handoff mode configuration.

    Attributes:
        entry_agent: Name of the agent to start with
        handoff_instructions: Instructions for when to hand off
        max_handoffs: Maximum number of handoffs allowed
        invoke_timeout: Timeout for agent invocation in seconds
        parallel_tool_calls: Allow parallel tool execution
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize handoff mode configuration.

        Args:
            config: Configuration dictionary
        """
        super().__init__(mode_name="handoff", config=config or {})
        config = config or {}

        self.entry_agent = config.get("entry_agent", "")
        self.handoff_instructions = config.get(
            "handoff_instructions",
            "Transfer to another agent when their expertise is needed",
        )
        self.max_handoffs = config.get("max_handoffs", DEFAULT_MAX_HANDOFFS)
        self.invoke_timeout = config.get("invoke_timeout", DEFAULT_INVOKE_TIMEOUT)
        self.parallel_tool_calls = config.get("parallel_tool_calls", False)

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary.

        Returns:
            Configuration as dict
        """
        return {
            "mode": self.mode_name,
            "entry_agent": self.entry_agent,
            "handoff_instructions": self.handoff_instructions,
            "max_handoffs": self.max_handoffs,
            "invoke_timeout": self.invoke_timeout,
            "parallel_tool_calls": self.parallel_tool_calls,
        }

    def validate(self) -> bool:
        """Validate configuration.

        Returns:
            True if valid

        Raises:
            ValueError: If configuration is invalid
        """
        if not self.entry_agent:
            raise ValueError("entry_agent must be specified for handoff mode")

        if self.max_handoffs < 1:
            raise ValueError("max_handoffs must be >= 1")

        if self.invoke_timeout < 1:
            raise ValueError("invoke_timeout must be >= 1")

        return True
