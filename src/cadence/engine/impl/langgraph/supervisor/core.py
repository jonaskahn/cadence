"""LangGraph supervisor orchestrator — classifier-planner-executor pipeline.

Nodes:
1. router       — intent classification (cheap, no tool schemas)
2. planner      — tool selection (expensive, tools bound)
3. executor     — plugin tool execution via ToolNode
4. validator    — LLM validation of tool results (optional)
5. synthesizer  — final response from tool results
6. clarifier    — clarifying questions for unclear intent
7. responder    — conversational / meta queries
8. error_handler — graceful failure recovery

Routing:
START → router
router → [planner | responder | clarifier | error_handler]
planner → [executor | synthesizer | error_handler]
executor → [validator | synthesizer | error_handler]
validator → [synthesizer | clarifier | error_handler]
synthesizer → [END | error_handler]
clarifier → [END | error_handler]
responder → [END | error_handler]
error_handler → END
"""

from __future__ import annotations

import asyncio
import functools
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from cadence.constants import Framework
from cadence.engine.base.supervisor_node_config import SupervisorModeNodeConfig
from cadence.engine.impl.langgraph.adapter import LangChainAdapter
from cadence.engine.impl.langgraph.base import BaseLangGraphOrchestrator
from cadence.engine.impl.langgraph.state import MessageState
from cadence.engine.impl.langgraph.streaming import LangGraphStreamingWrapper
from cadence.engine.impl.langgraph.supervisor.graph_node import GraphNode, NodeDisplay
from cadence.engine.impl.langgraph.supervisor.hook import with_node_start_hook
from cadence.engine.impl.langgraph.supervisor.nodes import (
    RoutingDecision,
    run_clarifier_node,
    run_error_handler_node,
    run_executor_node,
    run_planner_node,
    run_responder_node,
    run_router_node,
    run_synthesizer_node,
    run_validator_node,
)
from cadence.engine.impl.langgraph.supervisor.tool_collector import (
    SupervisorToolCollector,
)
from cadence.engine.modes import SupervisorMode
from cadence.infrastructure.plugins import SDKPluginManager
from cadence.infrastructure.streaming import StreamEvent

logger = logging.getLogger(__name__)

_SUPERVISOR_RECURSION_BUFFER = 10

