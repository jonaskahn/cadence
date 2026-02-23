"""Base orchestrator interfaces for all backends.

Exports BaseOrchestrator (abstract orchestrator contract) and OrchestratorAdapter
(converts SDK types to framework-native types). All LangGraph, OpenAI, and
Google ADK implementations extend these interfaces.
"""

from cadence.engine.base.adapter_base import OrchestratorAdapter
from cadence.engine.base.orchestrator_base import BaseOrchestrator
from cadence.infrastructure.streaming import StreamEvent

__all__ = ["OrchestratorAdapter", "BaseOrchestrator", "StreamEvent"]
