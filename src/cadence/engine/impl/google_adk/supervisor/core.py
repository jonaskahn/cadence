"""Google ADK supervisor orchestrator — classifier-planner-executor pipeline.

Nodes:
1. router       — intent classification (structured output → RoutingDecision)
2. planner      — tool selection and invocation (ADK handles tool loop)
3. executor     — implicit within planner (ADK native)
4. validator    — LLM validation of tool results (optional)
5. synthesizer  — final response from tool results
6. clarifier    — clarifying questions for unclear intent
7. responder    — conversational / meta queries
8. error_handler — graceful failure recovery

Routing:
START → router
router → [planner | responder | clarifier]
planner+executor → (validator loop?) → synthesizer
validator loop fail → clarifier
(any exception) → error_handler → END
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, NamedTuple, Optional

from cadence_sdk.types.sdk_state import UvState
from google.adk.agents import LlmAgent
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

from cadence.constants import Framework
from cadence.engine.base import BaseOrchestrator
from cadence.engine.base.supervisor_node_config import SupervisorModeNodeConfig
from cadence.engine.impl.google_adk.adapter import GoogleADKAdapter
from cadence.engine.impl.google_adk.streaming import GoogleADKStreamingWrapper
from cadence.engine.impl.google_adk.supervisor.pipeline import GoogleADKPipeline
from cadence.engine.impl.google_adk.supervisor.pipeline_node import PipelineNode
from cadence.engine.impl.google_adk.supervisor.prompts import GoogleADKSupervisorPrompts
from cadence.engine.impl.google_adk.supervisor.schemas import (
    RoutingDecision,
    SessionKeys,
    ValidationResponse,
)
from cadence.engine.impl.google_adk.supervisor.settings import (
    GoogleADKSupervisorSettings,
)
from cadence.engine.modes import SupervisorMode
from cadence.engine.utils.plugin_utils import (
    build_all_plugins_description,
    build_tool_descriptions,
)
from cadence.infrastructure.plugins import SDKPluginManager
from cadence.infrastructure.streaming import StreamEvent


class _AgentBundle(NamedTuple):
    router: LlmAgent
    planner: LlmAgent
    synthesizer: LlmAgent
    clarifier: LlmAgent
    responder: LlmAgent
    validator: Optional[LlmAgent]
    error_handler: LlmAgent


logger = logging.getLogger(__name__)

_AUTOCOMPACT_AGENT_INSTRUCTION = (
    "You are a conversation summarizer. "
    "When given a conversation history, summarize it into a concise paragraph "
    "that captures the key topics discussed, decisions made, and any important context. "
    "Be factual and preserve all important details."
)


class GoogleADKSupervisor(BaseOrchestrator):
    """Google ADK supervisor — classifier-planner-executor pipeline."""

    adapter: GoogleADKAdapter

    @staticmethod
    def _get_app_prefix() -> str:
        return "CADENCE_GOOGLE_ADK"

    def __init__(
        self,
        plugin_manager: SDKPluginManager,
        llm_factory: Any,
        resolved_config: Dict[str, Any],
        adapter: GoogleADKAdapter,
        streaming_wrapper: GoogleADKStreamingWrapper,
    ):
        super().__init__(
            plugin_manager=plugin_manager,
            llm_factory=llm_factory,
            resolved_config=resolved_config,
            adapter=adapter,
            streaming_wrapper=streaming_wrapper,
        )
        self._mode_config = SupervisorMode(
            Framework.GOOGLE_ADK, resolved_config.get("mode_config", {})
        )
        self._settings: GoogleADKSupervisorSettings = self._resolve_settings(
            self._mode_config, resolved_config
        )
        self._default_node_config = SupervisorModeNodeConfig.from_resolved_config(
            resolved_config
        )
        self._session_service: Optional[InMemorySessionService] = None
        self._runner: Optional[Runner] = None
        self._pipeline: Optional[GoogleADKPipeline] = None
        self._tool_to_plugin_map: Dict[str, str] = {}
        self._cached_plugin_descriptions: str = ""
        self._cached_tool_descriptions: str = ""
        self._auto_compact_agent: Optional[LlmAgent] = None
        self._compact_runner: Optional[Runner] = None

    @property
    def mode(self) -> str:
        return "supervisor"

    @property
    def framework_type(self) -> str:
        return "google_adk"

    def _llm_factory_extra_kwargs(self) -> Dict[str, Any]:
        return {"framework": Framework.GOOGLE_ADK}

    async def _build_resources(self) -> None:
        """Build all models, agents, and the ADK runner."""
        all_tools, self._tool_to_plugin_map = self._collect_tools()
        self._cached_plugin_descriptions = build_all_plugins_description(
            self._plugin_bundles
        )
        self._cached_tool_descriptions = build_tool_descriptions(self._plugin_bundles)
        agents = await self._build_agents(all_tools)
        self._pipeline = GoogleADKPipeline(
            settings=self._settings,
            router_agent=agents.router,
            planner_agent=agents.planner,
            synthesizer_agent=agents.synthesizer,
            clarifier_agent=agents.clarifier,
            responder_agent=agents.responder,
            error_handler_agent=agents.error_handler,
            validator_agent=agents.validator,
            tool_to_plugin_map=self._tool_to_plugin_map,
        )
        self._session_service = InMemorySessionService()
        self._runner = Runner(
            agent=self._pipeline,
            app_name=f"{self._get_app_prefix()}_{self.org_id}",
            session_service=self._session_service,
        )
        if self._settings.enabled_auto_compact:
            await self._build_compact_resources()

    async def _build_compact_resources(self) -> None:
        """Create a dedicated LlmAgent + Runner for autocompact history summarization."""
        compact_settings = self._default_node_config.merge(self._settings.autocompact)
        compact_model = await self._create_model_for_node(compact_settings)
        self._auto_compact_agent = LlmAgent(
            name="autocompact",
            model=compact_model,
            instruction=_AUTOCOMPACT_AGENT_INSTRUCTION,
        )
        compact_session_service = InMemorySessionService()
        self._compact_runner = Runner(
            agent=self._auto_compact_agent,
            app_name=f"{self._get_app_prefix()}_{self.org_id}_compact",
            session_service=compact_session_service,
        )

    async def astream(self, state: UvState) -> AsyncIterator[StreamEvent]:
        """Execute streaming orchestration via the ADK pipeline."""
        if not self._is_ready:
            raise RuntimeError("Google ADK supervisor is not ready")

        messages = state.get("messages", [])
        if not messages:
            return

        session_id = str(uuid.uuid4())
        user_id = f"{self.org_id}_{uuid.uuid4()}"
        app_name = f"{self._get_app_prefix()}_{self.org_id}"
        session = await self._session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
        )

        initial_state = {
            SessionKeys.CURRENT_TIME: datetime.now(timezone.utc).isoformat(),
            SessionKeys.PLUGIN_DESCRIPTIONS: (self._cached_plugin_descriptions),
            SessionKeys.TOOL_DESCRIPTIONS: self._cached_tool_descriptions,
            SessionKeys.MAX_AGENT_HOPS: self._settings.max_agent_hops,
            SessionKeys.ADDITIONAL_CONTEXT: "",
        }

        history_msgs = messages[:-1]
        for sdk_msg in history_msgs:
            hist_event = self.adapter.sdk_message_to_event(sdk_msg)
            if hist_event is not None:
                await self._session_service.append_event(session, hist_event)

        latest_content = self.adapter.sdk_message_to_orchestrator(messages[-1])
        if latest_content is None:
            return

        # Pre-emit ROUTER start before ADK runner initializes (mirrors LangGraph pattern).
        from cadence.engine.impl.google_adk.supervisor.pipeline_node import NodeDisplay

        yield StreamEvent.agent_start(NodeDisplay.get(PipelineNode.ROUTER))

        adk_stream = self._runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=latest_content,
            state_delta=initial_state,
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        )
        async for stream_event in self.streaming_wrapper.wrap_stream(adk_stream):
            yield stream_event

    async def compact_history(self, messages: List[Any]) -> str:
        """Summarize conversation history using the dedicated autocompact runner.

        Args:
            messages: List of conversation messages to summarize.

        Returns:
            Summary string from the LLM.
        """
        if not self._compact_runner:
            logger.warning(
                "compact_history called but autocompact runner not initialized"
            )
            return "Previous conversation summary not available."

        history_text = "\n".join(
            f"{type(m).__name__}: {getattr(m, 'content', str(m))}" for m in messages
        )
        user_content = Content(
            role="user",
            parts=[
                Part(
                    text=(
                        f"Current time: {datetime.now(timezone.utc).isoformat()}\n\n"
                        f"Conversation history:\n{history_text}\n\n"
                        f"Please summarize the conversation above."
                    )
                )
            ],
        )

        session_id = str(uuid.uuid4())
        user_id = f"compact_{uuid.uuid4()}"
        app_name = f"{self._get_app_prefix()}_{self.org_id}_compact"
        compact_session_service = self._compact_runner.session_service
        await compact_session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
        )

        timeout = (
            self._settings.autocompact.timeout or self._settings.node_execution_timeout
        )
        try:
            collected_text: List[str] = []
            async with asyncio.timeout(timeout):
                async for event in self._compact_runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=user_content,
                ):
                    if hasattr(event, "content") and event.content:
                        for part in getattr(event.content, "parts", []):
                            text = getattr(part, "text", None)
                            if text:
                                collected_text.append(text)
            return (
                "".join(collected_text)
                or "Previous conversation summary not available."
            )
        except asyncio.TimeoutError:
            logger.warning("Autocompact runner timed out after %ds", timeout)
            return "Previous conversation summary not available (timed out)."
        except Exception as e:
            logger.error("Error in compact_history: %s", e, exc_info=True)
            return "Previous conversation summary not available."

    def _on_config_update(self, config: Dict[str, Any]) -> None:
        self._mode_config = SupervisorMode(
            Framework.GOOGLE_ADK, config.get("mode_config", {})
        )
        self._settings = self._resolve_settings(self._mode_config, config)

    async def _release_resources(self) -> None:
        self._pipeline = None
        self._runner = None
        self._session_service = None
        self._auto_compact_agent = None
        self._compact_runner = None

    def _extra_health_fields(self) -> Dict[str, Any]:
        return {
            "max_agent_hops": self._settings.max_agent_hops,
            "enabled_llm_validation": self._settings.enabled_llm_validation,
        }

    @staticmethod
    def _resolve_settings(
        mode_config: SupervisorMode, config: Dict[str, Any]
    ) -> GoogleADKSupervisorSettings:
        if isinstance(mode_config.settings, GoogleADKSupervisorSettings):
            return mode_config.settings
        return GoogleADKSupervisorSettings.model_validate(config.get("mode_config", {}))

    def _collect_tools(self):
        """Collect ADK FunctionTool instances from all loaded plugin bundles.

        Returns:
            Tuple of (all_tools, tool_to_plugin_map).
        """
        all_tools = []
        tool_to_plugin_map: Dict[str, str] = {}
        for pid, bundle in self._plugin_bundles.items():
            for tool in bundle.orchestrator_tools:
                tool_name = getattr(tool, "name", None) or getattr(
                    getattr(tool, "func", None), "__name__", str(tool)
                )
                all_tools.append(tool)
                tool_to_plugin_map[tool_name] = pid
        self.logger.info(
            "Collected %d tools from %d plugin bundles",
            len(all_tools),
            len(self._plugin_bundles),
        )
        return all_tools, tool_to_plugin_map

    async def _build_agents(self, all_tools: List[Any]) -> _AgentBundle:
        """Create all LlmAgent instances for the pipeline."""
        settings = self._settings

        router_model = await self._create_model_for_node(
            self._default_node_config.merge(settings.classifier_node), temperature=0.0
        )
        router_agent = LlmAgent(
            name=PipelineNode.ROUTER.value,
            model=router_model,
            instruction=settings.classifier_node.prompt
            or GoogleADKSupervisorPrompts.ROUTER,
            output_schema=RoutingDecision,
            output_key=SessionKeys.ROUTING_DECISION,
        )

        planner_model = await self._create_model_for_node(
            self._default_node_config.merge(settings.planner_node)
        )
        planner_agent = LlmAgent(
            name=PipelineNode.PLANNER.value,
            model=planner_model,
            instruction=settings.planner_node.prompt
            or GoogleADKSupervisorPrompts.PLANNER,
            tools=all_tools,
        )

        synthesizer_model = await self._create_model_for_node(
            self._default_node_config.merge(settings.synthesizer_node)
        )
        synthesizer_agent = LlmAgent(
            name=PipelineNode.SYNTHESIZER.value,
            model=synthesizer_model,
            instruction=settings.synthesizer_node.prompt
            or GoogleADKSupervisorPrompts.SYNTHESIZER,
        )
        clarifier_agent = LlmAgent(
            name=PipelineNode.CLARIFIER.value,
            model=synthesizer_model,
            instruction=settings.clarifier_node.prompt
            or GoogleADKSupervisorPrompts.CLARIFIER,
        )
        responder_agent = LlmAgent(
            name=PipelineNode.RESPONDER.value,
            model=synthesizer_model,
            instruction=settings.responder_node.prompt
            or GoogleADKSupervisorPrompts.RESPONDER,
        )

        validator_agent: Optional[LlmAgent] = None
        if settings.enabled_llm_validation:
            validation_model = await self._create_model_for_node(
                self._default_node_config.merge(settings.validation_node),
                temperature=0.0,
            )
            validator_agent = LlmAgent(
                name=PipelineNode.VALIDATOR.value,
                model=validation_model,
                instruction=settings.validation_node.prompt
                or GoogleADKSupervisorPrompts.VALIDATION,
                output_schema=ValidationResponse,
                output_key=SessionKeys.VALIDATION_RESULT,
            )

        error_model = await self._create_model_for_node(
            self._default_node_config.merge(settings.error_handler_node)
        )
        error_agent = LlmAgent(
            name=PipelineNode.ERROR_HANDLER.value,
            model=error_model,
            instruction=settings.error_handler_node.prompt
            or GoogleADKSupervisorPrompts.ERROR_HANDLER,
        )

        return _AgentBundle(
            router=router_agent,
            planner=planner_agent,
            synthesizer=synthesizer_agent,
            clarifier=clarifier_agent,
            responder=responder_agent,
            validator=validator_agent,
            error_handler=error_agent,
        )
