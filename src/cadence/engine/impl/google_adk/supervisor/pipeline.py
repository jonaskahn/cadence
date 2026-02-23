"""Google ADK pipeline agent for the supervisor orchestrator.

Implements the classifier-planner-executor-validator-synthesizer pipeline
as a custom ADK BaseAgent. ADK's LlmAgent natively handles the tool-calling
loop, eliminating the separate executor node from the LangGraph design.
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator, Dict, List, Optional, override

from google.adk.agents import BaseAgent, InvocationContext, LlmAgent, LoopAgent
from google.adk.events import Event, EventActions
from pydantic import ConfigDict, PrivateAttr

from cadence.engine.impl.google_adk.supervisor.helpers import (
    build_clarification_context,
    build_error_state,
    build_tool_context_text,
    extract_tool_results_from_events,
)
from cadence.engine.impl.google_adk.supervisor.pipeline_node import PipelineNode
from cadence.engine.impl.google_adk.supervisor.schemas import SessionKeys
from cadence.engine.impl.google_adk.supervisor.settings import (
    GoogleADKSupervisorSettings,
)

logger = logging.getLogger(__name__)


class ValidationTerminator(BaseAgent):
    """Loop-control agent for ValidationRefinementLoop.

    Reads validation_result from session state after each validator run:
    - Valid:   yields escalation event to exit the LoopAgent.
    - Invalid: enriches additional_context, re-runs planner for fresh
               tool_results, returns without escalating so the loop continues.

    planner_agent is held as a PrivateAttr (not a sub-agent) so that ADK
    does not claim ownership; GoogleADKPipeline remains the sole parent.
    """

    _planner_agent: LlmAgent = PrivateAttr()
    _tool_to_plugin_map: Dict[str, str] = PrivateAttr()

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(
        self,
        *,
        planner_agent: LlmAgent,
        tool_to_plugin_map: Dict[str, str],
        name: str = "validation_terminator",
    ) -> None:
        super().__init__(name=name)
        self._planner_agent = planner_agent
        self._tool_to_plugin_map = tool_to_plugin_map

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        validation_result = ctx.session.state.get(SessionKeys.VALIDATION_RESULT)
        is_valid = True
        clarification_types: List[str] = []
        if isinstance(validation_result, dict):
            is_valid = bool(validation_result.get("is_valid", True))
            clarification_types = validation_result.get("clarification_type", []) or []

        if is_valid:
            yield Event(author=self.name, actions=EventActions(escalate=True))
            return

        ctx.session.state[SessionKeys.ADDITIONAL_CONTEXT] = build_clarification_context(
            clarification_types
        )
        planner_events: List[Event] = []
        executor_event_emitted = False
        yield GoogleADKPipeline.get_node_event(PipelineNode.PLANNER)
        async for event in self._planner_agent.run_async(ctx):
            planner_events.append(event)
            if not executor_event_emitted and event.get_function_responses():
                executor_event_emitted = True
                yield GoogleADKPipeline.get_node_event(PipelineNode.EXECUTOR)
            yield event
        tool_results = extract_tool_results_from_events(
            planner_events, self._tool_to_plugin_map
        )
        ctx.session.state[SessionKeys.TOOL_RESULTS] = tool_results
        ctx.session.state[SessionKeys.TOOL_CONTEXT_TEXT] = build_tool_context_text(
            tool_results
        )


class GoogleADKPipeline(BaseAgent):
    """Custom ADK agent implementing the full supervisor pipeline.

    Orchestrates the classifier → planner+executor → (validator loop) →
    synthesizer / clarifier / responder / error_handler flow using ADK
    LlmAgent sub-agents.

    ADK's LlmAgent natively handles the tool-calling loop, so the planner
    and executor are combined into one agent. Tool results are extracted
    from the yielded events after the planner loop completes.
    """

    router_agent: LlmAgent
    planner_agent: LlmAgent
    synthesizer_agent: LlmAgent
    clarifier_agent: LlmAgent
    responder_agent: LlmAgent
    error_handler_agent: LlmAgent
    validation_loop: Optional[LoopAgent] = None

    _settings: GoogleADKSupervisorSettings = PrivateAttr()
    _tool_to_plugin_map: Dict[str, str] = PrivateAttr()

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(
        self,
        *,
        settings: GoogleADKSupervisorSettings,
        router_agent: LlmAgent,
        planner_agent: LlmAgent,
        synthesizer_agent: LlmAgent,
        clarifier_agent: LlmAgent,
        responder_agent: LlmAgent,
        error_handler_agent: LlmAgent,
        tool_to_plugin_map: Dict[str, str],
        validator_agent: Optional[LlmAgent] = None,
        name: str = "cadence_supervisor_pipeline",
    ) -> None:
        validation_loop: Optional[LoopAgent] = None
        if settings.enabled_llm_validation and validator_agent is not None:
            terminator = ValidationTerminator(
                planner_agent=planner_agent,
                tool_to_plugin_map=tool_to_plugin_map,
            )
            validation_loop = LoopAgent(
                name="validation_refinement_loop",
                sub_agents=[validator_agent, terminator],
                max_iterations=settings.max_validation_iterations,
            )

        directly_orchestrated_agents = [
            router_agent,
            planner_agent,
            synthesizer_agent,
            clarifier_agent,
            responder_agent,
            error_handler_agent,
        ]
        if validation_loop is not None:
            directly_orchestrated_agents.append(validation_loop)

        super().__init__(
            name=name,
            router_agent=router_agent,
            planner_agent=planner_agent,
            synthesizer_agent=synthesizer_agent,
            clarifier_agent=clarifier_agent,
            responder_agent=responder_agent,
            error_handler_agent=error_handler_agent,
            validation_loop=validation_loop,
            sub_agents=directly_orchestrated_agents,
        )
        self._settings = settings
        self._tool_to_plugin_map = tool_to_plugin_map

    @staticmethod
    def get_node_event(node: PipelineNode) -> Event:
        """Create a custom ADK event that signals a pipeline node transition.

        The streaming wrapper detects these events via custom_metadata.node_name
        and emits StreamEvent.agent_start() for each node transition.
        """
        return Event(
            author="pipeline",
            custom_metadata={"node_name": node.value},
        )

    @staticmethod
    def _extract_user_query(ctx: InvocationContext) -> str:
        if ctx.user_content and ctx.user_content.parts:
            return "".join(
                content_part.text or ""
                for content_part in ctx.user_content.parts
                if hasattr(content_part, "text")
            )
        return ""

    @staticmethod
    def _extract_routing(ctx: InvocationContext) -> str:
        """Read routing decision from session state after all router events are yielded.

        Each yielded event causes Runner to call append_event, which commits
        state_delta to ctx.session.state before the generator resumes.
        """
        routing_decision = ctx.session.state.get(SessionKeys.ROUTING_DECISION)
        if isinstance(routing_decision, dict):
            return routing_decision.get("route", "tools")
        if isinstance(routing_decision, str):
            return routing_decision
        return "tools"

    async def _run_planner(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """Stream planner events and store tool results in session state.

        Emits PLANNER then EXECUTOR node events. Sets SessionKeys.TOOL_RESULTS
        and SessionKeys.TOOL_CONTEXT_TEXT in ctx.session.state after all events
        are yielded.
        """
        planner_events: List[Event] = []
        executor_event_emitted = False
        yield self.get_node_event(PipelineNode.PLANNER)
        async for event in self.planner_agent.run_async(ctx):
            planner_events.append(event)
            if not executor_event_emitted and event.get_function_responses():
                executor_event_emitted = True
                yield self.get_node_event(PipelineNode.EXECUTOR)
            yield event
        tool_results = extract_tool_results_from_events(
            planner_events, self._tool_to_plugin_map
        )
        ctx.session.state[SessionKeys.TOOL_RESULTS] = tool_results
        ctx.session.state[SessionKeys.TOOL_CONTEXT_TEXT] = build_tool_context_text(
            tool_results
        )

    async def _run_tools_path(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        async for event in self._run_planner(ctx):
            yield event

        tool_results = ctx.session.state.get(SessionKeys.TOOL_RESULTS, [])
        if (
            self._settings.enabled_llm_validation
            and tool_results
            and self.validation_loop
        ):
            yield self.get_node_event(PipelineNode.VALIDATOR)
            async for event in self.validation_loop.run_async(ctx):
                yield event

            validation_result = ctx.session.state.get(SessionKeys.VALIDATION_RESULT)
            validation_passed = isinstance(validation_result, dict) and bool(
                validation_result.get("is_valid", True)
            )
            if not validation_passed:
                yield self.get_node_event(PipelineNode.CLARIFIER)
                async for event in self.clarifier_agent.run_async(ctx):
                    yield event
                return

        yield self.get_node_event(PipelineNode.SYNTHESIZER)
        async for event in self.synthesizer_agent.run_async(ctx):
            yield event

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """Execute the supervisor pipeline for one user turn."""
        try:
            ctx.session.state[SessionKeys.USER_QUERY] = self._extract_user_query(ctx)

            # ROUTER start is pre-emitted in astream() before the runner starts.
            async for event in self.router_agent.run_async(ctx):
                yield event
            routing = self._extract_routing(ctx)

            if routing == "conversational":
                yield self.get_node_event(PipelineNode.RESPONDER)
                async for event in self.responder_agent.run_async(ctx):
                    yield event
                return

            if routing == "clarify":
                yield self.get_node_event(PipelineNode.CLARIFIER)
                async for event in self.clarifier_agent.run_async(ctx):
                    yield event
                return

            async for event in self._run_tools_path(ctx):
                yield event

        except Exception as exc:
            logger.error("Exception in supervisor pipeline: %s", exc, exc_info=True)
            ctx.session.state[SessionKeys.ERROR_STATE] = build_error_state(
                exc, "pipeline"
            )
            yield self.get_node_event(PipelineNode.ERROR_HANDLER)
            async for event in self.error_handler_agent.run_async(ctx):
                yield event
