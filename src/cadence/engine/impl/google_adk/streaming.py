"""Google ADK streaming wrapper — not yet implemented."""

from typing import Any, AsyncIterator

from cadence.engine.base import StreamEvent


class GoogleADKStreamingWrapper:
    """Placeholder streaming wrapper for Google ADK. Not yet implemented."""

    async def wrap_stream(
        self, google_stream: AsyncIterator[Any]
    ) -> AsyncIterator[StreamEvent]:
        raise NotImplementedError("Google ADK backend is not yet implemented")

    def _convert_event(self, event: Any) -> StreamEvent:
        raise NotImplementedError("Google ADK backend is not yet implemented")
