"""Multi-agent conversation orchestrator using LangGraph.

Builds sequential, tool-routed conversation graphs with plugin integration
and infinite loop prevention through hop counters.
"""

import traceback
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from cadence_sdk.base.loggable import Loggable
from cadence_sdk.types import AgentState
from cadence_sdk.types.state import AgentStateFields, PluginContext, PluginContextFields, RoutingHelpers, StateHelpers
from langchain_core.messages import AIMessage, SystemMessage, ToolCall
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from ...config.settings import Settings
from ...infrastructure.llm.factory import LLMModelFactory
from ...infrastructure.plugins.sdk_manager import SDKPluginManager


class ResponseTone(Enum):
    """Available response styles for conversation finalization."""

    NATURAL = "natural"
    EXPLANATORY = "explanatory"
    FORMAL = "formal"
    CONCISE = "concise"
    LEARNING = "learning"

    @property
    def description(self) -> str:
        """Return detailed description for this tone."""
        descriptions = {
            "natural": "Respond in a friendly, conversational way as if talking to a friend. Use casual language, contractions, and a warm tone. Be helpful and approachable.",
            "explanatory": "Provide detailed, educational explanations that help users understand concepts. Break down complex information into clear, digestible parts. Use examples and analogies when helpful.",
            "formal": "Use professional, structured language with clear organization. Present information in a business-like manner with proper formatting, bullet points, and formal language.",
            "concise": "Keep responses brief and to-the-point. Focus only on essential information. Avoid unnecessary elaboration or repetition.",
            "learning": "Adopt a teaching approach with step-by-step guidance. Structure responses like a lesson with clear progression, examples, and educational explanations.",
        }
        return descriptions.get(self.value, descriptions["natural"])

    @classmethod
    def get_description(cls, tone: str) -> str:
        """Return description for given tone value."""
        try:
            return cls(tone).description
        except ValueError:
            return cls.NATURAL.description


class GraphNodeNames:
    """Names of nodes in the conversation graph."""

    COORDINATOR = "coordinator"
    CONTROL_TOOLS = "control_tools"
    SUSPEND = "suspend"
    FINALIZER = "finalizer"


class RoutingDecision:
    """Possible routing decisions in the conversation flow."""

    CONTINUE = "continue"
    SUSPEND = "suspend"
    DONE = "done"
    TERMINATE = "terminate"


class ConversationPrompts:
    """System prompts for different conversation roles."""

    COORDINATOR_INSTRUCTIONS = """{additional_coordinator_context}, and you also are the Coordinator in a multi-agent conversation system. Your role is to analyze the conversation and determine the next appropriate tool/function call.

**YOUR TASK:**
1. Read and analyze the entire conversation history
2. Understand what the user is asking for
3. Determine which specialized agent should handle the request
4. Call the appropriate tool to route to that tool/function calls

**SYSTEM STATE:**
- Current Time (UTC): {current_time}

Remember: Your job is routing, not answering. Use tool/function calls to delegate to the appropriate specialist agent."""

    HOP_LIMIT_REACHED = """{additional_suspend_context}, your current role is The Friendly Suspender. Current situation is we have reached maximum agent call ({current}/{maximum}) allowed by the system.
**What this means:**
- The system cannot process any more agent switches
- You must provide a final answer based on the information gathered so far
- Further processing is not possible

**What you should do:**
1. Acknowledge that you've hit the system limit. Explain it friendly to users, do not use term system limit or agent stuff
2. Explain what you were able to accomplish base on results.
3. Provide the best possible answer with the available information
4. If the answer is incomplete, explain why and suggest the user continue the chat

**IMPORTANT**, never makeup the answer if provided information by agents not enough

**ADDITIONAL RESPONSE GUIDANCE**:
{plugin_suggestions}

**SYSTEM STATE**:
- Current Time (UTC): {current_time}

**RESPONSE STYLE**: {tone_instruction}
**LANGUAGE**: Respond in the same language as the user's query or as explicitly requested by the user.
Please provide a helpful response that addresses the user's query while explaining the hop limit situation."""

    FINALIZER_INSTRUCTIONS = """{additional_finalizer_context}, your current role is the Finalizer, responsible for creating the final response for a multi-agent conversation.
CRITICAL REQUIREMENTS:
1. **RESPECT AGENT RESPONSES** - Use ONLY the information provided by agents and tools, NEVER make up or add information. Explain errors from agents to user by a friendly way.
2. **ADDRESS CURRENT USER QUERY** - Focus on answering the recent user question, use previous conversation as context
3. **SYNTHESIZE RELEVANT WORK** - Connect and organize the work done by work done in each step for answer
4. **BE HELPFUL** - Provide useful, actionable information that directly answers the user's question
5. **RESPONSE STYLE**: {tone_instruction}
6. **LANGUAGE**: Respond in the same language as the current user's query or as explicitly requested by the user.
7. **MARKDOWN FORMAT**: Format your response using proper markdown syntax for better readability

**ADDITIONAL RESPONSE GUIDANCE**:
{plugin_suggestions}

**SYSTEM STATE**:
- Current Time (UTC): {current_time}

IMPORTANT: Your role is to synthesize and present the information that agents have gathered. Use markdown formatting for structure and readability."""


