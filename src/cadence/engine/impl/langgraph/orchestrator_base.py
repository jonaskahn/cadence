"""Shared base for all LangGraph orchestrator implementations.

All three LangGraph modes (supervisor, coordinator, handoff) share identical
ask/astream/rebuild/cleanup logic. Only graph construction and state layout
differ, so subclasses override the abstract hooks.
"""

import logging
from abc import abstractmethod
from typing import Any, AsyncIterator, Dict, List

from cadence_sdk.types.sdk_state import UvState

from cadence.engine.base import BaseOrchestrator, StreamEvent
from cadence.engine.impl.langgraph.orchestrator_adapter import LangChainAdapter
from cadence.engine.impl.langgraph.streaming_wrapper import LangGraphStreamingWrapper
from cadence.infrastructure.plugins import SDKPluginManager

logger = logging.getLogger(__name__)


class BaseLangGraphOrchestrator(BaseOrchestrator):
    """Shared logic for LangGraph supervisor, coordinator, and handoff modes.

    Subclasses implement:
    - ``_build_initial_graph_state(lc_messages)``
    - ``_get_recursion_limit()``
    - ``_map_result_to_output(result, output_state)``
    - ``_initialize()``
    - ``cleanup()``
    - ``health_check()``
    - ``mode`` property
    """

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
        self._plugin_bundles = plugin_manager.bundles
        self._is_ready = False
        self.graph = None

    @abstractmethod
    def _build_initial_graph_state(self, lc_messages: List[Any]) -> Dict[str, Any]:
        """Return the initial graph state dict for this mode."""

    @abstractmethod
    def _get_recursion_limit(self) -> int:
        """Return the recursion limit to use when invoking the graph."""

    @abstractmethod
    def _map_result_to_output(
        self, result: Dict[str, Any], output_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Map graph result fields to output_state fields."""

    @abstractmethod
    async def initialize(self) -> None:
        """Build mode-specific resources (model, graph, etc.)."""

    async def ask(self, state: UvState) -> UvState:
        """Execute single-shot orchestration.

        Args:
            state: Input state with messages

        Returns:
            Updated state with response
        """
        if not self._is_ready:
            raise RuntimeError("Orchestrator not ready")

        messages = state.get("messages", [])
        lc_messages = [
            self.adapter.sdk_message_to_orchestrator(msg) for msg in messages
        ]

        graph_state = self._build_initial_graph_state(lc_messages)
        config = {"recursion_limit": self._get_recursion_limit()}

        result = await self.graph.ainvoke(graph_state, config=config)

        result_messages = result.get("messages", [])
        sdk_messages = [
            self.adapter.orchestrator_message_to_sdk(msg) for msg in result_messages
        ]

        output_state = state.copy()
        output_state["messages"] = sdk_messages
        output_state = self._map_result_to_output(result, output_state)

        return output_state

    async def astream(self, state: UvState) -> AsyncIterator[StreamEvent]:
        """Execute streaming orchestration.

        Args:
            state: Input state with messages

        Yields:
            StreamEvent instances
        """
        if not self._is_ready:
            raise RuntimeError("Orchestrator not ready")

        messages = state.get("messages", [])
        lc_messages = [
            self.adapter.sdk_message_to_orchestrator(msg) for msg in messages
        ]

        graph_state = self._build_initial_graph_state(lc_messages)
        config = {"recursion_limit": self._get_recursion_limit()}

        langgraph_stream = self.graph.astream(graph_state, config=config)

        async for event in self.streaming_wrapper.wrap_stream(langgraph_stream):
            yield event

    @property
    def framework_type(self) -> str:
        return "langgraph"

    @property
    def plugin_pids(self) -> List[str]:
        return list(self._plugin_bundles.keys())

    @property
    def is_ready(self) -> bool:
        return self._is_ready
