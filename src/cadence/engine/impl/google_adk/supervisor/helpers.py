"""Utility helpers for the Google ADK supervisor."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_CLARIFICATION_TYPE_MESSAGES = {
    "insufficient_results": "Tool search returned no useful results.",
    "missing_parameters": "User intent is clear but required parameters are missing.",
    "low_relevance": "Tool results have low relevance to the user query.",
    "no_relevant_results": "No results match the user's intent.",
}


def extract_tool_results_from_events(
    events: List[Any],
    tool_to_plugin_map: Dict[str, str],
) -> List[Dict[str, Any]]:
    """Extract tool results from ADK events after a planner agent run.

    Scans events for FunctionResponse entries and builds tool_results list
    matching the format expected by the synthesizer.

    Args:
        events: List of ADK Event objects from the planner agent run.
        tool_to_plugin_map: Mapping from tool name to plugin pid.

    Returns:
        List of tool result dicts with tool_name, plugin_id, data, error keys.
    """
    results: List[Dict[str, Any]] = []
    for event in events:
        for func_response in event.get_function_responses():
            tool_name = func_response.name or ""
            plugin_id = tool_to_plugin_map.get(tool_name, "")
            raw = func_response.response or {}
            data: Any = None
            error: Optional[str] = None
            if isinstance(raw, dict):
                if "error" in raw:
                    error = str(raw["error"])
                    data = None
                else:
                    data = raw
            elif isinstance(raw, str):
                try:
                    data = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    data = raw
            else:
                data = raw
            results.append(
                {
                    "tool_name": tool_name,
                    "plugin_id": plugin_id,
                    "data": data,
                    "error": error,
                }
            )
    return results


def build_error_state(exception: Exception, node_name: str) -> Dict[str, Any]:
    """Build an error state dict for the error_handler node.

    Args:
        exception: The exception that caused the error.
        node_name: The pipeline node where the error occurred.

    Returns:
        Error state dictionary with categorized error type.
    """
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
        "node": node_name,
        "error_type": error_type,
        "error_message": str(exception),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def build_clarification_context(clarification_types: List[str]) -> str:
    """Build human-readable clarification context from type codes."""
    return "\n".join(
        _CLARIFICATION_TYPE_MESSAGES.get(t, t) for t in clarification_types
    )


def build_tool_context_text(tool_results: List[Dict[str, Any]]) -> str:
    """Format tool results as text for injection into synthesizer context."""
    if not tool_results:
        return ""
    return "\n".join(
        f"Tool: {r.get('tool_name')} | Plugin: {r.get('plugin_id')}\n{json.dumps(r.get('data'))}"
        for r in tool_results
    )
