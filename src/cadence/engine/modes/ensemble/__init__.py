"""Ensemble mode configuration.

In ensemble mode, multiple agents solve the same query in parallel and a
merger synthesizes the best combined answer from all responses.
"""

from typing import Any, Dict, List, Optional

from cadence.constants import Framework
from cadence.engine.modes.orchestrator_base import OrchestratorMode


class EnsembleMode(OrchestratorMode):
    """Ensemble orchestration mode configuration.

    N agents run in parallel on the same query and a merger synthesizes
    their outputs. Suitable for fact-sensitive QA, multi-perspective analysis,
    and queries with ambiguous intent.

    Configuration:
        num_agents: Number of parallel agents to spawn (default: 3)
        agent_configs: Per-agent configuration overrides (default: [])
        synthesis_strategy: How to merge agent outputs — "best", "union", "vote" (default: "best")
        invoke_timeout: Timeout in seconds per agent (default: 60)
        parallel_timeout: Total timeout in seconds for parallel execution (default: 120)
    """

    def __init__(self, framework: Framework, config: Optional[Dict[str, Any]] = None):
        """Initialize ensemble mode configuration.

        Args:
            framework: Framework identifier
            config: Configuration dictionary
        """
        super().__init__(mode_name="ensemble", framework=framework, config=config or {})
        config = config or {}

        self.num_agents: int = config.get("num_agents", 3)
        self.agent_configs: List[Dict[str, Any]] = config.get("agent_configs", [])
        self.synthesis_strategy: str = config.get("synthesis_strategy", "best")
        self.invoke_timeout: int = config.get("invoke_timeout", 60)
        self.parallel_timeout: int = config.get("parallel_timeout", 120)
