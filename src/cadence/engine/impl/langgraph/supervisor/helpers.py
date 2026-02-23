"""Utility helpers for the LangGraph supervisor."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from typing_extensions import TypedDict

_TIMEOUT_FALLBACK_PREFIX = "FKR_"

_CLARIFICATION_TYPE_MESSAGES = {
    "insufficient_results": "Tool search returned no useful results.",
    "missing_parameters": "User intent is clear but required parameters are missing.",
    "low_relevance": "Tool results have low relevance to the user query.",
    "no_relevant_results": "No results match the user's intent.",
}


class ToolResult(TypedDict):
    tool_name: str
    plugin_id: str
    data: Any
    error: Optional[str]


def sanitize_messages(messages: List[BaseMessage]) -> List[BaseMessage]:
    """Strip AIMessages with unresolved tool_calls to prevent OpenAI 400 errors."""
    resolved_ids: set = {
        msg.tool_call_id for msg in messages if isinstance(msg, ToolMessage)
    }
    sanitized = []
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            tc_ids = {
                tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                for tc in msg.tool_calls
            }
            if not tc_ids.issubset(resolved_ids):
                if msg.content:
                    sanitized.append(AIMessage(content=msg.content))
                continue
        sanitized.append(msg)
    return sanitized


def extract_tool_results(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
    """Extract tool result dicts from the most recent ToolMessages."""
    results = []
    for msg in reversed(messages):
        if not isinstance(msg, ToolMessage):
            break
        try:
            data = json.loads(msg.content)
            if isinstance(data, dict):
                results.append(data)
        except (json.JSONDecodeError, TypeError):
            pass
    return results


def extract_last_human_query(messages: List[BaseMessage]) -> str:
    """Return the content of the most recent HumanMessage."""
    return next(
        (
            msg.content or ""
            for msg in reversed(messages)
            if isinstance(msg, HumanMessage)
        ),
        "",
    )


def build_clarification_context(clarification_types: List[str]) -> str:
    parts = []
    for clarification_type in (
        clarification_types
        if isinstance(clarification_types, list)
        else [clarification_types]
    ):
        parts.append(
            _CLARIFICATION_TYPE_MESSAGES.get(clarification_type, clarification_type)
        )
    return "\n".join(parts)


def build_clarifier_messages(
    messages: List[BaseMessage], additional_context: str
) -> List[BaseMessage]:
    """Trim message history to the last human message for the clarifier."""
    last_human_idx = next(
        (
            message_index
            for message_index in range(len(messages) - 1, -1, -1)
            if isinstance(messages[message_index], HumanMessage)
        ),
        -1,
    )
    if last_human_idx == -1:
        return []

    cleaned = list(messages[: last_human_idx + 1])
    if not additional_context:
        return cleaned

    caller_id = f"{_TIMEOUT_FALLBACK_PREFIX}{uuid.uuid4().hex[:20]}"
    cleaned.append(
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "clarify_reason",
                    "args": {"reason": additional_context},
                    "id": caller_id,
                    "type": "tool_call",
                }
            ],
        )
    )
    cleaned.append(ToolMessage(content=additional_context, tool_call_id=caller_id))
    return cleaned


def build_error_state(
    state: Any, exception: Exception, node_name: str
) -> Dict[str, Any]:
    """Build a state update that flags an error for the error_handler."""
    error_lower = str(exception).lower()
    if any(error_keyword in error_lower for error_keyword in ("rate", "429", "quota")):
        error_type = "RateLimitError"
    elif any(
        error_keyword in error_lower for error_keyword in ("timeout", "timed out")
    ):
        error_type = "TimeoutError"
    elif any(error_keyword in error_lower for error_keyword in ("tool", "plugin")):
        error_type = "ToolError"
    else:
        error_type = "SystemError"

    return {
        "error_state": {
            "node": node_name,
            "error_type": error_type,
            "error_message": str(exception),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    }
