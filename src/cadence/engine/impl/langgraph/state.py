"""State type for LangGraph orchestrators."""

from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Optional

from langchain_core.messages import AnyMessage
from typing_extensions import TypedDict


class MessageState(TypedDict, total=False):
    """LangGraph-specific state.

    This is the internal state that travels through the LangGraph graph.
    Conversion to/from UvState is handled by the adapter layer.

    Attributes:
        messages: List of LangChain message dicts (add_messages reducer)
        thread_id: Conversation thread identifier
        error_state: Error details set by the error_handler node
        validation_result: ValidationResponse data from the validation node
        used_plugins: Plugin names invoked this turn
        routing_decision: Ephemeral classifier output — "tools" | "conversational" | "clarify"
        tool_results: Ephemeral attributed results from executor node
    """

    messages: Annotated[list[AnyMessage], operator.add]
    thread_id: Optional[str]
    agent_hops: Optional[int]
    current_agent: Optional[str]
    error_state: Optional[Dict[str, Any]]
    validation_result: Optional[Dict[str, Any]]
    used_plugins: List[str]
    routing_decision: Optional[str]
    tool_results: Optional[List[Dict[str, Any]]]
