"""Message processing utilities for orchestrators.

This module provides utilities for filtering, compacting, and processing messages.
"""

from collections import Counter
from typing import List, Optional

from cadence_sdk.types.sdk_messages import (
    AnyMessage,
    UvAIMessage,
    UvHumanMessage,
    UvSystemMessage,
    UvToolMessage,
)

from cadence.constants import CHARS_PER_TOKEN, DEFAULT_MAX_TOOL_CHARS


def filter_tool_messages(messages: List[AnyMessage]) -> List[AnyMessage]:
    """Remove tool messages from message list.

    Args:
        messages: List of messages

    Returns:
        Filtered message list
    """
    return [msg for msg in messages if not isinstance(msg, UvToolMessage)]


def get_last_human_message(messages: List[AnyMessage]) -> Optional[UvHumanMessage]:
    """Get the last human message from list.

    Args:
        messages: List of messages

    Returns:
        Last human message or None
    """
    for msg in reversed(messages):
        if isinstance(msg, UvHumanMessage):
            return msg
    return None


def count_tokens_estimate(messages: List[AnyMessage]) -> int:
    """Estimate token count for messages.

    Uses rough approximation: 1 token ≈ 4 characters.

    Args:
        messages: List of messages

    Returns:
        Estimated token count
    """
    total_chars = sum(len(str(msg.content)) for msg in messages)
    return total_chars // CHARS_PER_TOKEN


def compact_tool_messages(
    messages: List[AnyMessage],
    max_chars: int = DEFAULT_MAX_TOOL_CHARS,
) -> List[AnyMessage]:
    """Compact tool messages by truncating long outputs.

    Summarizes tool messages that exceed max_chars by truncating
    and adding a summary indicator.

    Args:
        messages: List of messages
        max_chars: Maximum characters per tool message

    Returns:
        List of messages with compacted tool messages
    """
    compacted = []

    for msg in messages:
        if isinstance(msg, UvToolMessage) and len(msg.content) > max_chars:
            compacted_msg = _create_truncated_tool_message(msg, max_chars)
            compacted.append(compacted_msg)
        else:
            compacted.append(msg)

    return compacted


def _create_truncated_tool_message(msg: UvToolMessage, max_chars: int) -> UvToolMessage:
    """Create truncated version of tool message.

    Args:
        msg: Original tool message
        max_chars: Maximum characters to keep

    Returns:
        Truncated tool message
    """
    truncated_content = msg.content[:max_chars]
    summary = (
        f"{truncated_content}... [truncated, original length: {len(msg.content)} chars]"
    )

    return UvToolMessage(
        content=summary,
        tool_call_id=msg.tool_call_id,
        tool_name=msg.tool_name,
    )


def compact_messages_by_mode(
    messages: List[AnyMessage],
    mode: str = "tool",
    max_tool_chars: int = DEFAULT_MAX_TOOL_CHARS,
) -> List[AnyMessage]:
    """Compact messages based on mode.

    Modes:
    - "none": No compaction
    - "tool": Compact only tool messages
    - "aggressive": Compact tool messages and summarize system messages

    Args:
        messages: List of messages
        mode: Compaction mode
        max_tool_chars: Maximum characters per tool message

    Returns:
        Compacted message list
    """
    if mode == "none":
        return messages

    if mode == "tool":
        return compact_tool_messages(messages, max_tool_chars)

    if mode == "aggressive":
        return _compact_messages_aggressively(messages, max_tool_chars)

    return messages


def _compact_messages_aggressively(
    messages: List[AnyMessage], max_tool_chars: int
) -> List[AnyMessage]:
    """Perform aggressive message compaction.

    Args:
        messages: Messages to compact
        max_tool_chars: Maximum characters per tool message

    Returns:
        Compacted messages
    """
    compacted = compact_tool_messages(messages, max_tool_chars)
    return compacted


def compact_messages(
    messages: List[AnyMessage],
    max_messages: Optional[int] = None,
    keep_system: bool = True,
) -> List[AnyMessage]:
    """Compact message list by keeping recent messages.

    Args:
        messages: List of messages
        max_messages: Maximum messages to keep (None = no limit)
        keep_system: Whether to always keep system messages

    Returns:
        Compacted message list
    """
    if max_messages is None or len(messages) <= max_messages:
        return messages

    if keep_system:
        system_msgs = [msg for msg in messages if isinstance(msg, UvSystemMessage)]
        other_msgs = [msg for msg in messages if not isinstance(msg, UvSystemMessage)]
        keep_count = max_messages - len(system_msgs)
        if keep_count <= 0:
            return system_msgs
        return system_msgs + other_msgs[-keep_count:]

    return messages[-max_messages:]


def build_message_summary(messages: List[AnyMessage]) -> str:
    """Build human-readable summary of messages.

    Args:
        messages: List of messages

    Returns:
        Summary string
    """
    type_map = {
        UvHumanMessage: "human",
        UvAIMessage: "ai",
        UvSystemMessage: "system",
        UvToolMessage: "tool",
    }
    counts: Counter = Counter()
    for msg in messages:
        for msg_type, label in type_map.items():
            if isinstance(msg, msg_type):
                counts[label] += 1
                break

    return f"{counts['human']} human, {counts['ai']} AI, {counts['system']} system, {counts['tool']} tool"
