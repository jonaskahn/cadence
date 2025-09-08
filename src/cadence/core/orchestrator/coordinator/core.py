"""Main agent coordinator for multi-agent conversation orchestration."""

import traceback
import uuid
from datetime import datetime, timezone
from typing import Any

from cadence_sdk.base.loggable import Loggable
from cadence_sdk.types import AgentState
from cadence_sdk.types.state import AgentStateFields, StateHelpers
from langchain_core.messages import SystemMessage, ToolCall

from .graph_builder import ConversationGraphBuilder
from .handlers import ResponseContextBuilder, SuspendHandler, SynthesizerHandler, TimeoutHandler
from .model_factory import CoordinatorModelFactory
from .prompts import ConversationPrompts
from .routing import ConversationRouter, RouteCounter


class AgentCoordinator(Loggable):
    """Coordinates multi-agent conversations using LangGraph with dynamic plugin integration."""

    def __init__(
        self,
        plugin_manager,
        llm_factory,
        settings,
        checkpointer: Any | None = None,
    ) -> None:
        """Initialize coordinator with dependencies."""
        super().__init__()
        self.plugin_manager = plugin_manager
        self.llm_factory = llm_factory
        self.settings = settings
        self.checkpointer = checkpointer

        # Initialize components
        self.router = ConversationRouter(settings)
        self.model_factory = CoordinatorModelFactory(llm_factory, settings)
        self.context_builder = ResponseContextBuilder(plugin_manager, settings)
        self.suspend_handler = SuspendHandler(plugin_manager, settings, self.context_builder)
        self.synthesizer_handler = SynthesizerHandler(plugin_manager, settings, self.context_builder)
        self.timeout_handler = TimeoutHandler(settings)
        self.graph_builder = ConversationGraphBuilder(plugin_manager, self.router)

        # Create models and graph
        self.coordinator_model = self.model_factory.create_coordinator_model(plugin_manager)
        self.suspend_model = self.model_factory.create_suspend_model()
        self.synthesizer_model = self.model_factory.create_synthesizer_model()
        self.graph = self._build_conversation_graph()

    def _build_conversation_graph(self):
        """Build the conversation graph with all components."""
        return self.graph_builder.build_conversation_graph(
            self._coordinator_node, self._suspend_node, self._synthesizer_node, self.checkpointer
        )

    def rebuild_graph(self) -> None:
        """Rebuild conversation graph after plugin changes."""
        try:
            self.logger.debug("Rebuilding orchestrator graph after plugins change/reload ...")
            self.coordinator_model = self.model_factory.create_coordinator_model(self.plugin_manager)
            self.suspend_model = self.model_factory.create_suspend_model()
            self.synthesizer_model = self.model_factory.create_synthesizer_model()
            self.graph = self._build_conversation_graph()
            self.logger.info("Graph rebuilt successfully")
        except Exception as e:
            self.logger.error(f"Failed to rebuild graph: {e}")
            raise

    async def ask(self, state: AgentState) -> AgentState:
        """Process conversation state through multi-agent workflow."""
        try:
            config = {"recursion_limit": self.settings.graph_recursion_limit}
            return await self.graph.ainvoke(state, config)
        except Exception as e:
            self.logger.error(f"Error in conversation processing: {e}")
            self.logger.error(traceback.format_exc())
            raise

    async def _coordinator_node(self, state: AgentState) -> AgentState:
        """Execute main decision-making step that determines conversation routing."""
        messages = StateHelpers.safe_get_messages(state)

        plugin_descriptions = self._build_plugin_descriptions()
        tool_options = self._build_tool_options()

        coordinator_prompt = ConversationPrompts.COORDINATOR_INSTRUCTIONS.format(
            plugin_descriptions=plugin_descriptions,
            tool_options=tool_options,
            current_time=datetime.now(timezone.utc).isoformat(),
            additional_coordinator_context=self.settings.additional_coordinator_context,
        )
        request_messages = [SystemMessage(content=coordinator_prompt)] + messages

        coordinator_response = await self.timeout_handler.invoke_with_timeout(self.coordinator_model, request_messages)

        current_agent_hops = StateHelpers.safe_get_agent_hops(state)
        plugin_context = StateHelpers.get_plugin_context(state)
        is_routing_to_agent = self.router.has_tool_calls({AgentStateFields.MESSAGES: [coordinator_response]})

        if is_routing_to_agent:
            tool_calls = getattr(coordinator_response, "tool_calls", [])
            if tool_calls:
                current_agent_hops = RouteCounter.calculate_agent_hops(current_agent_hops, tool_calls)
                plugin_context = RouteCounter.update_same_agent_route_counter(plugin_context, tool_calls)
        else:
            self.logger.warning("Coordinator was self-answering the question. This is not the expected behaviour")
            if not self.settings.allowed_coordinator_terminate:
                coordinator_response.content = ""
                coordinator_response.tool_calls = [ToolCall(id=str(uuid.uuid4()), name="goto_synthesize", args={})]
            plugin_context = RouteCounter.reset_route_counters(plugin_context)

        return StateHelpers.create_state_update(
            coordinator_response, current_agent_hops, StateHelpers.update_plugin_context(state, **plugin_context)
        )

    def _suspend_node(self, state: AgentState) -> AgentState:
        """Handle graceful conversation termination when hop limits are exceeded."""
        return self.suspend_handler.handle_suspend(state, self.suspend_model)

    def _synthesizer_node(self, state: AgentState) -> AgentState:
        """Synthesize complete conversation into coherent final response."""
        return self.synthesizer_handler.handle_synthesize(state, self.synthesizer_model)

    def _build_plugin_descriptions(self) -> str:
        """Build formatted string of available plugin descriptions."""
        descriptions = []
        for plugin_bundle in self.plugin_manager.plugin_bundles.values():
            descriptions.append(
                f"- **{plugin_bundle.metadata.name}**: {plugin_bundle.metadata.description}. No params are required."
            )
        return "\n".join(descriptions)

    def _build_tool_options(self) -> str:
        """Build formatted string of available tool options."""
        tool_names = [
            f"goto_{plugin_bundle.metadata.name}" for plugin_bundle in self.plugin_manager.plugin_bundles.values()
        ]
        return " | ".join(tool_names)
