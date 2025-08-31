"""Multi-agent conversation orchestrator using LangGraph.

Builds sequential, tool-routed conversation graphs with plugin integration
and infinite loop prevention through hop counters.
"""

import traceback
from enum import Enum
from typing import Any, Dict, List

from cadence_sdk.base.loggable import Loggable
from cadence_sdk.types import AgentState
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import StateGraph
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
    END = "end"
    FINAL = "final"


class ConversationPrompts:
    """System prompts for different conversation roles."""

    COORDINATOR_INSTRUCTIONS = """Your goal is to analyze queries and decide which agent to route to from the **AVAILABLE AGENTS**.
**AVAILABLE AGENTS**
{plugin_descriptions}
- finalize: Call when you think the answer for the user query/question is ready or no suitable agents.
**DECISION OUTPUT**
- Choose ONE of: {tool_options} | goto_finalize"""

    HOP_LIMIT_REACHED = """You have reached maximum agent call ({current}/{maximum}) allowed by the system.
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
Please provide a helpful response that addresses the user's query while explaining the hop limit situation."""

    FINALIZER_INSTRUCTIONS = """You are the Finalizer, responsible for creating the final response for a multi-agent conversation.

CRITICAL REQUIREMENTS:
1. **RESPECT AGENT RESPONSES** - Use ONLY the information provided by agents and tools, do NOT make up or add information
2. **ADDRESS CURRENT USER QUERY** - Focus on answering the recent user question, use previous conversation as context
3. **SYNTHESIZE RELEVANT WORK** - Connect and organize the work done by different agents into a coherent answer
4. **BE HELPFUL** - Provide useful, actionable information that directly answers the user's question
5. **RESPONSE STYLE**: {tone_instruction}

IMPORTANT: Your role is to synthesize and present the information that agents have gathered, not to generate new information or make assumptions beyond what's provided in the conversation."""


class ToolExecutionLogger(BaseCallbackHandler):
    """Logs tool execution and manages hop counting for conversation safety."""

    def __init__(self, logger, state_updater=None):
        self.logger = logger
        self.state_updater = state_updater

    def on_tool_start(self, serialized=None, input_str=None, **kwargs):
        """Log tool execution start and update hop counters for non-routing tools."""
        try:
            tool_name = serialized.get("name") if isinstance(serialized, dict) else None
            self.logger.debug(f"Tool start: name={tool_name or 'unknown'} input={input_str}")

            if tool_name.startswith("goto_"):
                self.logger.debug(f"Tool name={tool_name or 'unknown'} is skipped from counting")
            elif self.state_updater:
                self.logger.debug(f"Updating tool_hops: +1 (tool: {tool_name})")
                self.state_updater("tool_hops", 1)
            else:
                self.logger.warning("No state_updater available for tool_hops tracking")
        except Exception as e:
            self.logger.error(f"Error in on_tool_start: {e}")

    def on_tool_end(self, output=None, **kwargs):
        """Log tool execution completion."""
        try:
            output_preview = str(output)[:200] if output else None
            self.logger.debug(f"Tool end: output={output_preview}")
        except Exception:
            pass


