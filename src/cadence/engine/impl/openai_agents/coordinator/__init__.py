"""OpenAI Agents SDK coordinator orchestrator — not yet implemented."""

import logging
from typing import Any, AsyncIterator, Dict

from cadence_sdk.types.sdk_state import UvState

from cadence.engine.base import BaseOrchestrator, StreamEvent
from cadence.engine.impl.openai_agents.adapter import OpenAIAgentsAdapter
from cadence.engine.impl.openai_agents.streaming import OpenAIAgentsStreamingWrapper
from cadence.engine.modes import CoordinatorMode
from cadence.infrastructure.plugins import SDKPluginManager

logger = logging.getLogger(__name__)


class OpenAICoordinator(BaseOrchestrator):
    """Placeholder coordinator for OpenAI Agents SDK. Not yet implemented."""

    def __init__(
        self,
        plugin_manager: SDKPluginManager,
        llm_factory: Any,
        resolved_config: Dict[str, Any],
        adapter: OpenAIAgentsAdapter,
        streaming_wrapper: OpenAIAgentsStreamingWrapper,
    ):
        super().__init__(
            plugin_manager=plugin_manager,
            llm_factory=llm_factory,
            resolved_config=resolved_config,
            adapter=adapter,
            streaming_wrapper=streaming_wrapper,
        )
        self.mode_config = CoordinatorMode(
            "openai_agents", resolved_config.get("mode_config", {})
        )

    async def _build_resources(self) -> None:
        self.logger.warning("OpenAI Agents SDK backend is not yet implemented")

    async def astream(self, state: UvState) -> AsyncIterator[StreamEvent]:
        raise NotImplementedError("OpenAI Agents SDK backend is not yet implemented")

    async def rebuild(self, config: Dict[str, Any]) -> None:
        raise NotImplementedError("OpenAI Agents SDK backend is not yet implemented")

    def _extra_health_fields(self) -> Dict[str, Any]:
        return {"status": "not_implemented"}

    @property
    def mode(self) -> str:
        return "coordinator"

    @property
    def framework_type(self) -> str:
        return "openai_agents"
