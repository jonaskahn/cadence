"""OpenAI Agents SDK orchestrator backend.

This package provides OpenAI Agents SDK integration for all three orchestration modes:
supervisor, coordinator, and handoff.
"""

from cadence.engine.impl.openai_agents.adapter import OpenAIAgentsAdapter
from cadence.engine.impl.openai_agents.coordinator import OpenAICoordinator
from cadence.engine.impl.openai_agents.handoff import OpenAIHandoff
from cadence.engine.impl.openai_agents.streaming import OpenAIAgentsStreamingWrapper
from cadence.engine.impl.openai_agents.supervisor import OpenAISupervisor

__all__ = [
    "OpenAIAgentsAdapter",
    "OpenAIAgentsStreamingWrapper",
    "OpenAICoordinator",
    "OpenAIHandoff",
    "OpenAISupervisor",
]