class MultiAgentOrchestrator(Loggable):
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
        self.finalizer_model = self._create_finalizer_model()
        self.graph = self._build_conversation_graph()

    def _create_coordinator_model(self):
        """Create LLM model for coordinator with bound routing tools."""
        from ...infrastructure.llm.providers import ModelConfig

        control_tools = self.plugin_manager.get_coordinator_tools()
        model_config = ModelConfig(
            provider=self.settings.default_llm_provider,
            model_name=self.settings.get_default_provider_llm_model(),
            temperature=self.settings.default_llm_temperature,
            max_tokens=self.settings.default_llm_context_window,
        )

        base_model = self.llm_factory.create_base_model(model_config)

        return base_model.bind_tools(control_tools, parallel_tool_calls=True)

    def _create_finalizer_model(self):
        """Create LLM model for synthesizing final responses."""
        from ...infrastructure.llm.providers import ModelConfig

        model_config = ModelConfig(
            provider=self.settings.finalizer_llm_provider,
            model_name=self.settings.get_finalizer_provider_llm_model(),
            temperature=self.settings.finalizer_temperature,
            max_tokens=self.settings.finalizer_max_tokens,
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
            self.logger.info("Rebuilding orchestrator graph after plugin changes...")
            self.graph = self._build_conversation_graph()
            self.logger.info("Graph rebuilt successfully")
        except Exception as e:
            self.logger.error(f"Failed to rebuild graph: {e}")
            raise

    async def ask(self, state: AgentState) -> AgentState:
        """Process conversation state through multi-agent workflow."""
        try:
            return await self.graph.ainvoke(state)
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
                RoutingDecision.END: GraphNodeNames.FINALIZER,
                RoutingDecision.SUSPEND: GraphNodeNames.SUSPEND,
            },
        )

    def _add_control_tools_routing_edges(self, graph: StateGraph) -> None:
        """Add conditional edges from control tools to plugin agents and finalizer."""
        route_mapping = {}

        for plugin_bundle in self.plugin_manager.plugin_bundles.values():
            route_mapping[plugin_bundle.metadata.name] = f"{plugin_bundle.metadata.name}_agent"

        route_mapping[RoutingDecision.END] = GraphNodeNames.FINALIZER

        graph.add_conditional_edges(GraphNodeNames.CONTROL_TOOLS, self._determine_plugin_route, route_mapping)

    def _add_plugin_routing_edges(self, graph: StateGraph) -> None:
        """Add edges from plugin agents back to coordinator."""
        for plugin_bundle in self.plugin_manager.plugin_bundles.values():
            plugin_name = plugin_bundle.metadata.name

            graph.add_edge(f"{plugin_name}_agent", f"{plugin_name}_tools")
            graph.add_edge(f"{plugin_name}_tools", GraphNodeNames.COORDINATOR)

    def _coordinator_routing_logic(self, state: AgentState) -> str:
        """Determine next step in conversation flow based on current state."""
        if self._is_hop_limit_reached(state):
            self.logger.debug("Routing to SUSPEND due to hop limit reached")
            return RoutingDecision.SUSPEND
        elif self._has_tool_calls(state):
            self.logger.debug("Routing to CONTINUE due to tool calls present")
            return RoutingDecision.CONTINUE
        else:
            self.logger.debug("Routing to END - no tool calls and hop limit not reached")
            return RoutingDecision.END

    def _is_hop_limit_reached(self, state: AgentState) -> bool:
        """Check if conversation has reached maximum allowed agent hops."""
        agent_hops = state.get("agent_hops", 0)
        max_agent_hops = self.settings.max_agent_hops
        return agent_hops >= max_agent_hops

    def _has_tool_calls(self, state: AgentState) -> bool:
        """Check if last message contains tool calls that need processing."""
        messages = state.get("messages", [])
        if not messages:
            self.logger.debug("No messages in state")
            return False

        last_message = messages[-1]
        tool_calls = getattr(last_message, "tool_calls", None)
        has_tool_calls = bool(tool_calls)

        self.logger.debug(f"Last message type: {type(last_message).__name__}, has tool_calls: {has_tool_calls}")
        if has_tool_calls:
            self.logger.debug(f"Tool calls found: {len(tool_calls)} calls")
            for i, tc in enumerate(tool_calls):
                self.logger.debug(f"  Tool call {i}: {getattr(tc, 'name', 'unknown')}")

        return has_tool_calls

    def _determine_plugin_route(self, state: AgentState) -> str:
        """Route to appropriate plugin agent based on tool results."""
        messages = state.get("messages", [])
        if not messages:
            return RoutingDecision.END

        last_message = messages[-1]

        if not self._is_valid_tool_message(last_message):
            self.logger.warning("No valid tool message found in routing")
            return RoutingDecision.END

        tool_result = last_message.content
        self.logger.debug(
            f"Tool routing: tool_result='{tool_result}', available_plugins={[bundle.metadata.name for bundle in self.plugin_manager.plugin_bundles.values()]}"
        )

        if tool_result in [
            plugin_bundle.metadata.name for plugin_bundle in self.plugin_manager.plugin_bundles.values()
        ]:
            return tool_result
        elif tool_result == "finalize":
            return RoutingDecision.END
        else:
            self.logger.warning(f"Unknown tool result: '{tool_result}', routing to END")
            return RoutingDecision.END

    @staticmethod
    def _is_valid_tool_message(message: Any) -> bool:
        """Validate message has required structure for tool routing."""
        return message and hasattr(message, "content")

    def _coordinator_node(self, state: AgentState) -> AgentState:
        """Execute main decision-making step that determines conversation routing."""
        messages = state.get("messages", [])
        plugin_descriptions = self._build_plugin_descriptions()
        tool_options = self._build_tool_options()

        coordinator_prompt = ConversationPrompts.COORDINATOR_INSTRUCTIONS.format(
            plugin_descriptions=plugin_descriptions, tool_options=tool_options
        )

        system_message = SystemMessage(content=coordinator_prompt)
        safe_messages = self._filter_safe_messages(messages)

        coordinator_response = self.coordinator_model.invoke([system_message] + safe_messages)

        return self._create_state_update(coordinator_response, state.get("agent_hops", 0), state)

    def _suspend_node(self, state: AgentState) -> AgentState:
        """Handle graceful conversation termination when hop limits are exceeded."""
        current_hops = state.get("agent_hops", 0)
        max_hops = self.settings.max_agent_hops

        suspension_message = SystemMessage(
            content=ConversationPrompts.HOP_LIMIT_REACHED.format(current=current_hops, maximum=max_hops)
        )

        suspension_response = self._invoke_model_with_prompt(suspension_message, state["messages"])
        return self._create_state_update(suspension_response, current_hops, state)

    def _finalizer_node(self, state: AgentState) -> AgentState:
        """Synthesize complete conversation into coherent final response."""
        messages = state.get("messages", [])
        requested_tone = state.get("tone", "natural") or "natural"
        tone_instruction = self._get_tone_instruction(requested_tone)

        finalization_prompt_content = ConversationPrompts.FINALIZER_INSTRUCTIONS.format(
            tone_instruction=tone_instruction
        )
        finalization_prompt = SystemMessage(content=finalization_prompt_content)

        safe_messages = self._filter_safe_messages(messages)
        final_response = self.finalizer_model.invoke([finalization_prompt] + safe_messages)

        return self._create_state_update(final_response, state.get("agent_hops", 0), state)

    def _get_tone_instruction(self, tone: str) -> str:
        """Return appropriate tone instruction based on requested response style."""
        return ResponseTone.get_description(tone)

    def _update_tool_hops(self, field: str, increment: int) -> None:
        """Update tool hops counter for tool execution logger."""
        self.logger.debug(f"Tool execution logger requested update: {field} += {increment}")

    def _build_plugin_descriptions(self) -> str:
        """Build formatted string of available plugin descriptions."""
        descriptions = []
        for plugin_bundle in self.plugin_manager.plugin_bundles.values():
            descriptions.append(f"- {plugin_bundle.metadata.name}: {plugin_bundle.metadata.description}")
        return "\n".join(descriptions)

    def _build_tool_options(self) -> str:
        """Build formatted string of available tool options."""
        tool_names = [
            f"goto_{plugin_bundle.metadata.name}" for plugin_bundle in self.plugin_manager.plugin_bundles.values()
        ]
        return " | ".join(tool_names)

    def _invoke_model_with_prompt(self, system_prompt: SystemMessage, messages: List) -> AIMessage:
        """Invoke coordinator model with system prompt and conversation messages."""
        safe_messages = self._filter_safe_messages(messages)
        return self.coordinator_model.invoke([system_prompt] + safe_messages)

    def _filter_safe_messages(self, messages: List) -> List:
        """Remove messages with incomplete tool call sequences to prevent validation errors."""
        if not messages:
            return []

        filtered_messages = []
        for message_index, message in enumerate(messages):
            if self._is_incomplete_tool_call_sequence(message, messages, message_index):
                self.logger.warning(f"Skipping incomplete tool call sequence in message {message_index}")
                continue
            filtered_messages.append(message)

        return filtered_messages

    def _is_incomplete_tool_call_sequence(self, message: Any, messages: List, message_index: int) -> bool:
        """Determine if assistant message contains tool calls without proper responses."""
        if not (hasattr(message, "tool_calls") and message.tool_calls and isinstance(message, AIMessage)):
            return False

        tool_call_ids = {tc.get("id") for tc in message.tool_calls if tc.get("id")}
        found_tool_responses = self._find_tool_responses(messages, message_index)

        return not tool_call_ids.issubset(found_tool_responses)

    def _find_tool_responses(self, messages: List, message_index: int) -> set:
        """Search for tool response messages that correspond to tool calls."""
        found_tool_responses = set()
        look_ahead_limit = min(message_index + 10, len(messages))

        for next_message in messages[message_index + 1 : look_ahead_limit]:
            if hasattr(next_message, "tool_call_id") and next_message.tool_call_id:
                found_tool_responses.add(next_message.tool_call_id)

        return found_tool_responses

    @staticmethod
    def _create_state_update(message: AIMessage, agent_hops: int, state: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create standardized state update structure for graph node responses."""
        update = {
            "messages": [message],
            "agent_hops": agent_hops,
        }

        if state:
            for key in ["tool_hops", "current_agent", "plugin_context", "session_id"]:
                if key in state:
                    update[key] = state[key]

        return update
