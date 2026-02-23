"""Google ADK reflection orchestrator — not yet implemented."""

import logging
from typing import Any, AsyncIterator, Dict

from cadence_sdk.types.sdk_state import UvState

from cadence.constants import Framework
from cadence.engine.base import BaseOrchestrator, StreamEvent
from cadence.engine.impl.google_adk.adapter import GoogleADKAdapter
from cadence.engine.impl.google_adk.streaming import GoogleADKStreamingWrapper
from cadence.engine.modes import ReflectionMode
from cadence.infrastructure.plugins import SDKPluginManager

logger = logging.getLogger(__name__)


class GoogleADKReflection(BaseOrchestrator):
    """Placeholder reflection orchestrator for Google ADK. Not yet implemented."""

    adapter: GoogleADKAdapter

    def __init__(
        self,
        plugin_manager: SDKPluginManager,
        llm_factory: Any,
        resolved_config: Dict[str, Any],
        adapter: GoogleADKAdapter,
        streaming_wrapper: GoogleADKStreamingWrapper,
    ):
        super().__init__(
            plugin_manager=plugin_manager,
            llm_factory=llm_factory,
            resolved_config=resolved_config,
            adapter=adapter,
            streaming_wrapper=streaming_wrapper,
        )
        self.mode_config = ReflectionMode(
            Framework.GOOGLE_ADK, resolved_config.get("mode_config", {})
        )

    async def _build_resources(self) -> None:
        self.logger.warning("Google ADK reflection is not yet implemented")

    async def astream(self, state: UvState) -> AsyncIterator[StreamEvent]:
        raise NotImplementedError("Google ADK reflection is not yet implemented")

    async def rebuild(self, config: Dict[str, Any]) -> None:
        raise NotImplementedError("Google ADK reflection is not yet implemented")

    def _extra_health_fields(self) -> Dict[str, Any]:
        return {"status": "not_implemented"}

    @property
    def mode(self) -> str:
        return "reflection"

    @property
    def framework_type(self) -> str:
        return "google_adk"
