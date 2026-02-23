"""LangGraph handoff orchestrator — not yet implemented."""

import logging
from typing import Any, AsyncIterator, Dict

from cadence_sdk.types.sdk_state import UvState

from cadence.constants import Framework
from cadence.engine.base import StreamEvent
from cadence.engine.impl.langgraph.adapter import LangChainAdapter
from cadence.engine.impl.langgraph.base import BaseLangGraphOrchestrator
from cadence.engine.impl.langgraph.streaming import LangGraphStreamingWrapper
from cadence.engine.modes import HandoffMode
from cadence.infrastructure.plugins import SDKPluginManager

logger = logging.getLogger(__name__)


class LangGraphHandoff(BaseLangGraphOrchestrator):
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
        self.mode_config = HandoffMode(
            Framework.LANGGRAPH, resolved_config.get("mode_config", {})
        )

    async def _build_resources(self) -> None:
        self.logger.warning("LangGraph handoff is not yet implemented")

    async def astream(self, state: UvState) -> AsyncIterator[StreamEvent]:
        raise NotImplementedError("LangGraph handoff is not yet implemented")

    async def rebuild(self, config: Dict[str, Any]) -> None:
        raise NotImplementedError("LangGraph handoff is not yet implemented")

    def _extra_health_fields(self) -> Dict[str, Any]:
        return {"status": "not_implemented"}

    @property
    def mode(self) -> str:
        return "handoff"

    def get_stream_data_before_graph_start(self) -> Any:
        return None

    def _build_initial_graph_state(self, lc_messages):
        raise NotImplementedError

    def _get_recursion_limit(self) -> int:
        raise NotImplementedError

    def _map_result_to_output(self, result, output_state):
        raise NotImplementedError
