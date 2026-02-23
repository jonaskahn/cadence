"""Google ADK streaming wrapper.

Converts Google ADK native events to the unified StreamEvent format for SSE delivery.
"""

import logging
from typing import Any, AsyncIterator

from cadence_sdk import Loggable

from cadence.infrastructure.streaming import StreamEvent

logger = logging.getLogger(__name__)


def _token_streaming_nodes() -> set:
    """Lazy import to avoid circular dependency."""
    from cadence.engine.impl.google_adk.supervisor.pipeline_node import NodeDisplay

    return NodeDisplay.token_streaming_nodes()


class GoogleADKStreamingWrapper(Loggable):
    """Wrapper for converting Google ADK stream events to StreamEvent.

    ADK emits Event objects during agent execution. This wrapper normalises
    them to the unified StreamEvent format for consistent SSE delivery.

    Two event types are handled:
    - Custom node-transition events emitted by GoogleADKPipeline via
      ``_make_node_event()`` — detected via ``event.custom_metadata.node_name``.
    - Text content events from token-streaming nodes (synthesizer, clarifier,
      responder, error_handler) — emitted as ``StreamEvent.message()``.
    """

    async def wrap_stream(
        self, google_stream: AsyncIterator[Any]
    ) -> AsyncIterator[StreamEvent]:
        """Convert Google ADK event stream to StreamEvent stream.

        Args:
            google_stream: Async iterator of ADK Event objects.

        Yields:
            StreamEvent instances.
        """
        self.logger.info("Google ADK Stream started to stream")
        async for event in google_stream:
            try:
                # ── Custom node-start events from GoogleADKPipeline ───────────
                if event.custom_metadata and "node_name" in event.custom_metadata:
                    node_name = event.custom_metadata["node_name"]
                    from cadence.engine.impl.google_adk.supervisor.pipeline_node import (
                        NodeDisplay,
                    )

                    yield StreamEvent.agent_start(NodeDisplay.get_by_name(node_name))
                    continue

                # ── Text tokens from terminal nodes ────────────────────────────
                # Skip partial=False (final duplicate event when streaming=True).
                # partial=True → streaming chunk (emit), partial=None → non-streaming final (emit).
                if (
                    event.author in _token_streaming_nodes()
                    and event.partial is not False
                    and event.content
                    and event.content.parts
                ):
                    for part in event.content.parts:
                        if part.text:
                            yield StreamEvent.message(
                                content=part.text,
                                role="assistant",
                                node=event.author,
                            )

            except Exception as e:
                logger.error("Error converting ADK event: %s", e, exc_info=True)
