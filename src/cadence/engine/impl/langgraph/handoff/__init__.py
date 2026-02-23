"""LangGraph handoff orchestrator — not yet implemented."""

import logging
from typing import Any, AsyncIterator, Dict, List

from cadence_sdk.types.sdk_state import UvState

from cadence.engine.base import BaseOrchestrator, StreamEvent
from cadence.engine.impl.langgraph.orchestrator_adapter import LangChainAdapter
from cadence.engine.impl.langgraph.streaming_wrapper import LangGraphStreamingWrapper
from cadence.engine.modes import HandoffMode
from cadence.infrastructure.plugins import SDKPluginManager

logger = logging.getLogger(__name__)


class LangGraphHandoff(BaseOrchestrator):
    """Placeholder handoff orchestrator for LangGraph. Not yet implemented."""

    def __init__(
        self,
        plugin_manager: SDKPluginManager,
        llm_factory: Any,
        resolved_config: Dict[str, Any],
        adapter: LangChainAdapter,
        streaming_wrapper: LangGraphStreamingWrapper,
    ):
        super().__init__(
            plugin_manager=plugin_manager,
            llm_factory=llm_factory,
            resolved_config=resolved_config,
            adapter=adapter,
            streaming_wrapper=streaming_wrapper,
        )
        self.mode_config = HandoffMode(resolved_config.get("mode_config", {}))
        self._plugin_bundles = plugin_manager.bundles
        self._is_ready = False

    def _initialize(self) -> None:
        logger.warning("LangGraph handoff is not yet implemented")

    async def ask(self, state: UvState) -> UvState:
        raise NotImplementedError("LangGraph handoff is not yet implemented")

    async def astream(self, state: UvState) -> AsyncIterator[StreamEvent]:
        raise NotImplementedError("LangGraph handoff is not yet implemented")

    async def rebuild(self, config: Dict[str, Any]) -> None:
        raise NotImplementedError("LangGraph handoff is not yet implemented")

    async def cleanup(self) -> None:
        self._is_ready = False

    async def health_check(self) -> Dict[str, Any]:
        return {
            "framework_type": self.framework_type,
            "mode": self.mode,
            "is_ready": False,
            "status": "not_implemented",
        }

    @property
    def mode(self) -> str:
        return "handoff"

    @property
    def framework_type(self) -> str:
        return "langgraph"

    @property
    def plugin_pids(self) -> List[str]:
        return list(self._plugin_bundles.keys())

    @property
    def is_ready(self) -> bool:
        return False
