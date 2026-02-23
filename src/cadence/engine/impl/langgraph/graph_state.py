"""Shared types and utilities for LangGraph graph builders."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sdk.src.cadence_sdk import UvState


class GraphState(UvState):
    """State type for LangGraph v1.0+.

    Attributes:
        messages: List of messages with add_messages reducer (v1.0+ pattern)
        agent_hops: Number of agent iterations
        current_agent: Current agent name
        error_state: Error details for error_handler node
        validation_result: ValidationResponse data from validation node
        used_plugins: Plugins invoked this turn
        route_to_facilitator: Supervisor detected unclear intent
        route_to_conversational: Supervisor detected context-only query
    """

    error_state: Optional[Dict[str, Any]]
    validation_result: Optional[Dict[str, Any]]
    used_plugins: List[str]
    route_to_facilitator: bool
    route_to_conversational: bool
