"""LangGraph streaming event wrapper.

This module converts LangGraph native streaming events to unified StreamEvent format.
"""

import logging
from typing import Any, AsyncIterator, Dict, Tuple

from cadence.infrastructure.streaming import StreamEvent, StreamEventType

logger = logging.getLogger(__name__)


def _token_streaming_nodes() -> set:
    from cadence.engine.impl.langgraph.supervisor.graph_node import NodeDisplay

    return NodeDisplay.token_streaming_nodes()


class LangGraphStreamingWrapper:
    """Wrapper for converting LangGraph stream events to StreamEvent.

    LangGraph emits various event types during graph execution. This wrapper
    normalizes them to the unified StreamEvent format for consistent SSE delivery.

    When stream_mode=["updates", "messages"] is used, LangGraph emits tuples:
    - ("messages", (AIMessageChunk, metadata)) — individual token chunks
    - ("updates", {node_name: state_update}) — node completion events
    """

    async def wrap_stream(
        self,
        langgraph_stream: AsyncIterator[Any],
    ) -> AsyncIterator[StreamEvent]:
        """Convert LangGraph stream to StreamEvent stream.

        Handles combined stream_mode=["updates", "messages"] tuples as well as
        plain update dicts for backwards compatibility.

        Args:
            langgraph_stream: Async iterator of LangGraph events

        Yields:
            StreamEvent instances
        """
        async for item in langgraph_stream:
            try:
                if isinstance(item, tuple) and len(item) == 2:
                    mode, data = item
                    if mode == "messages":
                        converted = self._convert_message_chunk(data)
                    else:
                        converted = self._convert_update_event(data)
                else:
                    converted = self._convert_update_event(item)

                if converted:
                    yield converted
            except Exception as e:
                logger.error("Error converting LangGraph event: %s", e, exc_info=True)

    @staticmethod
    def _convert_message_chunk(data: Tuple[Any, Dict[str, Any]]) -> StreamEvent | None:
        """Convert a token-level message chunk from LangGraph messages stream mode.

        Args:
            data: (AIMessageChunk, metadata) tuple from LangGraph

        Returns:
            StreamEvent with the token content, or None to skip
        """
        chunk, metadata = data
        node = metadata.get("langgraph_node", "")

        if node not in _token_streaming_nodes():
            return None

        content = chunk.content if hasattr(chunk, "content") else ""
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        if not content:
            return None

        return StreamEvent.message(content=content, role="assistant", node=node)

    @staticmethod
    def _convert_update_event(event: Dict[str, Any]) -> StreamEvent | None:
        """Convert a node-completion update event.

        Emits agent/tool lifecycle events. Skips message content for token-streaming
        nodes since their content was already sent chunk-by-chunk.

        Args:
            event: {node_name: state_update} dict from LangGraph

        Returns:
            StreamEvent or None if event should be skipped
        """
        if not event:
            return None

        event_type = next(iter(event), None)
        if event_type == StreamEventType.AGENT:
            return StreamEvent.agent_start(event[event_type])
        else:
            return None


def create_streaming_wrapper() -> LangGraphStreamingWrapper:
    """Factory function for creating streaming wrapper.

    Returns:
        LangGraphStreamingWrapper instance
    """
    return LangGraphStreamingWrapper()
