"""LangGraph streaming event wrapper.

This module converts LangGraph native streaming events to unified StreamEvent format.
"""

import logging
from typing import Any, AsyncIterator, Dict

from cadence.infrastructure.streaming import StreamEvent

logger = logging.getLogger(__name__)


class LangGraphStreamingWrapper:
    """Wrapper for converting LangGraph stream events to StreamEvent.

    LangGraph emits various event types during graph execution. This wrapper
    normalizes them to the unified StreamEvent format for consistent SSE delivery.
    """

    def __init__(self):
        """Initialize streaming wrapper."""
        pass

    async def wrap_stream(
        self,
        langgraph_stream: AsyncIterator[Dict[str, Any]],
    ) -> AsyncIterator[StreamEvent]:
        """Convert LangGraph stream to StreamEvent stream.

        Args:
            langgraph_stream: Async iterator of LangGraph events

        Yields:
            StreamEvent instances
        """
        async for event in langgraph_stream:
            try:
                converted = self._convert_event(event)
                if converted:
                    yield converted
            except Exception as e:
                logger.error(f"Error converting LangGraph event: {e}", exc_info=True)
                yield StreamEvent.error(f"Stream conversion error: {str(e)}")

    def _convert_event(self, event: Dict[str, Any]) -> StreamEvent:
        """Convert single LangGraph event to StreamEvent.

        LangGraph events have structure: {node_name: {messages: [...]}}

        Args:
            event: LangGraph event dictionary

        Returns:
            StreamEvent or None if event should be skipped
        """
        if not event:
            return None

        node_name = list(event.keys())[0] if event else None
        if not node_name:
            return None

        node_data = event[node_name]

        if node_name == "supervisor":
            return self._convert_supervisor_event(node_data)
        elif node_name == "control_tools":
            return self._convert_tool_event(node_data)
        elif node_name == "synthesizer":
            return self._convert_synthesizer_event(node_data)
        elif node_name == "error_handler":
            return self._convert_error_event(node_data)
        else:
            return StreamEvent.status(f"Node: {node_name}", data=node_data)

    def _convert_supervisor_event(self, data: Dict[str, Any]) -> StreamEvent:
        """Convert supervisor node event.

        Args:
            data: Node data

        Returns:
            StreamEvent
        """
        messages = data.get("messages", [])
        if messages:
            last_msg = messages[-1]
            if hasattr(last_msg, "content"):
                return StreamEvent.message(
                    content=last_msg.content,
                    role="assistant",
                    node="supervisor",
                )

        return StreamEvent.agent_start("supervisor")

    def _convert_tool_event(self, data: Dict[str, Any]) -> StreamEvent:
        """Convert tool execution event.

        Args:
            data: Node data

        Returns:
            StreamEvent
        """
        messages = data.get("messages", [])
        if messages:
            last_msg = messages[-1]
            if hasattr(last_msg, "name"):
                tool_name = last_msg.name
                content = last_msg.content if hasattr(last_msg, "content") else ""
                return StreamEvent.tool_end(tool_name, result=content)

        return StreamEvent.status("tool_executing")

    def _convert_synthesizer_event(self, data: Dict[str, Any]) -> StreamEvent:
        """Convert synthesizer node event.

        Args:
            data: Node data

        Returns:
            StreamEvent
        """
        messages = data.get("messages", [])
        if messages:
            last_msg = messages[-1]
            if hasattr(last_msg, "content"):
                return StreamEvent.message(
                    content=last_msg.content,
                    role="assistant",
                    node="synthesizer",
                    final=True,
                )

        return StreamEvent.agent_start("synthesizer")

    def _convert_error_event(self, data: Dict[str, Any]) -> StreamEvent:
        """Convert error handler event.

        Args:
            data: Node data

        Returns:
            StreamEvent
        """
        messages = data.get("messages", [])
        if messages:
            last_msg = messages[-1]
            error_text = (
                last_msg.content if hasattr(last_msg, "content") else "Unknown error"
            )
            return StreamEvent.error(error_text)

        return StreamEvent.error("An error occurred")


def create_streaming_wrapper() -> LangGraphStreamingWrapper:
    """Factory function for creating streaming wrapper.

    Returns:
        LangGraphStreamingWrapper instance
    """
    return LangGraphStreamingWrapper()
