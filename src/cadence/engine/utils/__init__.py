"""Orchestrator utility functions for messages, state, and plugins.

Exports message utilities (filter, compact, token estimation), state utilities
(copy, merge, sanitize), and plugin utilities (capability matching, routing prompts).
"""

from cadence.engine.utils.message_utils import (
    build_message_summary,
    compact_messages,
    count_tokens_estimate,
    filter_tool_messages,
    get_last_human_message,
)
from cadence.engine.utils.plugin_utils import (
    build_all_plugins_description,
    build_plugin_description,
    build_routing_prompt,
    build_tool_descriptions,
    extract_plugin_capabilities,
    match_capability,
    select_plugin_by_capability,
)
from cadence.engine.utils.state_utils import (
    copy_state,
    extract_metadata,
    merge_states,
    sanitize_state,
    update_metadata,
)

__all__ = [
    "copy_state",
    "merge_states",
    "sanitize_state",
    "extract_metadata",
    "update_metadata",
    "filter_tool_messages",
    "get_last_human_message",
    "count_tokens_estimate",
    "compact_messages",
    "build_message_summary",
    "build_all_plugins_description",
    "build_plugin_description",
    "build_routing_prompt",
    "build_tool_descriptions",
    "extract_plugin_capabilities",
    "match_capability",
    "select_plugin_by_capability",
]
