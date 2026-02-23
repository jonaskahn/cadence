"""Per-node LLM and prompt configuration for the Google ADK supervisor."""

from __future__ import annotations

from cadence.engine.impl.langgraph.supervisor.settings import BaseSupervisorSettings

__all__ = ["GoogleADKSupervisorSettings"]


class GoogleADKSupervisorSettings(BaseSupervisorSettings):
    """Typed settings schema for the Google ADK supervisor orchestrator."""

    max_validation_iterations: int = 3
