"""LangGraph supervisor orchestrator — full 7-node implementation.

Nodes:
1. supervisor       — tool selection / routing decision
2. control_tools    — plugin tool execution via ToolNode
3. validation       — LLM validation of tool results (optional)
4. synthesizer      — final response generation
5. facilitator      — clarifying questions for unclear intent
6. conversational   — context-only queries (translate, summarise, chat)
7. error_handler    — graceful failure recovery

Routing:
START → supervisor
supervisor → [control_tools | facilitator | conversational | error_handler]
control_tools → [validation | error_handler]
validation → [synthesizer | facilitator | error_handler]
synthesizer → [END | error_handler]
facilitator → [END | error_handler]
conversational → [END | error_handler]
error_handler → END
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from cadence.constants import DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE
from cadence.engine.impl.langgraph.graph_state import GraphState
from cadence.engine.impl.langgraph.orchestrator_adapter import LangChainAdapter
from cadence.engine.impl.langgraph.orchestrator_base import BaseLangGraphOrchestrator
from cadence.engine.impl.langgraph.streaming_wrapper import LangGraphStreamingWrapper
from cadence.engine.impl.langgraph.supervisor.prompts import SupervisorPrompts
from cadence.engine.impl.langgraph.supervisor.settings import NodeConfig
from cadence.engine.impl.langgraph.supervisor.tool_collector import (
    SupervisorToolCollector,
)
from cadence.engine.modes import SupervisorMode
from cadence.engine.utils.plugin_utils import (
    build_all_plugins_description,
    build_tool_descriptions,
)
from cadence.infrastructure.plugins import SDKPluginManager

logger = logging.getLogger(__name__)

_SUPERVISOR_RECURSION_BUFFER = 10
_TIMEOUT_FALLBACK_PREFIX = "FKR_"


class ValidationResponse(BaseModel):
    """Structured validation result from the validation node."""

    is_valid: bool = Field(description="Whether validation passed")
    valid_plugin_resources: str = Field(
        default="", description="Comma-separated list of valid plugin resource names"
    )
    valid_ids: Optional[List[str]] = Field(
        default=None, description="IDs of results that passed validation"
    )
    clarification_type: List[str] = Field(
        default_factory=list,
        description="Clarification types needed when invalid",
    )
    reasoning: str = Field(description="Explanation of the validation decision")
    query_intent: str = Field(default="", description="User's query intent")


class LangGraphSupervisor(BaseLangGraphOrchestrator):
    """LangGraph supervisor mode — full 7-node workflow.

    In supervisor mode all plugin tools are bound to a single model.
    The supervisor decides which tools to call (or routes to facilitator /
    conversational) based on the user query.
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
        self.mode_config = SupervisorMode(resolved_config.get("mode_config", {}))
        self._tool_collector: Optional[SupervisorToolCollector] = None
        self._supervisor_model: Any = None
        self._synthesizer_model: Any = None
        self._validation_model: Any = None
        self._error_model: Any = None

    # ------------------------------------------------------------------ #
    # Initialisation
    # ------------------------------------------------------------------ #

    async def initialize(self) -> None:
        """Build all models and the LangGraph workflow."""
        try:
            self._tool_collector = SupervisorToolCollector(self._plugin_bundles)
            await self._setup_models()
            self.graph = self._build_supervisor_graph()
            self._is_ready = True
            logger.info("LangGraph supervisor (7-node) initialised successfully")
        except Exception as e:
            logger.error(
                "Failed to initialise LangGraph supervisor: %s", e, exc_info=True
            )
            raise

    async def _setup_models(self) -> None:
        """Create LLM instances for each node that needs one."""
        all_tools = self._tool_collector.collect_all_tools()
        routing_tools = all_tools + [
            self._create_facilitator_tool(),
            self._create_conversational_tool(),
        ]

        base_supervisor = await self._create_model_for_node(
            self.mode_config.settings.supervisor_node
        )
        self._supervisor_model = base_supervisor.bind_tools(
            routing_tools,
            parallel_tool_calls=self.mode_config.parallel_tool_calls,
        )

        self._synthesizer_model = await self._create_model_for_node(
            self.mode_config.settings.synthesizer_node
        )

        if self.mode_config.use_llm_validation:
            validation_base = await self._create_model_for_node(
                self.mode_config.settings.validation_node,
                temperature=0.0,
            )
            try:
                self._validation_model = validation_base.with_structured_output(
                    ValidationResponse
                )
            except Exception:
                logger.warning(
                    "Could not bind ValidationResponse schema; falling back to base model"
                )
                self._validation_model = validation_base

        self._error_model = await self._create_model_for_node(
            self.mode_config.settings.error_handler_node
        )

    async def _create_model_for_node(
        self,
        node_config: NodeConfig,
        temperature: Optional[float] = None,
    ) -> Any:
        """Create an LLM instance for a specific node via the factory.

        Resolution order:
        1. node_config.llm_config_id — node-specific override
        2. resolved_config["default_llm_config_id"] — instance-level default
        3. Raise ValueError — no LLM config available

        Args:
            node_config: Per-node configuration with optional llm_config_id
            temperature: Override temperature (uses resolved_config default if None)

        Returns:
            Configured LLM instance

        Raises:
            ValueError: If no llm_config_id can be resolved
        """
        temp = (
            temperature
            if temperature is not None
            else self.resolved_config.get("temperature", DEFAULT_TEMPERATURE)
        )
        max_tok = self.resolved_config.get("max_tokens", DEFAULT_MAX_TOKENS)
        org_id = self.resolved_config.get("org_id", "")

        config_id = node_config.llm_config_id or self.resolved_config.get(
            "default_llm_config_id"
        )
        if not config_id:
            raise ValueError(
                f"No llm_config_id for node and no default_llm_config_id on "
                f"instance (org={org_id})"
            )

        model_name = node_config.model_name or self.resolved_config.get(
            "default_model_name"
        )
        if not model_name:
            raise ValueError(
                f"No model_name for node and no default_model_name on "
                f"instance (org={org_id})"
            )

        return await self.llm_factory.create_model_by_id(
            org_id, config_id, model_name, temp, max_tok
        )

    # ------------------------------------------------------------------ #
    # Graph construction
    # ------------------------------------------------------------------ #

    def _build_supervisor_graph(self) -> Any:
        """Construct and compile the 7-node StateGraph."""
        all_tools = self._tool_collector.collect_all_tools()
        tool_node = ToolNode(all_tools)

        workflow = StateGraph(GraphState)

        workflow.add_node("supervisor", self._supervisor_node)
        workflow.add_node("control_tools", tool_node)
        workflow.add_node("validation", self._validation_node)
        workflow.add_node("synthesizer", self._synthesizer_node)
        workflow.add_node("facilitator", self._facilitator_node)
        workflow.add_node("conversational", self._conversational_node)
        workflow.add_node("error_handler", self._error_handler_node)

        workflow.add_edge(START, "supervisor")

        workflow.add_conditional_edges(
            "supervisor",
            self._route_from_supervisor,
            {
                "control_tools": "control_tools",
                "facilitator": "facilitator",
                "conversational": "conversational",
                "synthesizer": "synthesizer",
                "error_handler": "error_handler",
            },
        )

        workflow.add_conditional_edges(
            "control_tools",
            self._route_from_control_tools,
            {"validation": "validation", "error_handler": "error_handler"},
        )

        workflow.add_conditional_edges(
            "validation",
            self._route_from_validation,
            {
                "synthesizer": "synthesizer",
                "facilitator": "facilitator",
                "error_handler": "error_handler",
            },
        )

        workflow.add_conditional_edges(
            "synthesizer",
            self._route_from_synthesizer,
            {"end": END, "error_handler": "error_handler"},
        )

        workflow.add_conditional_edges(
            "facilitator",
            self._route_from_facilitator,
            {"end": END, "error_handler": "error_handler"},
        )

        workflow.add_conditional_edges(
            "conversational",
            self._route_from_conversational,
            {"end": END, "error_handler": "error_handler"},
        )

        workflow.add_edge("error_handler", END)

        return workflow.compile()

    # ------------------------------------------------------------------ #
    # Routing tools (signal-only, no real execution)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _create_facilitator_tool() -> Any:
        """Create a signal tool that triggers routing to the facilitator node."""

        @tool
        def call_facilitator(reason: str = "") -> str:
            """Signal the supervisor to ask the user for clarification. Use when:
            1. User intent is unclear or ambiguous.
            2. Required parameters are missing for tool execution.
            3. Query is too vague to proceed with data tools."""
            return reason or "facilitate"

        return call_facilitator

    @staticmethod
    def _create_conversational_tool() -> Any:
        """Create a signal tool that triggers routing to the conversational node."""

        @tool
        def call_conversational(task: str = "") -> str:
            """Signal the supervisor that this is a context-only task. Use when:
            1. User asks to translate or reformat a previous answer.
            2. User wants a conversation summary.
            3. User asks meta-questions about the discussion.
            4. No external data or tools are needed."""
            return task or "conversational"

        return call_conversational

    # ------------------------------------------------------------------ #
    # Node implementations
    # ------------------------------------------------------------------ #

    async def _supervisor_node(self, state: GraphState) -> Dict[str, Any]:
        """Select tools OR route to facilitator / conversational."""
        try:
            messages = state.get("messages", [])
            agent_hops = state.get("agent_hops", 0)
            plugin_desc = build_all_plugins_description(self._plugin_bundles)
            tool_desc = build_tool_descriptions(self._plugin_bundles)

            template = (
                self.mode_config.settings.supervisor_node.prompt_override
                or SupervisorPrompts.SUPERVISOR
            )
            system_prompt = template.format(
                current_time=datetime.now(timezone.utc).isoformat(),
                plugin_descriptions=plugin_desc,
                tool_descriptions=tool_desc,
            )

            request_messages = [SystemMessage(content=system_prompt)] + list(messages)

            try:
                response = await asyncio.wait_for(
                    self._supervisor_model.ainvoke(request_messages),
                    timeout=self.mode_config.supervisor_timeout,
                )
                is_timeout = False
            except asyncio.TimeoutError:
                logger.warning(
                    "Supervisor timed out after %ds, routing to facilitator",
                    self.mode_config.supervisor_timeout,
                )
                response = self._build_facilitator_call_message()
                is_timeout = True

            if not is_timeout:
                response = self._ensure_tool_calls_present(response)

            used_plugins = self._detect_used_plugins([response])

            return {
                "messages": [response],
                "agent_hops": agent_hops + 1,
                "current_agent": "supervisor",
                "used_plugins": used_plugins,
                "error_state": None,
                "route_to_facilitator": False,
                "route_to_conversational": False,
            }

        except Exception as e:
            logger.error("Error in supervisor node: %s", e, exc_info=True)
            return self._build_error_state(state, e, "supervisor")

    async def _validation_node(self, state: GraphState) -> Dict[str, Any]:
        """Validate tool results against user intent."""
        try:
            messages = list(state.get("messages", []))
            used_plugins = state.get("used_plugins", [])

            if not self.mode_config.use_llm_validation:
                return {
                    "validation_result": {"passed": True},
                    "current_agent": "validation",
                }

            tool_results = self._extract_tool_results(messages)
            if not tool_results:
                return {
                    "validation_result": {"passed": True},
                    "current_agent": "validation",
                }

            user_query = self._extract_last_human_query(messages)
            tool_results_text = "\n".join(
                f"Tool Result {i + 1}: {json.dumps(r)}"
                for i, r in enumerate(tool_results)
            )
            template = (
                self.mode_config.settings.validation_node.prompt_override
                or SupervisorPrompts.VALIDATION
            )
            system_prompt = template.format(
                current_time=datetime.now(timezone.utc).isoformat(),
                user_query=user_query,
                plugins_used=", ".join(used_plugins),
                tool_results=tool_results_text,
            )

            request_messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content="Please validate the tool results above."),
            ]
            validation_response = await self._validation_model.ainvoke(request_messages)

            if isinstance(validation_response, ValidationResponse):
                result = {
                    "passed": validation_response.is_valid,
                    "reasoning": validation_response.reasoning,
                    "query_intent": validation_response.query_intent,
                    "clarification_type": validation_response.clarification_type,
                    "valid_ids": validation_response.valid_ids,
                }
            else:
                result = {"passed": True}

            return {
                "validation_result": result,
                "current_agent": "validation",
                "error_state": None,
            }

        except Exception as e:
            logger.error("Error in validation node: %s", e, exc_info=True)
            return self._build_error_state(state, e, "validation")

    async def _synthesizer_node(self, state: GraphState) -> Dict[str, Any]:
        """Generate final response from validated tool results."""
        try:
            messages = list(state.get("messages", []))
            plugin_desc = build_all_plugins_description(self._plugin_bundles)

            template = (
                self.mode_config.settings.synthesizer_node.prompt_override
                or SupervisorPrompts.SYNTHESIZER
            )
            system_prompt = template.format(
                current_time=datetime.now(timezone.utc).isoformat(),
                plugin_descriptions=plugin_desc,
            )

            synth_model_no_tools = (
                self._synthesizer_model.without_tools()
                if hasattr(self._synthesizer_model, "without_tools")
                else self._synthesizer_model
            )

            request_messages = [SystemMessage(content=system_prompt)] + messages
            response = await synth_model_no_tools.ainvoke(request_messages)

            return {
                "messages": [response],
                "current_agent": "synthesizer",
                "error_state": None,
            }

        except Exception as e:
            logger.error("Error in synthesizer node: %s", e, exc_info=True)
            return self._build_error_state(state, e, "synthesizer")

    async def _facilitator_node(self, state: GraphState) -> Dict[str, Any]:
        """Generate clarifying questions when intent is unclear."""
        try:
            messages = list(state.get("messages", []))
            validation_result = state.get("validation_result") or {}
            plugin_desc = build_all_plugins_description(self._plugin_bundles)

            clarification_type = validation_result.get("clarification_type", [])
            additional_context = self._build_clarification_context(clarification_type)

            template = (
                self.mode_config.settings.facilitator_node.prompt_override
                or SupervisorPrompts.FACILITATOR
            )
            system_prompt = template.format(
                current_time=datetime.now(timezone.utc).isoformat(),
                plugin_descriptions=plugin_desc,
                additional_context=additional_context,
            )

            facilitator_messages = self._build_facilitator_messages(
                messages, additional_context
            )
            request_messages = [
                SystemMessage(content=system_prompt)
            ] + facilitator_messages

            fac_model = (
                self._synthesizer_model.without_tools()
                if hasattr(self._synthesizer_model, "without_tools")
                else self._synthesizer_model
            )
            response = await fac_model.ainvoke(request_messages)

            return {
                "messages": [response],
                "current_agent": "facilitator",
                "error_state": None,
            }

        except Exception as e:
            logger.error("Error in facilitator node: %s", e, exc_info=True)
            return self._build_error_state(state, e, "facilitator")

    async def _conversational_node(self, state: GraphState) -> Dict[str, Any]:
        """Handle context-only queries (translation, summarisation, meta-questions)."""
        try:
            messages = list(state.get("messages", []))
            plugin_desc = build_all_plugins_description(self._plugin_bundles)

            template = (
                self.mode_config.settings.conversational_node.prompt_override
                or SupervisorPrompts.CONVERSATIONAL
            )
            system_prompt = template.format(
                current_time=datetime.now(timezone.utc).isoformat(),
                plugin_descriptions=plugin_desc,
            )

            conv_model = (
                self._synthesizer_model.without_tools()
                if hasattr(self._synthesizer_model, "without_tools")
                else self._synthesizer_model
            )
            request_messages = [SystemMessage(content=system_prompt)] + messages
            response = await conv_model.ainvoke(request_messages)

            return {
                "messages": [response],
                "current_agent": "conversational",
                "error_state": None,
            }

        except Exception as e:
            logger.error("Error in conversational node: %s", e, exc_info=True)
            return self._build_error_state(state, e, "conversational")

    async def _error_handler_node(self, state: GraphState) -> Dict[str, Any]:
        """Generate a user-friendly recovery message for any node failure."""
        try:
            error_state = state.get("error_state") or {}
            messages = list(state.get("messages", []))

            user_query = self._extract_last_human_query(messages)
            failed_node = error_state.get("node", "unknown")
            error_type = error_state.get("error_type", "SystemError")
            error_details_raw = error_state.get("error_message", "")

            template = (
                self.mode_config.settings.error_handler_node.prompt_override
                or SupervisorPrompts.ERROR_HANDLER
            )
            system_prompt = template.format(
                current_time=datetime.now(timezone.utc).isoformat(),
                failed_node=failed_node,
                error_type=error_type,
                error_details=error_details_raw,
                user_query=user_query,
            )

            request_messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(
                    content=f"Help me handle this error gracefully for: {user_query}"
                ),
            ]
            response = await self._error_model.ainvoke(request_messages)

            return {
                "messages": [response],
                "current_agent": "error_handler",
                "error_state": None,
            }

        except Exception as e:
            logger.error("Critical: error_handler itself failed: %s", e, exc_info=True)
            fallback = AIMessage(
                content="I apologise, but I encountered an issue processing your request. Please try again."
            )
            return {"messages": [fallback], "current_agent": "error_handler"}

    # ------------------------------------------------------------------ #
    # Routing functions
    # ------------------------------------------------------------------ #

    def _route_from_supervisor(self, state: GraphState) -> str:
        if state.get("error_state"):
            return "error_handler"

        messages = state.get("messages", [])
        agent_hops = state.get("agent_hops", 0)

        if agent_hops >= self.mode_config.max_agent_hops:
            logger.warning(
                "Max agent hops (%d) reached", self.mode_config.max_agent_hops
            )
            return "facilitator"

        if not messages:
            return "facilitator"

        last_message = messages[-1]
        if not (hasattr(last_message, "tool_calls") and last_message.tool_calls):
            return "synthesizer"

        analysis = self._analyze_tool_calls(last_message)
        if analysis["has_facilitator"]:
            return "facilitator"
        if analysis["has_conversational"]:
            return "conversational"
        return "control_tools"

    def _route_from_control_tools(self, state: GraphState) -> str:
        if state.get("error_state"):
            return "error_handler"
        return "validation"

    def _route_from_validation(self, state: GraphState) -> str:
        if state.get("error_state"):
            return "error_handler"
        validation_result = state.get("validation_result") or {}
        passed = validation_result.get("passed", True)
        return "synthesizer" if passed else "facilitator"

    def _route_from_synthesizer(self, state: GraphState) -> str:
        return "error_handler" if state.get("error_state") else "end"

    def _route_from_facilitator(self, state: GraphState) -> str:
        return "error_handler" if state.get("error_state") else "end"

    def _route_from_conversational(self, state: GraphState) -> str:
        return "error_handler" if state.get("error_state") else "end"

    # ------------------------------------------------------------------ #
    # Helper methods
    # ------------------------------------------------------------------ #

    @staticmethod
    def _analyze_tool_calls(message: AIMessage) -> Dict[str, bool]:
        """Inspect tool calls to determine routing direction."""
        has_facilitator = False
        has_conversational = False
        has_plugin_tools = False

        for tc in message.tool_calls:
            name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "")
            if name == "call_facilitator":
                has_facilitator = True
            elif name == "call_conversational":
                has_conversational = True
            else:
                has_plugin_tools = True

        return {
            "has_facilitator": has_facilitator,
            "has_conversational": has_conversational,
            "has_plugin_tools": has_plugin_tools,
        }

    def _ensure_tool_calls_present(self, response: AIMessage) -> AIMessage:
        """Guarantee the supervisor response carries tool calls."""
        if not isinstance(response, AIMessage):
            return response

        if response.tool_calls:
            response.content = ""
            return response

        content = response.content or ""
        if "call_conversational" in content:
            return self._build_conversational_call_message()

        return self._build_facilitator_call_message()

    @staticmethod
    def _build_facilitator_call_message() -> AIMessage:
        return AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "call_facilitator",
                    "args": {"reason": ""},
                    "id": f"{_TIMEOUT_FALLBACK_PREFIX}{uuid.uuid4().hex[:20]}",
                    "type": "tool_call",
                }
            ],
        )

    @staticmethod
    def _build_conversational_call_message() -> AIMessage:
        return AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "call_conversational",
                    "args": {"task": ""},
                    "id": f"{_TIMEOUT_FALLBACK_PREFIX}{uuid.uuid4().hex[:20]}",
                    "type": "tool_call",
                }
            ],
        )

    def _detect_used_plugins(self, messages: List[Any]) -> List[str]:
        """Return plugin pids called in the given messages."""
        used: List[str] = []
        for msg in messages:
            if not (hasattr(msg, "tool_calls") and msg.tool_calls):
                continue
            for tc in msg.tool_calls:
                name = (
                    tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "")
                )
                pid = self._tool_collector.get_plugin_for_tool(name)
                if pid and pid not in used:
                    used.append(pid)
        return used

    @staticmethod
    def _extract_tool_results(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        """Extract tool result dicts from the most recent ToolMessages."""
        results = []
        for msg in reversed(messages):
            if not isinstance(msg, ToolMessage):
                break
            try:
                data = json.loads(msg.content)
                if isinstance(data, dict):
                    results.append(data)
            except (json.JSONDecodeError, TypeError):
                pass
        return results

    @staticmethod
    def _extract_last_human_query(messages: List[BaseMessage]) -> str:
        """Return the content of the most recent HumanMessage."""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                return msg.content or ""
        return ""

    @staticmethod
    def _build_clarification_context(clarification_types: List[str]) -> str:
        context_map = {
            "insufficient_results": "Tool search returned no useful results.",
            "missing_parameters": "User intent is clear but required parameters are missing.",
            "low_relevance": "Tool results have low relevance to the user query.",
            "no_relevant_results": "No results match the user's intent.",
        }
        parts = []
        for t in (
            clarification_types
            if isinstance(clarification_types, list)
            else [clarification_types]
        ):
            parts.append(context_map.get(t, t))
        return "\n".join(parts)

    @staticmethod
    def _build_facilitator_messages(
        messages: List[BaseMessage], additional_context: str
    ) -> List[BaseMessage]:
        """Trim message history to the last human message for the facilitator."""
        last_human_idx = -1
        for i in range(len(messages) - 1, -1, -1):
            if isinstance(messages[i], HumanMessage):
                last_human_idx = i
                break
        if last_human_idx == -1:
            return []

        cleaned = list(messages[: last_human_idx + 1])
        if not additional_context:
            return cleaned

        caller_id = f"{_TIMEOUT_FALLBACK_PREFIX}{uuid.uuid4().hex[:20]}"
        cleaned.append(
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "clarify_reason",
                        "args": {"reason": additional_context},
                        "id": caller_id,
                        "type": "tool_call",
                    }
                ],
            )
        )
        cleaned.append(ToolMessage(content=additional_context, tool_call_id=caller_id))
        return cleaned

    @staticmethod
    def _build_error_state(
        state: GraphState, exception: Exception, node_name: str
    ) -> Dict[str, Any]:
        """Build a state update that flags an error for the error_handler."""
        error_lower = str(exception).lower()
        if any(k in error_lower for k in ("rate", "429", "quota")):
            error_type = "RateLimitError"
        elif any(k in error_lower for k in ("timeout", "timed out")):
            error_type = "TimeoutError"
        elif any(k in error_lower for k in ("tool", "plugin")):
            error_type = "ToolError"
        else:
            error_type = "SystemError"

        return {
            "error_state": {
                "node": node_name,
                "error_type": error_type,
                "error_message": str(exception),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        }

    # ------------------------------------------------------------------ #
    # BaseLangGraphOrchestrator abstract method implementations
    # ------------------------------------------------------------------ #

    def _build_initial_graph_state(self, lc_messages: List[Any]) -> Dict[str, Any]:
        return {
            "messages": lc_messages,
            "agent_hops": 0,
            "current_agent": "",
            "error_state": None,
            "validation_result": None,
            "used_plugins": [],
            "route_to_facilitator": False,
            "route_to_conversational": False,
        }

    def _get_recursion_limit(self) -> int:
        return self.mode_config.max_agent_hops + _SUPERVISOR_RECURSION_BUFFER

    def _map_result_to_output(
        self, result: Dict[str, Any], output_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        output_state["agent_hops"] = result.get("agent_hops", 0)
        output_state["current_agent"] = result.get("current_agent", "")
        return output_state

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    async def rebuild(self, config: Dict[str, Any]) -> None:
        """Hot-reload with new configuration."""
        logger.info("Rebuilding LangGraph supervisor")
        await self.cleanup()
        self.resolved_config = config
        self.mode_config = SupervisorMode(config.get("mode_config", {}))
        await self.initialize()
        logger.info("LangGraph supervisor rebuilt successfully")

    async def cleanup(self) -> None:
        """Release resources."""
        logger.info("Cleaning up LangGraph supervisor")
        await self.plugin_manager.cleanup_all()
        self._supervisor_model = None
        self._synthesizer_model = None
        self._validation_model = None
        self._error_model = None
        self.graph = None
        self._is_ready = False

    async def health_check(self) -> Dict[str, Any]:
        return {
            "framework_type": self.framework_type,
            "mode": self.mode,
            "is_ready": self._is_ready,
            "plugin_count": len(self._plugin_bundles),
            "plugins": list(self._plugin_bundles.keys()),
            "max_agent_hops": self.mode_config.max_agent_hops,
            "use_llm_validation": self.mode_config.use_llm_validation,
        }

    @property
    def mode(self) -> str:
        return "supervisor"
