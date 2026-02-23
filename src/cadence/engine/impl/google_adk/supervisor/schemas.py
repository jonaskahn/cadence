"""Data models and session state key constants for the ADK supervisor pipeline."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class RoutingDecision(BaseModel):
    """Structured output from the router node."""

    route: Literal["tools", "conversational", "clarify"]


class ValidationResponse(BaseModel):
    """Structured validation result from the validation node."""

    is_valid: bool = Field(description="Whether validation passed")
    valid_plugin_resources: str = Field(
        default="", description="Comma-separated list of valid plugin resource names"
    )
    valid_ids: Optional[List[str]] = Field(
        default=None, description="IDs of results that passed validation"
    )
    clarification_type: List[str] = Field(
        default_factory=list,
        description="Clarification types needed when invalid",
    )
    reasoning: str = Field(description="Explanation of the validation decision")
    query_intent: str = Field(default="", description="User's query intent")


class SessionKeys:
    """Typed constants for all session.state keys used in the pipeline."""

    USER_QUERY = "user_query"
    TOOL_RESULTS = "tool_results"
    TOOL_CONTEXT_TEXT = "tool_context_text"
    ROUTING_DECISION = "routing_decision"
    VALIDATION_RESULT = "validation_result"
    ADDITIONAL_CONTEXT = "additional_context"
    ERROR_STATE = "error_state"
    PLUGIN_DESCRIPTIONS = "plugin_descriptions"
    TOOL_DESCRIPTIONS = "tool_descriptions"
    CURRENT_TIME = "current_time"
    MAX_AGENT_HOPS = "max_agent_hops"
