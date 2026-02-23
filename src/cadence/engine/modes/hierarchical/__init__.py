"""Hierarchical mode configuration.

In hierarchical mode, a top-level supervisor routes queries to team supervisors,
each of which manages its own subset of plugin agents.
"""

from typing import Any, Dict, List, Optional

from cadence.constants import Framework
from cadence.engine.modes.orchestrator_base import OrchestratorMode


class HierarchicalMode(OrchestratorMode):
    """Hierarchical orchestration mode configuration.

    A two-level supervisor hierarchy where a top router delegates to specialized
    team supervisors. Suitable for large plugin sets, domain isolation, and
    enterprise multi-team workflows.

    Configuration:
        teams: List of team definitions with name, plugins, and supervisor config (default: [])
        team_invocation: How teams are invoked — "sequential" or "parallel" (default: "sequential")
        max_teams_per_query: Maximum number of teams to invoke per query (default: 3)
        invoke_timeout: Timeout in seconds per team invocation (default: 120)
    """

    def __init__(self, framework: Framework, config: Optional[Dict[str, Any]] = None):
        """Initialize hierarchical mode configuration.

        Args:
            framework: Framework identifier
            config: Configuration dictionary
        """
        super().__init__(
            mode_name="hierarchical", framework=framework, config=config or {}
        )
        config = config or {}

        self.teams: List[Dict[str, Any]] = config.get("teams", [])
        self.team_invocation: str = config.get("team_invocation", "sequential")
        self.max_teams_per_query: int = config.get("max_teams_per_query", 3)
        self.invoke_timeout: int = config.get("invoke_timeout", 120)
