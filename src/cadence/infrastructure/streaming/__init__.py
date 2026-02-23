"""Streaming infrastructure for Server-Sent Events (SSE).

Exports StreamEvent and StreamEventType for real-time chat responses.
Used by orchestrators to yield agent_start, tool_start, message, and
agent_end events to clients.
"""

from cadence.infrastructure.streaming.stream_event import StreamEvent, StreamEventType

__all__ = ["StreamEvent", "StreamEventType"]
