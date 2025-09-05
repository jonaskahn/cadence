"""Core Business Logic and Multi-Agent Orchestration for Cadence Framework.

This package provides the central business logic for the Cadence multi-agent AI framework,
including intelligent conversation routing, state management, and multi-agent coordination
through LangGraph-based workflows with dynamic plugin integration.
"""

from cadence_sdk.types import AgentState, PluginContext, StateHelpers

from .orchestrator.coordinator import AgentCoordinator

__all__ = ["AgentState", "PluginContext", "StateHelpers", "AgentCoordinator"]
