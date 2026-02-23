"""Streaming event infrastructure.

This module defines unified streaming events for Server-Sent Events (SSE) delivery.
All orchestrator backends convert their native streaming events to this format.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict


class StreamEventType:
    """Event type constants for streaming.

    Attributes:
        AGENT_START: Agent execution started
        AGENT_END: Agent execution completed
        TOOL_START: Tool execution started
        TOOL_END: Tool execution completed
        MESSAGE: Message or response chunk
        ERROR: Error occurred
        METADATA: Metadata update
        STATUS: Status update
    """

    AGENT_START = "agent_start"
    AGENT_END = "agent_end"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    MESSAGE = "message"
    ERROR = "error"
    METADATA = "metadata"
    STATUS = "status"


class StreamEvent:
    """Unified streaming event for orchestrator responses.

    Converts to Server-Sent Event (SSE) format for HTTP streaming.

    Attributes:
        event_type: Type of event (from StreamEventType)
        data: Event payload dictionary
        timestamp: Unix timestamp when event was created
    """

    def __init__(self, event_type: str, data: Dict[str, Any], timestamp: float = None):
        """Initialize stream event.

        Args:
            event_type: Event type identifier
            data: Event payload
            timestamp: Optional timestamp (defaults to current time)
        """
        self.event_type = event_type
        self.data = data
        self.timestamp = timestamp or time.time()

    def to_sse(self) -> str:
        """Convert to Server-Sent Event format.

        Returns:
            SSE-formatted string with event type and JSON data
        """
        return f"event: {self.event_type}\ndata: {json.dumps(self.data)}\n\n"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "event_type": self.event_type,
            "data": self.data,
            "timestamp": self.timestamp,
        }

    @classmethod
    def agent_start(cls, agent_name: str, **kwargs) -> StreamEvent:
        """Create agent start event.

        Args:
            agent_name: Name of the agent
            **kwargs: Additional data

        Returns:
            StreamEvent instance
        """
        return cls(StreamEventType.AGENT_START, {"agent": agent_name, **kwargs})

    @classmethod
    def agent_end(cls, agent_name: str, **kwargs) -> StreamEvent:
        """Create agent end event.

        Args:
            agent_name: Name of the agent
            **kwargs: Additional data

        Returns:
            StreamEvent instance
        """
        return cls(StreamEventType.AGENT_END, {"agent": agent_name, **kwargs})

    @classmethod
    def tool_start(cls, tool_name: str, **kwargs) -> StreamEvent:
        """Create tool start event.

        Args:
            tool_name: Name of the tool
            **kwargs: Additional data

        Returns:
            StreamEvent instance
        """
        return cls(StreamEventType.TOOL_START, {"tool": tool_name, **kwargs})

    @classmethod
    def tool_end(cls, tool_name: str, result: Any, **kwargs) -> StreamEvent:
        """Create tool end event.

        Args:
            tool_name: Name of the tool
            result: Tool execution result
            **kwargs: Additional data

        Returns:
            StreamEvent instance
        """
        return cls(
            StreamEventType.TOOL_END, {"tool": tool_name, "result": result, **kwargs}
        )

    @classmethod
    def message(cls, content: str, role: str = "assistant", **kwargs) -> StreamEvent:
        """Create message event.

        Args:
            content: Message content
            role: Message role (default: assistant)
            **kwargs: Additional data

        Returns:
            StreamEvent instance
        """
        return cls(
            StreamEventType.MESSAGE, {"content": content, "role": role, **kwargs}
        )

    @classmethod
    def error(cls, error_message: str, **kwargs) -> StreamEvent:
        """Create error event.

        Args:
            error_message: Error description
            **kwargs: Additional data

        Returns:
            StreamEvent instance
        """
        return cls(StreamEventType.ERROR, {"error": error_message, **kwargs})

    @classmethod
    def metadata(cls, metadata: Dict[str, Any]) -> StreamEvent:
        """Create metadata event.

        Args:
            metadata: Metadata dictionary

        Returns:
            StreamEvent instance
        """
        return cls(StreamEventType.METADATA, metadata)

    @classmethod
    def status(cls, status: str, **kwargs) -> StreamEvent:
        """Create status event.

        Args:
            status: Status message
            **kwargs: Additional data

        Returns:
            StreamEvent instance
        """
        return cls(StreamEventType.STATUS, {"status": status, **kwargs})
