"""OpenAI Agents SDK orchestrator backend.

This package provides OpenAI Agents SDK integration for all orchestration modes:
supervisor, coordinator, handoff, pipeline, reflection, ensemble, and hierarchical.
"""

from cadence.engine.impl.openai_agents.adapter import OpenAIAgentsAdapter
from cadence.engine.impl.openai_agents.coordinator import OpenAICoordinator
from cadence.engine.impl.openai_agents.ensemble import OpenAIEnsemble
from cadence.engine.impl.openai_agents.handoff import OpenAIHandoff
from cadence.engine.impl.openai_agents.hierarchical import OpenAIHierarchical
from cadence.engine.impl.openai_agents.pipeline import OpenAIPipeline
from cadence.engine.impl.openai_agents.reflection import OpenAIReflection
from cadence.engine.impl.openai_agents.streaming import OpenAIAgentsStreamingWrapper
from cadence.engine.impl.openai_agents.supervisor import OpenAISupervisor

__all__ = [
    "OpenAIAgentsAdapter",
    "OpenAIAgentsStreamingWrapper",
    "OpenAICoordinator",
    "OpenAIEnsemble",
    "OpenAIHandoff",
    "OpenAIHierarchical",
    "OpenAIPipeline",
    "OpenAIReflection",
    "OpenAISupervisor",
]