_AUTOCOMPACT_PROMPT = (
    "You are a conversation summarizer. "
    "Summarize the following conversation history into a concise paragraph that captures "
    "the key topics discussed, decisions made, and any important context. "
    "Be factual and preserve all important details. "
    "Current time: {current_time}\n\nConversation history:\n{history}"
)


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
    """LangGraph supervisor — classifier-planner-executor pipeline."""

    def get_stream_data_before_graph_start(self):
        try:
            return StreamEvent.agent_start(NodeDisplay.get(GraphNode.ROUTER))
        except Exception as e:
            self.logger.warning(
                "Failed to initialise supervisor mode: %s", e, exc_info=True
            )

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
        self._mode_config = self._create_mode_config(resolved_config)
        self._default_node_config = SupervisorModeNodeConfig.from_resolved_config(
            resolved_config
        )
        self._tool_collector: Optional[SupervisorToolCollector] = None
        self._all_tools: Optional[List[Any]] = None
        self._classifier_model: Any = None
        self._planner_model: Any = None
        self._synthesizer_model: Any = None
        self._validation_model: Any = None
        self._error_model: Any = None
        self._auto_compact_model: Any = None

    @property
    def mode_config(self):
        return self._mode_config

    @staticmethod
    def _create_mode_config(config: Dict[str, Any]) -> SupervisorMode:
        return SupervisorMode(Framework.LANGGRAPH, config.get("mode_config", {}))

    async def _build_resources(self) -> None:
        """Build all models and the LangGraph workflow."""
        self._tool_collector = SupervisorToolCollector(self._plugin_bundles)
        self._all_tools = self._tool_collector.collect_all_tools()
        await self._setup_models()
        self.graph = self._build_graph()

    async def _setup_models(self) -> None:
        """Create LLM instances for each node that needs one."""
        settings = self._mode_config.settings

        classifier_node_settings = self._default_node_config.merge(
            settings.classifier_node
        )
        classifier_base = await self._create_model_for_node(classifier_node_settings)
        try:
            self._classifier_model = classifier_base.with_structured_output(
                RoutingDecision
            )
        except Exception as e:
            self.logger.warning(
                "Could not bind RoutingDecision schema; falling back to base model: %s",
                e,
                exc_info=True,
            )
            self._classifier_model = classifier_base

        planner_node_settings = self._default_node_config.merge(settings.planner_node)
        planner_base = await self._create_model_for_node(planner_node_settings)
        self._planner_model = planner_base.bind_tools(
            self._all_tools,
            parallel_tool_calls=self._mode_config.enabled_parallel_tool_calls,
        )

        synthesizer_node_settings = self._default_node_config.merge(
            settings.synthesizer_node
        )
        self._synthesizer_model = await self._create_model_for_node(
            synthesizer_node_settings
        )

        if self._mode_config.enabled_llm_validation:
            validation_node_settings = self._default_node_config.merge(
                settings.validation_node
            )
            validation_base = await self._create_model_for_node(
                validation_node_settings, temperature=0.0
            )
            try:
                self._validation_model = validation_base.with_structured_output(
                    ValidationResponse
                )
            except Exception as e:
                self.logger.warning(
                    "Could not bind ValidationResponse schema; falling back to base model: %s",
                    e,
                    exc_info=True,
                )
                self._validation_model = validation_base

        error_handler_node_settings = self._default_node_config.merge(
            settings.error_handler_node
        )
        self._error_model = await self._create_model_for_node(
            error_handler_node_settings
        )

        if self._mode_config.enabled_auto_compact:
            autocompact_settings = self._default_node_config.merge(settings.autocompact)
            self._auto_compact_model = await self._create_model_for_node(
                autocompact_settings
            )

    def _build_graph(self) -> Any:
        """Construct and compile the supervisor StateGraph."""
        executor = ToolNode(self._all_tools)
        settings = self._mode_config.settings

        workflow = StateGraph(MessageState)

        workflow.add_node(
            GraphNode.ROUTER.value,
            functools.partial(
                run_router_node,
                model=self._classifier_model,
                settings=settings,
                plugin_bundles=self._plugin_bundles,
            ),
        )
        workflow.add_node(
            GraphNode.PLANNER.value,
            functools.partial(
                run_planner_node,
                model=self._planner_model,
                settings=settings,
                plugin_bundles=self._plugin_bundles,
            ),
        )
        workflow.add_node(
            GraphNode.EXECUTOR.value,
            functools.partial(
                run_executor_node,
                tool_node=executor,
                tool_collector=self._tool_collector,
                settings=settings,
            ),
        )
        workflow.add_node(
            GraphNode.SYNTHESIZER.value,
            functools.partial(
                run_synthesizer_node,
                model=self._synthesizer_model,
                settings=settings,
                plugin_bundles=self._plugin_bundles,
            ),
        )
        workflow.add_node(
            GraphNode.CLARIFIER.value,
            functools.partial(
                run_clarifier_node,
                model=self._synthesizer_model,
                settings=settings,
                plugin_bundles=self._plugin_bundles,
            ),
        )
        workflow.add_node(
            GraphNode.RESPONDER.value,
            functools.partial(
                run_responder_node,
                model=self._synthesizer_model,
                settings=settings,
                plugin_bundles=self._plugin_bundles,
            ),
        )
        workflow.add_node(
            GraphNode.ERROR_HANDLER.value,
            functools.partial(
                run_error_handler_node,
                model=self._error_model,
                settings=settings,
            ),
        )

        workflow.add_edge(START, GraphNode.ROUTER.value)

        workflow.add_conditional_edges(
            GraphNode.ROUTER.value,
            self._route_from_router,
            {
                GraphNode.PLANNER.value: GraphNode.PLANNER.value,
                GraphNode.RESPONDER.value: GraphNode.RESPONDER.value,
                GraphNode.CLARIFIER.value: GraphNode.CLARIFIER.value,
                GraphNode.ERROR_HANDLER.value: GraphNode.ERROR_HANDLER.value,
            },
        )

        workflow.add_conditional_edges(
            GraphNode.PLANNER.value,
            self._route_from_planner,
            {
                GraphNode.EXECUTOR.value: GraphNode.EXECUTOR.value,
                GraphNode.SYNTHESIZER.value: GraphNode.SYNTHESIZER.value,
                GraphNode.ERROR_HANDLER.value: GraphNode.ERROR_HANDLER.value,
            },
        )

        if self._mode_config.enabled_llm_validation:
            workflow.add_node(
                GraphNode.VALIDATOR.value,
                functools.partial(
                    run_validator_node,
                    model=self._validation_model,
                    settings=settings,
                ),
            )
            workflow.add_conditional_edges(
                GraphNode.EXECUTOR.value,
                self._route_from_executor,
                {
                    GraphNode.VALIDATOR.value: GraphNode.VALIDATOR.value,
                    GraphNode.ERROR_HANDLER.value: GraphNode.ERROR_HANDLER.value,
                },
            )
            workflow.add_conditional_edges(
                GraphNode.VALIDATOR.value,
                self._route_from_validator,
                {
                    GraphNode.SYNTHESIZER.value: GraphNode.SYNTHESIZER.value,
                    GraphNode.CLARIFIER.value: GraphNode.CLARIFIER.value,
                    GraphNode.ERROR_HANDLER.value: GraphNode.ERROR_HANDLER.value,
                },
            )
        else:
            workflow.add_conditional_edges(
                GraphNode.EXECUTOR.value,
                self._route_from_executor_to_synthesizer,
                {
                    GraphNode.SYNTHESIZER.value: GraphNode.SYNTHESIZER.value,
                    GraphNode.ERROR_HANDLER.value: GraphNode.ERROR_HANDLER.value,
                },
            )

        for terminal in (
            GraphNode.SYNTHESIZER,
            GraphNode.CLARIFIER,
            GraphNode.RESPONDER,
        ):
            workflow.add_conditional_edges(
                terminal.value,
                self._route_from_terminal,
                {
                    GraphNode.END.value: END,
                    GraphNode.ERROR_HANDLER.value: GraphNode.ERROR_HANDLER.value,
                },
            )

        workflow.add_edge(GraphNode.ERROR_HANDLER.value, END)

        return workflow.compile()

    @with_node_start_hook()
    def _route_from_router(self, state: MessageState) -> str:
        if state.get("error_state"):
            return GraphNode.ERROR_HANDLER.value
        return {
            "tools": GraphNode.PLANNER.value,
            "conversational": GraphNode.RESPONDER.value,
            "clarify": GraphNode.CLARIFIER.value,
        }.get(state.get("routing_decision", "tools"), GraphNode.CLARIFIER.value)

    @with_node_start_hook()
    def _route_from_planner(self, state: MessageState) -> str:
        if state.get("error_state"):
            return GraphNode.ERROR_HANDLER.value
        if state.get("agent_hops", 0) >= self._mode_config.max_agent_hops:
            logger.warning(
                "Max agent hops (%d) reached, routing to synthesizer",
                self._mode_config.max_agent_hops,
            )
            return GraphNode.SYNTHESIZER.value
        last = (state.get("messages") or [None])[-1]
        if last and getattr(last, "tool_calls", None):
            return GraphNode.EXECUTOR.value
        return GraphNode.SYNTHESIZER.value

    @with_node_start_hook()
    def _route_from_executor(self, state: MessageState) -> str:
        if state.get("error_state"):
            return GraphNode.ERROR_HANDLER.value
        return GraphNode.VALIDATOR.value

    @with_node_start_hook()
    def _route_from_executor_to_synthesizer(self, state: MessageState) -> str:
        if state.get("error_state"):
            return GraphNode.ERROR_HANDLER.value
        return GraphNode.SYNTHESIZER.value

    @with_node_start_hook()
    def _route_from_validator(self, state: MessageState) -> str:
        if state.get("error_state"):
            return GraphNode.ERROR_HANDLER.value
        passed = (state.get("validation_result") or {}).get("passed", True)
        return GraphNode.SYNTHESIZER.value if passed else GraphNode.CLARIFIER.value

    @with_node_start_hook()
    def _route_from_terminal(self, state: MessageState) -> str:
        return (
            GraphNode.ERROR_HANDLER.value
            if state.get("error_state")
            else GraphNode.END.value
        )

    def _on_config_update(self, config: Dict[str, Any]) -> None:
        self._mode_config = self._create_mode_config(config)

    async def _release_resources(self) -> None:
        self._classifier_model = None
        self._planner_model = None
        self._synthesizer_model = None
        self._validation_model = None
        self._error_model = None
        self._auto_compact_model = None
        self.graph = None

    def _extra_health_fields(self) -> Dict[str, Any]:
        return {
            "max_agent_hops": self._mode_config.max_agent_hops,
            "enabled_llm_validation": self._mode_config.enabled_llm_validation,
        }

    @property
    def mode(self) -> str:
        return "supervisor"

    def _build_initial_graph_state(self, lc_messages: List[Any]) -> MessageState:
        return MessageState(
            messages=lc_messages,
            agent_hops=0,
            current_agent="",
            error_state=None,
            validation_result=None,
            used_plugins=[],
            routing_decision=None,
            tool_results=None,
        )

    def _get_recursion_limit(self) -> int:
        return self._mode_config.max_agent_hops + _SUPERVISOR_RECURSION_BUFFER

    def _map_result_to_output(
        self, result: Dict[str, Any], output_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        output_state["agent_hops"] = result.get("agent_hops", 0)
        output_state["current_agent"] = result.get("current_agent", "")
        return output_state

    async def compact_history(self, messages: List[Any]) -> str:
        """Summarize conversation history using the autocompact model.

        Args:
            messages: List of conversation messages to summarize.

        Returns:
            Summary string from the LLM.
        """
        if not self._auto_compact_model:
            logger.warning(
                "compact_history called but autocompact model not initialized"
            )
            return "Previous conversation summary not available."

        history_text = "\n".join(
            f"{type(m).__name__}: {getattr(m, 'content', str(m))}" for m in messages
        )
        prompt = _AUTOCOMPACT_PROMPT.format(
            current_time=datetime.now(timezone.utc).isoformat(),
            history=history_text,
        )

        timeout = (
            self._mode_config.settings.autocompact.timeout
            or self._mode_config.node_execution_timeout
        )
        try:
            response = await asyncio.wait_for(
                self._auto_compact_model.ainvoke(
                    [
                        SystemMessage(content=prompt),
                        HumanMessage(
                            content="Please summarize the conversation above."
                        ),
                    ]
                ),
                timeout=timeout,
            )
            return getattr(response, "content", str(response))
        except asyncio.TimeoutError:
            logger.warning("Autocompact model timed out after %ds", timeout)
            return "Previous conversation summary not available (timed out)."
        except Exception as e:
            logger.error("Error in compact_history: %s", e, exc_info=True)
            return "Previous conversation summary not available."
