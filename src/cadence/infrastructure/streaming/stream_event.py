"""Streaming event infrastructure.

This module defines unified streaming events for Server-Sent Events (SSE) delivery.
All orchestrator backends convert their native streaming events to this format.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional


class StreamEventType:
    """Event type constants for streaming.

    Attributes:
        AGENT: Agent execution started
        MESSAGE: Message or response chunk
        METADATA: Metadata update
    """

    AGENT = "agent"
    MESSAGE = "message"
    METADATA = "metadata"


class StreamEvent:
    """Unified streaming event for orchestrator responses.

    Converts to Server-Sent Event (SSE) format for HTTP streaming.

    Attributes:
        event_type: Type of event (from StreamEventType)
        data: Event payload dictionary
        timestamp: Unix timestamp when event was created
    """

    def __init__(
        self, event_type: str, data: Dict[str, Any], timestamp: Optional[float] = None
    ):
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
    def agent_start(cls, data: Any | None) -> StreamEvent:
        """Create agent start event.

        Args:
            data: Additional data

        Returns:
            StreamEvent instance
        """
        return cls(StreamEventType.AGENT, data)

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
    def metadata(cls, metadata: Dict[str, Any]) -> StreamEvent:
        """Create metadata event.

        Args:
            metadata: Metadata dictionary

        Returns:
            StreamEvent instance
        """
        return cls(StreamEventType.METADATA, metadata)