class AgentCoordinator(Loggable):
    """Coordinates multi-agent conversations using LangGraph with dynamic plugin integration."""

    def __init__(
        self,
        plugin_manager: SDKPluginManager,
        llm_factory: LLMModelFactory,
        settings: Settings,
        checkpointer: Any | None = None,
    ) -> None:
        super().__init__()
        self.plugin_manager = plugin_manager
        self.llm_factory = llm_factory
        self.settings = settings
        self.checkpointer = checkpointer

        self.coordinator_model = self._create_coordinator_model()
        self.suspend_model = self._create_suspend_model()
        self.finalizer_model = self._create_finalizer_model()
        self.graph = self._build_conversation_graph()

    def _create_coordinator_model(self):
        """Create LLM model for coordinator with bound routing tools."""
        from ...infrastructure.llm.providers import ModelConfig

        control_tools = self.plugin_manager.get_coordinator_tools()

        provider = self.settings.coordinator_llm_provider or self.settings.default_llm_provider
        model_name = self.settings.get_default_provider_llm_model(provider)
        temperature = self.settings.coordinator_temperature
        max_tokens = self.settings.coordinator_max_tokens

        model_config = ModelConfig(
            provider=provider,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        base_model = self.llm_factory.create_base_model(model_config)
        return base_model.bind_tools(control_tools, parallel_tool_calls=self.settings.coordinator_parallel_tool_calls)

    def _create_suspend_model(self):
        """Create LLM model for suspend node with fallback to default."""
        from ...infrastructure.llm.providers import ModelConfig

        provider = self.settings.suspend_llm_provider or self.settings.default_llm_provider
        model_name = self.settings.get_default_provider_llm_model(provider)
        temperature = self.settings.suspend_temperature
        max_tokens = self.settings.suspend_max_tokens

        model_config = ModelConfig(
            provider=provider,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return self.llm_factory.create_base_model(model_config)

    def _create_finalizer_model(self):
        """Create LLM model for synthesizing final responses."""
        from ...infrastructure.llm.providers import ModelConfig

        provider = self.settings.finalizer_llm_provider or self.settings.default_llm_provider
        model_name = self.settings.get_finalizer_provider_llm_model(provider)
        temperature = self.settings.finalizer_temperature
        max_tokens = self.settings.finalizer_max_tokens

        model_config = ModelConfig(
            provider=provider,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return self.llm_factory.create_base_model(model_config)

    def _build_conversation_graph(self) -> StateGraph:
        """Construct LangGraph workflow for multi-agent orchestration."""
        graph = StateGraph(AgentState)

        self._add_core_orchestration_nodes(graph)
        self._add_dynamic_plugin_nodes(graph)

        graph.set_entry_point(GraphNodeNames.COORDINATOR)
        self._add_conditional_routing_edges(graph)

        compilation_options = {"checkpointer": self.checkpointer} if self.checkpointer else {}
        compiled_graph = graph.compile(**compilation_options)

        self.logger.debug(f"Graph built with \n{compiled_graph.get_graph().draw_mermaid()}")
        return compiled_graph

    def rebuild_graph(self) -> None:
        """Rebuild conversation graph after plugin changes."""
        try:
            self.logger.debug("Rebuilding orchestrator graph after plugins change/reload ...")
            self.coordinator_model = self._create_coordinator_model()
            self.suspend_model = self._create_suspend_model()
            self.finalizer_model = self._create_finalizer_model()
            self.graph = self._build_conversation_graph()
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

    def _add_core_orchestration_nodes(self, graph: StateGraph) -> None:
        """Add core orchestration nodes to conversation graph."""
        graph.add_node(GraphNodeNames.COORDINATOR, self._coordinator_node)
        graph.add_node(GraphNodeNames.CONTROL_TOOLS, ToolNode(tools=self.plugin_manager.get_coordinator_tools()))
        graph.add_node(GraphNodeNames.SUSPEND, self._suspend_node)
        graph.add_node(GraphNodeNames.FINALIZER, self._finalizer_node)

    def _add_dynamic_plugin_nodes(self, graph: StateGraph) -> None:
        """Dynamically add plugin nodes and connections to graph."""
        for plugin_bundle in self.plugin_manager.plugin_bundles.values():
            plugin_name = plugin_bundle.metadata.name

            graph.add_node(f"{plugin_name}_agent", plugin_bundle.agent_node)
            graph.add_node(f"{plugin_name}_tools", plugin_bundle.tool_node)

    def _add_conditional_routing_edges(self, graph: StateGraph) -> None:
        """Add conditional routing edges between graph nodes."""
        self._add_coordinator_routing_edges(graph)
        self._add_control_tools_routing_edges(graph)
        self._add_plugin_routing_edges(graph)

    def _add_coordinator_routing_edges(self, graph: StateGraph) -> None:
        """Add conditional edges from coordinator to other nodes."""
        graph.add_conditional_edges(
            GraphNodeNames.COORDINATOR,
            self._coordinator_routing_logic,
            {
                RoutingDecision.CONTINUE: GraphNodeNames.CONTROL_TOOLS,
                RoutingDecision.DONE: GraphNodeNames.FINALIZER,
                RoutingDecision.SUSPEND: GraphNodeNames.SUSPEND,
                RoutingDecision.TERMINATE: END,
            },
        )
        graph.add_edge(GraphNodeNames.SUSPEND, END)
        graph.add_edge(GraphNodeNames.FINALIZER, END)

    def _add_control_tools_routing_edges(self, graph: StateGraph) -> None:
        """Add conditional edges from control tools to plugin agents and finalizer."""
        route_mapping = {}

        for plugin_bundle in self.plugin_manager.plugin_bundles.values():
            route_mapping[plugin_bundle.metadata.name] = f"{plugin_bundle.metadata.name}_agent"

        route_mapping[RoutingDecision.DONE] = GraphNodeNames.FINALIZER

        graph.add_conditional_edges(GraphNodeNames.CONTROL_TOOLS, self._determine_plugin_route, route_mapping)

    def _add_plugin_routing_edges(self, graph: StateGraph) -> None:
        """Add edges from plugin agents back to coordinator using bundle edge definitions."""
        for plugin_bundle in self.plugin_manager.plugin_bundles.values():
            edges = plugin_bundle.get_graph_edges()

            self.logger.debug(f"Adding edges for plugin {plugin_bundle.metadata.name}: {edges}")

            for node_name, edge_config in edges["conditional_edges"].items():
                self.logger.debug(f"Adding conditional edge: {node_name} -> {edge_config['mapping']}")
                graph.add_conditional_edges(node_name, edge_config["condition"], edge_config["mapping"])

            for from_node, to_node in edges["direct_edges"]:
                self.logger.debug(f"Adding direct edge: {from_node} -> {to_node}")
                graph.add_edge(from_node, to_node)

    def _coordinator_routing_logic(self, state: AgentState) -> str:
        """Determine next step in conversation flow based on current state."""
        if self._is_hop_limit_reached(state):
            self.logger.debug("Routing to SUSPEND due to hop limit reached")
            return RoutingDecision.SUSPEND
        elif self._is_consecutive_agent_route_limit_reached(state):
            self.logger.debug("Routing to SUSPEND due to consecutive coordinator->agent routing limit reached")
            return RoutingDecision.SUSPEND
        elif self._has_tool_calls(state):
            self.logger.debug("Routing to CONTINUE due to tool calls present")
            return RoutingDecision.CONTINUE
        elif self.settings.allowed_coordinator_terminate:
            self.logger.debug("Routing to TERMINATE - coordinator allowed to terminate directly")
            return RoutingDecision.TERMINATE
        else:
            self.logger.debug("Routing to DONE - no tool calls, routing through finalizer")
            return RoutingDecision.DONE

    def _is_hop_limit_reached(self, state: AgentState) -> bool:
        """Check if conversation has reached maximum allowed agent hops."""
        agent_hops = StateHelpers.safe_get_agent_hops(state)
        max_agent_hops = self.settings.max_agent_hops
        return agent_hops >= max_agent_hops

    def _is_consecutive_agent_route_limit_reached(self, state: AgentState) -> bool:
        """Check if coordinator has routed to the SAME agent too many times consecutively.

        Tracks only coordinator tool routes to agents (excludes finalize) and
        requires that the selected agent is the same across consecutive decisions.
        """
        try:
            plugin_context = StateHelpers.get_plugin_context(state)
            same_agent_count = plugin_context.get(PluginContextFields.CONSECUTIVE_AGENT_REPEATS, 0)
            limit = int(self.settings.coordinator_consecutive_agent_route_limit or 0)
            reached = 0 < limit <= same_agent_count
        except Exception:
            reached = False
        self.logger.debug(
            f"Same-agent consecutive route check: count={same_agent_count}, limit={limit}, reached={reached}"
        )
        return reached

    def _has_tool_calls(self, state: AgentState) -> bool:
        """Check if last message contains tool calls that need processing."""
        messages = StateHelpers.safe_get_messages(state)
        if not messages:
            self.logger.debug("No messages in state")
            return False

        last_message = messages[-1]
        tool_calls = getattr(last_message, "tool_calls", None)
        has_tool_calls = bool(tool_calls)

        self.logger.debug(f"Tool calls found: {len(tool_calls)} calls")
        for i, tc in enumerate(tool_calls):
            self.logger.debug(f"  Tool call {i}: {getattr(tc, 'name', 'unknown')}")

        return has_tool_calls

    def _determine_plugin_route(self, state: AgentState) -> str:
        """Route to appropriate plugin agent based on tool results."""
        messages = StateHelpers.safe_get_messages(state)
        if not messages:
            return RoutingDecision.DONE

        last_message = messages[-1]

        if not self._is_valid_tool_message(last_message):
            self.logger.warning("No valid tool message found in routing")
            return RoutingDecision.DONE

        tool_result = last_message.content

        if tool_result in [
            plugin_bundle.metadata.name for plugin_bundle in self.plugin_manager.plugin_bundles.values()
        ]:
            return tool_result
        elif tool_result == "finalize":
            return RoutingDecision.DONE
        else:
            self.logger.warning(f"Unknown tool result: '{tool_result}', routing to DONE")
            return RoutingDecision.DONE

    @staticmethod
    def _is_valid_tool_message(message: Any) -> bool:
        """Validate message has required structure for tool routing."""
        return message and hasattr(message, "content")

    def _coordinator_node(self, state: AgentState) -> AgentState:
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

        coordinator_response = self.coordinator_model.invoke(request_messages)

        current_agent_hops = StateHelpers.safe_get_agent_hops(state)
        plugin_context = StateHelpers.get_plugin_context(state)
        is_routing_to_agent = self._has_tool_calls({AgentStateFields.MESSAGES: [coordinator_response]})

        if is_routing_to_agent:
            tool_calls = getattr(coordinator_response, "tool_calls", [])
            if tool_calls:
                current_agent_hops = self.calculate_agent_hops(current_agent_hops, tool_calls)
                plugin_context = self._update_same_agent_route_counter(plugin_context, tool_calls)
        else:
            self.logger.warning("Coordinator was self-answering the question. This is not the expected behaviour")
            if not self.settings.allowed_coordinator_terminate:
                coordinator_response.content = ""
                coordinator_response.tool_calls = [ToolCall(id=str(uuid.uuid4()), name="goto_finalize", args={})]
            plugin_context = self._reset_route_counters(plugin_context)

        # Use StateHelpers for safe state update
        return StateHelpers.create_state_update(
            coordinator_response, current_agent_hops, StateHelpers.update_plugin_context(state, **plugin_context)
        )

    @staticmethod
    def calculate_agent_hops(current_agent_hops, tool_calls):

        def _get_name(tc):
            try:
                if isinstance(tc, dict):
                    return tc.get("name")
                return getattr(tc, "name", None)
            except Exception:
                return None

        potential_tool_calls = [_get_name(tc) for tc in tool_calls]
        for potential_tool_call in potential_tool_calls:
            if potential_tool_call and potential_tool_call != "goto_finalize":
                current_agent_hops += 1
        return current_agent_hops

    @staticmethod
    def _reset_route_counters(plugin_context: PluginContext) -> PluginContext:
        """Reset route counters using RoutingHelpers."""
        return RoutingHelpers.update_consecutive_routes(plugin_context, "goto_finalize")

    @staticmethod
    def _update_same_agent_route_counter(
        plugin_context: PluginContext, tool_calls: List[Dict[str, Any]]
    ) -> PluginContext:
        """Update route counter using RoutingHelpers."""
        routed_tools = [tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "") for tc in tool_calls]
        selected_tool = routed_tools[0] if routed_tools else ""

        # Update consecutive routes and add to routing history
        updated_context = RoutingHelpers.update_consecutive_routes(plugin_context, selected_tool)
        if selected_tool:
            updated_context = RoutingHelpers.add_to_routing_history(updated_context, selected_tool)

        return updated_context

    def _suspend_node(self, state: AgentState) -> AgentState:
        """Handle graceful conversation termination when hop limits are exceeded."""
        current_hops = StateHelpers.safe_get_agent_hops(state)
        max_hops = self.settings.max_agent_hops
        metadata = StateHelpers.safe_get_metadata(state)
        requested_tone = metadata.get("tone", "natural") or "natural"
        tone_instruction = self._get_tone_instruction(requested_tone)

        # Collect response suggestions from used plugins
        plugin_context = StateHelpers.get_plugin_context(state)
        routing_history = plugin_context.get(PluginContextFields.ROUTING_HISTORY, [])
        used_plugins = list(set(routing_history))
        plugin_suggestions = self._collect_plugin_suggestions(used_plugins)
        suggestions_text = self._format_plugin_suggestions(plugin_suggestions)

        suspension_message = SystemMessage(
            content=ConversationPrompts.HOP_LIMIT_REACHED.format(
                current=current_hops,
                maximum=max_hops,
                tone_instruction=tone_instruction,
                current_time=datetime.now(timezone.utc).isoformat(),
                additional_suspend_context=self.settings.additional_suspend_context,
                plugin_suggestions=suggestions_text,
            )
        )

        safe_messages = self._filter_safe_messages(state[AgentStateFields.MESSAGES])
        suspension_response = self._get_structured_suspend_response([suspension_message] + safe_messages, used_plugins)
        return StateHelpers.create_state_update(suspension_response, current_hops, state)

    def _finalizer_node(self, state: AgentState) -> AgentState:
        """Synthesize complete conversation into coherent final response."""
        messages = StateHelpers.safe_get_messages(state)
        metadata = StateHelpers.safe_get_metadata(state)
        requested_tone = metadata.get("tone", "natural") or "natural"
        tone_instruction = self._get_tone_instruction(requested_tone)

        plugin_context = StateHelpers.get_plugin_context(state)
        routing_history = plugin_context.get(PluginContextFields.ROUTING_HISTORY, [])
        used_plugins = list(set(routing_history))

        plugin_suggestions = self._collect_plugin_suggestions(used_plugins)
        suggestions_text = self._format_plugin_suggestions(plugin_suggestions)

        finalization_prompt_content = ConversationPrompts.FINALIZER_INSTRUCTIONS.format(
            tone_instruction=tone_instruction,
            current_time=datetime.now(timezone.utc).isoformat(),
            additional_finalizer_context=self.settings.additional_finalizer_context,
            plugin_suggestions=suggestions_text,
        )
        finalization_prompt = SystemMessage(content=finalization_prompt_content)

        if self.settings.enable_structured_finalizer and used_plugins:
            try:
                model_binder = self.plugin_manager.get_model_binder()
                structured_model, is_structured = model_binder.get_structured_model(self.finalizer_model, used_plugins)

                if is_structured:
                    structured_response = structured_model.invoke([finalization_prompt] + messages)

                    if isinstance(structured_response, dict) and "response" in structured_response:
                        response_content = structured_response["response"]
                        if "additional_data" in structured_response:
                            additional_data = structured_response["additional_data"]
                            data_sources = list(additional_data.keys()) if isinstance(additional_data, dict) else []

                            plugin_context[PluginContextFields.FINALIZER_OUTPUT] = {
                                "response": response_content,
                                "additional_data": additional_data,
                                "data_sources": data_sources,
                            }

                        final_response = AIMessage(content=response_content)
                    else:
                        final_response = self.finalizer_model.invoke([finalization_prompt] + messages)
                else:
                    final_response = self.finalizer_model.invoke([finalization_prompt] + messages)

            except Exception as e:
                self.logger.warning(f"Structured output failed: {e}")
                final_response = self.finalizer_model.invoke([finalization_prompt] + messages)
        else:
            final_response = self.finalizer_model.invoke([finalization_prompt] + messages)

        updated_state = StateHelpers.update_plugin_context(state, **plugin_context)
        return StateHelpers.create_state_update(final_response, StateHelpers.safe_get_agent_hops(state), updated_state)

    def get_structured_output(self, state: AgentState) -> Optional[Dict[str, Any]]:
        """Get the structured output from finalizer if available."""
        plugin_context = StateHelpers.get_plugin_context(state)
        return plugin_context.get(PluginContextFields.FINALIZER_OUTPUT)

    @staticmethod
    def _get_tone_instruction(tone: str) -> str:
        """Return appropriate tone instruction based on requested response style."""
        return ResponseTone.get_description(tone)

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

    def _collect_plugin_suggestions(self, used_plugins: List[str]) -> Dict[str, str]:
        """Collect response suggestions from plugins that were used during the conversation."""
        suggestions = {}

        for plugin_name in used_plugins:
            plugin_bundle = self.plugin_manager.plugin_bundles.get(plugin_name)
            if plugin_bundle and plugin_bundle.metadata.response_suggestion:
                suggestions[plugin_name] = plugin_bundle.metadata.response_suggestion
                self.logger.debug(
                    f"Collected suggestion from {plugin_name}: {plugin_bundle.metadata.response_suggestion[:100]}..."
                )

        return suggestions

    @staticmethod
    def _format_plugin_suggestions(plugin_suggestions: Dict[str, str]) -> str:
        """Format plugin suggestions for inclusion in the finalizer prompt."""
        if not plugin_suggestions:
            return ""

        formatted_suggestions = []
        for plugin_name, suggestion in plugin_suggestions.items():
            formatted_suggestions.append(f"- **{plugin_name}**: {suggestion}")

        return "\n".join(formatted_suggestions)

    def _get_structured_suspend_response(self, request_messages: List, used_plugins: List[str]) -> Any:
        """Get structured suspend response with plugin suggestions."""
        try:
            if used_plugins:
                model_binder = self.plugin_manager.get_model_binder()
                structured_model, is_structured = model_binder.get_structured_model(self.suspend_model, used_plugins)

                if is_structured:
                    structured_response = structured_model.invoke(request_messages)

                    if isinstance(structured_response, dict) and "response" in structured_response:
                        response_content = structured_response["response"]
                        return AIMessage(content=response_content)
                    else:
                        self.logger.warning(
                            "Structured suspend response format unexpected, falling back to regular model"
                        )
                        return self.suspend_model.invoke(request_messages)
                else:
                    return self.suspend_model.invoke(request_messages)
            else:
                return self.suspend_model.invoke(request_messages)

        except Exception as e:
            self.logger.warning(f"Structured suspend output failed: {e}")
            return self.suspend_model.invoke(request_messages)

    @staticmethod
    def _filter_safe_messages(messages: List) -> List:
        """Remove messages with incomplete tool call sequences to prevent validation errors."""
        if not messages:
            return []
        last_message = messages[-1]
        if isinstance(last_message, AIMessage):
            messages.pop()
            return messages
        else:
            return messages
