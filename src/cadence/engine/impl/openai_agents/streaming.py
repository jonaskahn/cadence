"""OpenAI Agents SDK streaming wrapper — not yet implemented."""

from typing import AsyncIterator

from cadence.infrastructure.streaming import StreamEvent


class OpenAIAgentsStreamingWrapper:
    """Placeholder streaming wrapper for OpenAI Agents SDK. Not yet implemented."""

    async def wrap_stream(
        self, openai_stream: AsyncIterator
    ) -> AsyncIterator[StreamEvent]:
        raise NotImplementedError("OpenAI Agents SDK backend is not yet implemented")

    def _convert_event(self, event: dict) -> StreamEvent:
        raise NotImplementedError("OpenAI Agents SDK backend is not yet implemented")
