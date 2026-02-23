"""Reflection mode configuration.

In reflection mode, a generator agent produces an answer and a critic agent
evaluates it. The generator then revises based on feedback, iterating until
quality criteria are met or the iteration limit is reached.
"""

from typing import Any, Dict, List, Optional

from cadence.constants import Framework
from cadence.engine.modes.orchestrator_base import OrchestratorMode


class ReflectionMode(OrchestratorMode):
    """Reflection orchestration mode configuration.

    A generator-critic loop where the generator produces output and the critic
    evaluates it. Suitable for high-stakes documents, quality-gated content,
    and code review workflows.

    Configuration:
        max_iterations: Maximum generator-critic cycles (default: 3)
        approval_threshold: Minimum critic score to accept output (default: 0.8)
        critique_criteria: List of evaluation criteria for the critic (default: [])
        use_tools: Allow generator to use plugin tools (default: True)
        invoke_timeout: Timeout in seconds per agent call (default: 60)
    """

    def __init__(self, framework: Framework, config: Optional[Dict[str, Any]] = None):
        """Initialize reflection mode configuration.

        Args:
            framework: Framework identifier
            config: Configuration dictionary
        """
        super().__init__(
            mode_name="reflection", framework=framework, config=config or {}
        )
        config = config or {}

        self.max_iterations: int = config.get("max_iterations", 3)
        self.approval_threshold: float = config.get("approval_threshold", 0.8)
        self.critique_criteria: List[str] = config.get("critique_criteria", [])
        self.use_tools: bool = config.get("use_tools", True)
        self.invoke_timeout: int = config.get("invoke_timeout", 60)
