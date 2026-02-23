"""Shared base for all LangGraph orchestrator implementations.

All three LangGraph modes (supervisor, coordinator, handoff) share identical
astream/rebuild/cleanup logic. Only graph construction and state layout
differ, so subclasses override the abstract hooks.
"""

import logging
from abc import abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional, TypedDict

from cadence_sdk.types.sdk_state import UvState

from cadence.engine.base import BaseOrchestrator, StreamEvent
from cadence.engine.impl.langgraph.adapter import LangChainAdapter
from cadence.engine.impl.langgraph.streaming import LangGraphStreamingWrapper
from cadence.infrastructure.plugins import SDKPluginManager

logger = logging.getLogger(__name__)


class BaseLangGraphOrchestrator(BaseOrchestrator):
    """Shared logic for LangGraph supervisor, coordinator, and handoff modes.

    Subclasses implement:
    - ``_build_resources()``
    - ``get_stream_data_before_graph_start()``
    - ``_build_initial_graph_state(lc_messages)``
    - ``_get_recursion_limit()``
    - ``_map_result_to_output(result, output_state)``
    - ``mode`` property
    """

    adapter: LangChainAdapter

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
        self.graph = None

    async def astream(self, state: UvState) -> AsyncIterator[StreamEvent]:
        """Execute streaming orchestration."""
        if not self._is_ready:
            raise RuntimeError("Orchestrator is not ready")

        messages = state.get("messages", [])
        lc_messages = [
            self.adapter.sdk_message_to_orchestrator(msg) for msg in messages
        ]

        graph_state = self._build_initial_graph_state(lc_messages)
        config = {"recursion_limit": self._get_recursion_limit()}

        before_orch_start_data = self.get_stream_data_before_graph_start()
        if before_orch_start_data:
            yield before_orch_start_data

        langgraph_stream = self.graph.astream(
            graph_state, config=config, stream_mode=["messages", "custom"]
        )
        async for event in self.streaming_wrapper.wrap_stream(langgraph_stream):
            yield event

    @abstractmethod
    def get_stream_data_before_graph_start(self) -> Any:
        """Before orchestrator start."""
        return None

    @abstractmethod
    def _build_initial_graph_state(self, lc_messages: List[Any]) -> TypedDict:
        """Return the initial graph state dict for this mode."""
        pass

    @abstractmethod
    def _get_recursion_limit(self) -> int:
        """Return the recursion limit to use when invoking the graph."""
        pass

    @abstractmethod
    def _map_result_to_output(
        self, result: Dict[str, Any], output_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Map graph result fields to output_state fields."""
        pass

    def get_graph_mermaid(self) -> Optional[str]:
        """Return Mermaid diagram definition for the compiled graph."""
        if self.graph is None:
            return None
        try:
            return self.graph.get_graph().draw_mermaid()
        except Exception:
            logger.warning("Failed to generate Mermaid diagram", exc_info=True)
            return None

    @property
    def framework_type(self) -> str:
        return "langgraph"
