"""Pipeline mode configuration.

In pipeline mode, agents are arranged in fixed sequential stages where each
stage's output feeds into the next stage as input.
"""

from typing import Any, Dict, List, Optional

from cadence.constants import Framework
from cadence.engine.modes.orchestrator_base import OrchestratorMode


class PipelineMode(OrchestratorMode):
    """Pipeline orchestration mode configuration.

    Agents execute in a fixed sequential order. Each stage receives the
    output of the previous stage as its input context. Suitable for ETL
    workflows, compliance pipelines, and multi-step content production.

    Configuration:
        stages: Ordered list of stage definitions (default: [])
        pass_full_context: Pass full conversation history to each stage (default: True)
        invoke_timeout: Timeout in seconds per stage (default: 60)
        max_stage_retries: Maximum retry attempts per stage on failure (default: 1)
    """

    def __init__(self, framework: Framework, config: Optional[Dict[str, Any]] = None):
        """Initialize pipeline mode configuration.

        Args:
            framework: Framework identifier
            config: Configuration dictionary
        """
        super().__init__(mode_name="pipeline", framework=framework, config=config or {})
        config = config or {}

        self.stages: List[Dict[str, Any]] = config.get("stages", [])
        self.pass_full_context: bool = config.get("pass_full_context", True)
        self.invoke_timeout: int = config.get("invoke_timeout", 60)
        self.max_stage_retries: int = config.get("max_stage_retries", 1)
