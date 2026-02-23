"""Unit tests for the LangGraph supervisor — classifier-planner-executor pipeline.

Covers:
- Graph builds without errors
- _route_from_router: maps routing_decision to correct node
- _route_from_planner: executor, synthesizer, max-hops routing
- _route_from_executor: validator (when enabled) or synthesizer
- _route_from_validator: synthesizer vs clarifier based on passed flag
- run_error_handler_node: returns a user-friendly AIMessage on exception state
- ValidationResponse model construction
- LangGraphSupervisorSettings: defaults and model_validate
- Per-node model resolution: node llm_config_id, instance default_llm_config_id
- Prompt overrides: custom template used when set, default when not
- Executor node populates attributed tool_results
- Synthesizer reads from tool_results field
- Validator absent from graph when enabled_llm_validation=False
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool

# Pre-load engine module to avoid circular import issues
import cadence.engine.factory  # noqa: F401
from cadence.engine.impl.langgraph.supervisor.core import (
    LangGraphSupervisor,
    ValidationResponse,
)
from cadence.engine.impl.langgraph.supervisor.graph_node import GraphNode, NodeDisplay
from cadence.engine.impl.langgraph.supervisor.nodes import (
    run_error_handler_node,
    run_executor_node,
    run_planner_node,
    run_router_node,
    run_synthesizer_node,
)
from cadence.engine.impl.langgraph.supervisor.settings import (
    LangGraphSupervisorSettings,
    SupervisorModeNodeConfig,
)
from cadence.engine.impl.langgraph.supervisor.tool_collector import (
    SupervisorToolCollector,
)

# Backward-compatible alias used in some tests
NodeConfig = SupervisorModeNodeConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_lc_tool(name: str) -> StructuredTool:
    """Create a real LangChain StructuredTool so ToolNode accepts it."""

    def _run(query: str = "") -> str:
        return f"result from {name}"

    return StructuredTool.from_function(
        name=name,
        description=f"Mock tool {name}",
        func=_run,
    )


def _make_mock_bundle(pid: str) -> MagicMock:
    bundle = MagicMock()
    bundle.metadata.name = pid
    bundle.metadata.description = f"Plugin {pid}"
    bundle.metadata.capabilities = ["general"]
    bundle.metadata.version = "1.0.0"
    bundle.orchestrator_tools = [_make_lc_tool(f"{pid}_search")]
    bundle.uv_tools = []
    return bundle


async def _make_supervisor_async(
    mode_config: dict | None = None,
    default_llm_config_id: int = 1,
) -> LangGraphSupervisor:
    """Create a LangGraphSupervisor with all dependencies mocked (async)."""
    bundles = {
        "io.cadence.test.plugin": _make_mock_bundle("io.cadence.test.plugin"),
    }

    plugin_manager = MagicMock()
    plugin_manager.bundles = bundles
    plugin_manager.cleanup_all = AsyncMock()

    mock_model = MagicMock()
    mock_model.bind_tools = MagicMock(return_value=mock_model)
    mock_model.without_tools = MagicMock(return_value=mock_model)
    mock_model.with_structured_output = MagicMock(return_value=mock_model)
    mock_model.ainvoke = AsyncMock(return_value=AIMessage(content="test response"))

    llm_factory = MagicMock()
    llm_factory.create_model_by_id = AsyncMock(return_value=mock_model)

    adapter = MagicMock()
    adapter.sdk_message_to_orchestrator = MagicMock(side_effect=lambda m: m)
    adapter.orchestrator_message_to_sdk = MagicMock(side_effect=lambda m: m)

    streaming_wrapper = MagicMock()

    resolved_config = {
        "default_llm_config_id": default_llm_config_id,
        "org_id": "test-org",
        "temperature": 0.7,
        "max_tokens": 2048,
        "mode_config": mode_config or {},
    }

    supervisor = LangGraphSupervisor(
        plugin_manager=plugin_manager,
        llm_factory=llm_factory,
        resolved_config=resolved_config,
        adapter=adapter,
        streaming_wrapper=streaming_wrapper,
    )
    await supervisor.initialize()
    return supervisor


def _make_supervisor(
    mode_config: dict | None = None,
    default_llm_config_id: int = 1,
) -> LangGraphSupervisor:
    """Sync wrapper around _make_supervisor_async for non-async tests."""
    return asyncio.get_event_loop().run_until_complete(
        _make_supervisor_async(mode_config, default_llm_config_id)
    )


# ---------------------------------------------------------------------------
# LangGraphSupervisorSettings
# ---------------------------------------------------------------------------


class TestLangGraphSupervisorSettings:
    def test_defaults(self):
        settings = LangGraphSupervisorSettings.model_validate({})
        assert settings.max_agent_hops == 10
        assert settings.enabled_parallel_tool_calls is True
        assert settings.node_execution_timeout == 60
        assert settings.enabled_llm_validation is False
        assert settings.message_context_window == 5
        assert settings.max_context_window == 16_000
        assert settings.enabled_auto_compact is False
        assert isinstance(settings.autocompact, SupervisorModeNodeConfig)
        assert settings.classifier_node.llm_config_id is None
        assert settings.planner_node.llm_config_id is None

    def test_node_defaults(self):
        settings = LangGraphSupervisorSettings.model_validate({})
        assert settings.planner_node.llm_config_id is None
        assert settings.planner_node.prompt is None
        assert settings.synthesizer_node.llm_config_id is None
        assert settings.validation_node.llm_config_id is None
        assert settings.clarifier_node.llm_config_id is None
        assert settings.responder_node.llm_config_id is None
        assert settings.error_handler_node.llm_config_id is None

    def test_node_config_from_dict(self):
        settings = LangGraphSupervisorSettings.model_validate(
            {
                "max_agent_hops": 5,
                "planner_node": {"llm_config_id": 3, "prompt_override": "custom"},
                "synthesizer_node": {"llm_config_id": 2},
            }
        )
        assert settings.max_agent_hops == 5
        assert settings.planner_node.llm_config_id == 3
        assert settings.planner_node.prompt == "custom"
        assert settings.synthesizer_node.llm_config_id == 2
        assert settings.synthesizer_node.prompt is None

    def test_null_node_config_stripped_by_supervisor_mode(self):
        """SupervisorMode strips None values so autocompact=None does not reach Pydantic."""
        from cadence.constants import Framework
        from cadence.engine.modes.supervisor import SupervisorMode

        mode = SupervisorMode(Framework.LANGGRAPH, {"autocompact": None})
        # Should not raise; autocompact should be default empty NodeConfig
        assert isinstance(mode.settings.autocompact, SupervisorModeNodeConfig)


# ---------------------------------------------------------------------------
# ValidationResponse
# ---------------------------------------------------------------------------


class TestValidationResponse:
    def test_defaults(self):
        v = ValidationResponse(is_valid=True, reasoning="ok")
        assert v.is_valid is True
        assert v.valid_ids is None
        assert v.clarification_type == []
        assert v.query_intent == ""

    def test_invalid_with_types(self):
        v = ValidationResponse(
            is_valid=False,
            reasoning="no match",
            clarification_type=["insufficient_results"],
            query_intent="find product X",
        )
        assert v.is_valid is False
        assert "insufficient_results" in v.clarification_type


# ---------------------------------------------------------------------------
# GraphNode / NodeDisplay
# ---------------------------------------------------------------------------


class TestGraphNodeAndDisplay:
    def test_graph_node_values(self):
        values = GraphNode.values()
        assert "router" in values
        assert "planner" in values
        assert "executor" in values
        assert "synthesizer" in values
        assert "clarifier" in values
        assert "responder" in values
        assert "error_handler" in values

    def test_token_streaming_nodes(self):
        streaming = NodeDisplay.token_streaming_nodes()
        assert "synthesizer" in streaming
        assert "clarifier" in streaming
        assert "responder" in streaming
        assert "error_handler" in streaming
        assert "router" not in streaming
        assert "planner" not in streaming

    def test_node_display_get_by_name(self):
        meta = NodeDisplay.get_by_name("synthesizer")
        assert 80 <= meta.get("progress") <= 95
        assert "key" in meta

    def test_convenience_dict_covers_all_nodes(self):
        d = NodeDisplay.to_convenience_dict()
        for node in GraphNode:
            assert node.value in d


# ---------------------------------------------------------------------------
# SupervisorToolCollector
# ---------------------------------------------------------------------------


class TestSupervisorToolCollector:
    def test_collect_all_tools(self):
        bundles = {
            "plugin_a": _make_mock_bundle("plugin_a"),
            "plugin_b": _make_mock_bundle("plugin_b"),
        }
        collector = SupervisorToolCollector(bundles)
        tools = collector.collect_all_tools()
        assert len(tools) == 2

    def test_get_plugin_for_tool(self):
        bundles = {"plugin_a": _make_mock_bundle("plugin_a")}
        collector = SupervisorToolCollector(bundles)
        collector.collect_all_tools()
        assert collector.get_plugin_for_tool("plugin_a_search") == "plugin_a"
        assert collector.get_plugin_for_tool("nonexistent") is None

    def test_get_tools_for_plugin(self):
        bundles = {"plugin_a": _make_mock_bundle("plugin_a")}
        collector = SupervisorToolCollector(bundles)
        tools = collector.get_tools_for_plugin("plugin_a")
        assert len(tools) == 1

    def test_get_plugin_capabilities(self):
        bundles = {"plugin_a": _make_mock_bundle("plugin_a")}
        collector = SupervisorToolCollector(bundles)
        caps = collector.get_plugin_capabilities()
        assert "plugin_a" in caps


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


class TestGraphBuilds:
    def test_graph_builds_without_error(self):
        supervisor = _make_supervisor()
        assert supervisor._is_ready is True
        assert supervisor.graph is not None

    def test_health_check_returns_ready(self):
        supervisor = _make_supervisor()
        result = asyncio.get_event_loop().run_until_complete(supervisor.health_check())
        assert result["is_ready"] is True
        assert result["mode"] == "supervisor"

    def test_health_check_includes_validation_flag(self):
        supervisor = _make_supervisor({"enabled_llm_validation": True})
        result = asyncio.get_event_loop().run_until_complete(supervisor.health_check())
        assert result["enabled_llm_validation"] is True

    def test_validator_node_absent_when_disabled(self):
        supervisor = _make_supervisor({"enabled_llm_validation": False})
        graph_nodes = set(supervisor.graph.nodes)
        assert GraphNode.VALIDATOR.value not in graph_nodes

    def test_validator_node_present_when_enabled(self):
        supervisor = _make_supervisor({"enabled_llm_validation": True})
        graph_nodes = set(supervisor.graph.nodes)
        assert GraphNode.VALIDATOR.value in graph_nodes


# ---------------------------------------------------------------------------
# Per-node model resolution
# ---------------------------------------------------------------------------


class TestPerNodeModelResolution:
    @pytest.mark.asyncio
    async def test_node_falls_back_to_default_llm_config_id(self):
        """Node with llm_config_id=None uses resolved_config default_llm_config_id."""
        supervisor = await _make_supervisor_async(default_llm_config_id=42)
        supervisor.llm_factory.create_model_by_id.assert_awaited()
        calls = supervisor.llm_factory.create_model_by_id.await_args_list
        for call in calls:
            assert call.args[1] == 42

    @pytest.mark.asyncio
    async def test_node_specific_llm_config_id_used(self):
        """Node with llm_config_id overrides the instance default."""
        mode_config = {
            "synthesizer_node": {"llm_config_id": 99},
        }
        supervisor = await _make_supervisor_async(
            mode_config=mode_config, default_llm_config_id=1
        )
        calls = supervisor.llm_factory.create_model_by_id.await_args_list
        config_ids_used = [c.args[1] for c in calls]
        assert 99 in config_ids_used

    @pytest.mark.asyncio
    async def test_planner_node_config_key_used(self):
        """planner_node llm_config_id is used for planner model."""
        mode_config = {"planner_node": {"llm_config_id": 77}}
        supervisor = await _make_supervisor_async(
            mode_config=mode_config, default_llm_config_id=1
        )
        calls = supervisor.llm_factory.create_model_by_id.await_args_list
        config_ids_used = [c.args[1] for c in calls]
        assert 77 in config_ids_used

    @pytest.mark.asyncio
    async def test_raises_when_no_llm_config_id(self):
        """_create_model_for_node raises ValueError when no config ID available."""
        bundles = {"p": _make_mock_bundle("p")}
        plugin_manager = MagicMock()
        plugin_manager.bundles = bundles
        plugin_manager.cleanup_all = AsyncMock()

        llm_factory = MagicMock()
        llm_factory.create_model_by_id = AsyncMock(return_value=MagicMock())

        supervisor = LangGraphSupervisor(
            plugin_manager=plugin_manager,
            llm_factory=llm_factory,
            resolved_config={"org_id": "x"},  # no default_llm_config_id
            adapter=MagicMock(),
            streaming_wrapper=MagicMock(),
        )
        with pytest.raises(ValueError, match="No llm_config_id"):
            await supervisor._create_model_for_node(SupervisorModeNodeConfig())


# ---------------------------------------------------------------------------
# Prompt overrides
# ---------------------------------------------------------------------------


class TestPromptOverrides:
    @pytest.mark.asyncio
    async def test_default_planner_prompt_used_when_no_override(self):
        from cadence.engine.impl.langgraph.supervisor.prompts import SupervisorPrompts

        supervisor = await _make_supervisor_async()
        node_settings = supervisor.mode_config.settings.planner_node
        template = node_settings.prompt or SupervisorPrompts.PLANNER
        assert template is SupervisorPrompts.PLANNER

    @pytest.mark.asyncio
    async def test_custom_planner_prompt_stored_in_settings(self):
        custom = (
            "Custom planner {current_time} {plugin_descriptions} {tool_descriptions}"
        )
        mode_config = {"planner_node": {"prompt_override": custom}}
        supervisor = await _make_supervisor_async(mode_config=mode_config)
        node_settings = supervisor.mode_config.settings.planner_node
        assert node_settings.prompt == custom

    @pytest.mark.asyncio
    async def test_planner_node_uses_override_in_execution(self):
        """planner_node.prompt_override is applied inside run_planner_node."""
        custom = "Custom {current_time} {plugin_descriptions} {tool_descriptions}"
        mode_config = {"planner_node": {"prompt_override": custom}}
        supervisor = await _make_supervisor_async(mode_config=mode_config)

        state = {
            "messages": [HumanMessage(content="hello")],
            "agent_hops": 0,
            "current_agent": "",
            "error_state": None,
            "validation_result": None,
            "used_plugins": [],
            "routing_decision": "tools",
            "tool_results": None,
        }
        captured_messages = []

        async def capture_ainvoke(messages):
            captured_messages.extend(messages)
            return AIMessage(content="", tool_calls=[])

        supervisor._planner_model.ainvoke = capture_ainvoke
        await run_planner_node(
            state,
            model=supervisor._planner_model,
            settings=supervisor.mode_config.settings,
            plugin_bundles=supervisor._plugin_bundles,
        )
        assert captured_messages, "No messages captured"
        system_content = captured_messages[0].content
        assert system_content.startswith("Custom ")


# ---------------------------------------------------------------------------
# Routing: _route_from_router
# ---------------------------------------------------------------------------


class TestRouteFromRouter:
    def _make_state(self, routing_decision=None, error_state=None):
        return {
            "messages": [],
            "agent_hops": 0,
            "current_agent": "",
            "error_state": error_state,
            "validation_result": None,
            "used_plugins": [],
            "routing_decision": routing_decision,
            "tool_results": None,
        }

    def test_tools_decision_routes_to_planner(self):
        supervisor = _make_supervisor()
        state = self._make_state(routing_decision="tools")
        assert supervisor._route_from_router(state) == GraphNode.PLANNER.value

    def test_conversational_decision_routes_to_responder(self):
        supervisor = _make_supervisor()
        state = self._make_state(routing_decision="conversational")
        assert supervisor._route_from_router(state) == GraphNode.RESPONDER.value

    def test_clarify_decision_routes_to_clarifier(self):
        supervisor = _make_supervisor()
        state = self._make_state(routing_decision="clarify")
        assert supervisor._route_from_router(state) == GraphNode.CLARIFIER.value

    def test_unknown_decision_falls_back_to_clarifier(self):
        supervisor = _make_supervisor()
        state = self._make_state(routing_decision="unknown_value")
        assert supervisor._route_from_router(state) == GraphNode.CLARIFIER.value

    def test_none_decision_falls_back_to_clarifier(self):
        supervisor = _make_supervisor()
        state = self._make_state(routing_decision=None)
        assert supervisor._route_from_router(state) == GraphNode.CLARIFIER.value

    def test_routes_to_error_handler_on_error_state(self):
        supervisor = _make_supervisor()
        state = self._make_state(
            routing_decision="tools",
            error_state={"node": "router", "error_type": "SystemError"},
        )
        assert supervisor._route_from_router(state) == GraphNode.ERROR_HANDLER.value


# ---------------------------------------------------------------------------
# Routing: _route_from_planner
# ---------------------------------------------------------------------------


class TestRouteFromPlanner:
    def _make_state(self, messages, agent_hops=0, error_state=None):
        return {
            "messages": messages,
            "agent_hops": agent_hops,
            "current_agent": GraphNode.PLANNER.value,
            "error_state": error_state,
            "validation_result": None,
            "used_plugins": [],
            "routing_decision": "tools",
            "tool_results": None,
        }

    def test_routes_to_executor_on_tool_calls(self):
        supervisor = _make_supervisor()
        msg = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "io.cadence.test.plugin_search",
                    "args": {"q": "x"},
                    "id": "tc1",
                    "type": "tool_call",
                }
            ],
        )
        state = self._make_state([msg])
        assert supervisor._route_from_planner(state) == GraphNode.EXECUTOR.value

    def test_routes_to_synthesizer_when_no_tool_calls(self):
        supervisor = _make_supervisor()
        msg = AIMessage(content="direct answer")
        state = self._make_state([msg])
        assert supervisor._route_from_planner(state) == GraphNode.SYNTHESIZER.value

    def test_routes_to_synthesizer_on_max_hops(self):
        supervisor = _make_supervisor({"max_agent_hops": 2})
        msg = AIMessage(content="no tools")
        state = self._make_state([msg], agent_hops=10)
        assert supervisor._route_from_planner(state) == GraphNode.SYNTHESIZER.value

    def test_routes_to_error_handler_on_error_state(self):
        supervisor = _make_supervisor()
        state = self._make_state(
            [], error_state={"node": "planner", "error_type": "SystemError"}
        )
        assert supervisor._route_from_planner(state) == GraphNode.ERROR_HANDLER.value


# ---------------------------------------------------------------------------
# Routing: _route_from_executor (when validation enabled)
# ---------------------------------------------------------------------------


class TestRouteFromExecutor:
    def _make_state(self, error_state=None):
        return {
            "messages": [],
            "agent_hops": 0,
            "current_agent": GraphNode.EXECUTOR.value,
            "error_state": error_state,
            "validation_result": None,
            "used_plugins": [],
            "routing_decision": "tools",
            "tool_results": [],
        }

    def test_routes_to_validator_normally(self):
        supervisor = _make_supervisor({"enabled_llm_validation": True})
        assert (
            supervisor._route_from_executor(self._make_state())
            == GraphNode.VALIDATOR.value
        )

    def test_routes_to_error_handler_on_error(self):
        supervisor = _make_supervisor({"enabled_llm_validation": True})
        state = self._make_state(error_state={"node": GraphNode.EXECUTOR.value})
        assert supervisor._route_from_executor(state) == GraphNode.ERROR_HANDLER.value


# ---------------------------------------------------------------------------
# Routing: _route_from_validator
# ---------------------------------------------------------------------------


class TestRouteFromValidator:
    def _make_state(self, validation_result=None, error_state=None):
        return {
            "messages": [],
            "agent_hops": 0,
            "current_agent": GraphNode.VALIDATOR.value,
            "error_state": error_state,
            "validation_result": validation_result,
            "used_plugins": [],
            "routing_decision": "tools",
            "tool_results": [],
        }

    def test_routes_to_synthesizer_when_passed(self):
        supervisor = _make_supervisor()
        state = self._make_state({"passed": True})
        assert supervisor._route_from_validator(state) == GraphNode.SYNTHESIZER.value

    def test_routes_to_clarifier_when_failed(self):
        supervisor = _make_supervisor()
        state = self._make_state({"passed": False})
        assert supervisor._route_from_validator(state) == GraphNode.CLARIFIER.value

    def test_routes_to_error_handler_on_error(self):
        supervisor = _make_supervisor()
        state = self._make_state(error_state={"node": GraphNode.VALIDATOR.value})
        assert supervisor._route_from_validator(state) == GraphNode.ERROR_HANDLER.value


# ---------------------------------------------------------------------------
# Executor node: attributed tool_results
# ---------------------------------------------------------------------------


class TestExecutorNodeToolResults:
    @pytest.mark.asyncio
    async def test_executor_populates_attributed_tool_results(self):
        """run_executor_node populates tool_results with plugin attribution."""
        import json as _json

        tool_call_id = "tc-abc123"
        tool_name = "plugin_a_search"
        plugin_id = "plugin_a"
        result_data = {"items": [{"id": 1, "name": "Test"}]}

        tool_message = ToolMessage(
            content=_json.dumps(result_data),
            tool_call_id=tool_call_id,
        )

        mock_tool_node = MagicMock()
        mock_tool_node.ainvoke = AsyncMock(return_value={"messages": [tool_message]})

        mock_collector = MagicMock()
        mock_collector.get_plugin_for_tool = MagicMock(return_value=plugin_id)

        mock_settings = MagicMock()
        mock_settings.node_execution_timeout = 60

        ai_msg = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": tool_name,
                    "args": {"q": "test"},
                    "id": tool_call_id,
                    "type": "tool_call",
                }
            ],
        )
        state = {
            "messages": [HumanMessage(content="find me stuff"), ai_msg],
            "agent_hops": 1,
            "current_agent": GraphNode.PLANNER.value,
            "error_state": None,
            "validation_result": None,
            "used_plugins": [],
            "routing_decision": "tools",
            "tool_results": None,
        }

        result = await run_executor_node(
            state,
            tool_node=mock_tool_node,
            tool_collector=mock_collector,
            settings=mock_settings,
        )

        assert "tool_results" in result
        assert len(result["tool_results"]) == 1
        tr = result["tool_results"][0]
        assert tr["tool_name"] == tool_name
        assert tr["plugin_id"] == plugin_id
        assert tr["data"] == result_data
        assert tr["error"] is None


# ---------------------------------------------------------------------------
# Synthesizer reads tool_results field
# ---------------------------------------------------------------------------


class TestSynthesizerReadsToolResults:
    @pytest.mark.asyncio
    async def test_synthesizer_reads_tool_results_not_messages(self):
        """run_synthesizer_node includes tool_results data in request, not scanning messages."""
        supervisor = await _make_supervisor_async()

        tool_results = [
            {
                "tool_name": "plugin_search",
                "plugin_id": "plugin_a",
                "data": {"id": 1},
                "error": None,
            }
        ]
        state = {
            "messages": [HumanMessage(content="find items")],
            "agent_hops": 1,
            "current_agent": GraphNode.EXECUTOR.value,
            "error_state": None,
            "validation_result": None,
            "used_plugins": [],
            "routing_decision": "tools",
            "tool_results": tool_results,
        }

        captured = []

        async def capture(messages):
            captured.extend(messages)
            return AIMessage(content="synthesized answer")

        supervisor._synthesizer_model.ainvoke = capture
        result = await run_synthesizer_node(
            state,
            model=supervisor._synthesizer_model,
            settings=supervisor.mode_config.settings,
            plugin_bundles=supervisor._plugin_bundles,
        )

        assert result["current_agent"] == GraphNode.SYNTHESIZER.value
        assert result["tool_results"] is None  # cleared after synthesis
        full_content = " ".join(m.content for m in captured if hasattr(m, "content"))
        assert "plugin_search" in full_content or "Tool results" in full_content

    @pytest.mark.asyncio
    async def test_synthesizer_clears_tool_results_in_output(self):
        supervisor = await _make_supervisor_async()
        state = {
            "messages": [HumanMessage(content="test")],
            "agent_hops": 0,
            "current_agent": "",
            "error_state": None,
            "validation_result": None,
            "used_plugins": [],
            "routing_decision": "tools",
            "tool_results": [
                {"tool_name": "t", "plugin_id": "p", "data": {}, "error": None}
            ],
        }
        supervisor._synthesizer_model.ainvoke = AsyncMock(
            return_value=AIMessage(content="done")
        )
        result = await run_synthesizer_node(
            state,
            model=supervisor._synthesizer_model,
            settings=supervisor.mode_config.settings,
            plugin_bundles=supervisor._plugin_bundles,
        )
        assert result.get("tool_results") is None


# ---------------------------------------------------------------------------
# run_error_handler_node
# ---------------------------------------------------------------------------


class TestErrorHandlerNode:
    @pytest.mark.asyncio
    async def test_returns_ai_message_on_exception_state(self):
        supervisor = await _make_supervisor_async()
        state = {
            "messages": [HumanMessage(content="find me something")],
            "agent_hops": 0,
            "current_agent": GraphNode.PLANNER.value,
            "error_state": {
                "node": GraphNode.PLANNER.value,
                "error_type": "SystemError",
                "error_message": "Connection refused",
                "timestamp": "2026-01-01T00:00:00Z",
            },
            "validation_result": None,
            "used_plugins": [],
            "routing_decision": "tools",
            "tool_results": None,
        }
        result = await run_error_handler_node(
            state,
            model=supervisor._error_model,
            settings=supervisor.mode_config.settings,
        )
        assert "messages" in result
        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], AIMessage)

    @pytest.mark.asyncio
    async def test_fallback_on_error_model_failure(self):
        supervisor = await _make_supervisor_async()
        error_model = MagicMock()
        error_model.ainvoke = AsyncMock(side_effect=RuntimeError("model down"))

        state = {
            "messages": [HumanMessage(content="help")],
            "agent_hops": 0,
            "current_agent": GraphNode.PLANNER.value,
            "error_state": {
                "node": GraphNode.PLANNER.value,
                "error_type": "SystemError",
                "error_message": "boom",
            },
            "validation_result": None,
            "used_plugins": [],
            "routing_decision": "tools",
            "tool_results": None,
        }
        result = await run_error_handler_node(
            state,
            model=error_model,
            settings=supervisor.mode_config.settings,
        )
        assert "messages" in result
        assert isinstance(result["messages"][0], AIMessage)
        assert (
            "apologise" in result["messages"][0].content.lower()
            or "encountered" in result["messages"][0].content.lower()
        )


# ---------------------------------------------------------------------------
# Context window guard in run_router_node
# ---------------------------------------------------------------------------


def _make_router_state(messages):
    return {
        "messages": messages,
        "agent_hops": 0,
        "current_agent": "",
        "error_state": None,
        "validation_result": None,
        "used_plugins": [],
        "routing_decision": None,
        "tool_results": None,
    }


class TestRouterContextWindowGuard:
    @pytest.mark.asyncio
    async def test_router_routes_to_error_when_context_exceeded(self):
        """Router returns error_state when token count exceeds max_context_window."""
        settings = LangGraphSupervisorSettings.model_validate(
            {"max_context_window": 10, "enabled_auto_compact": False}
        )
        # 4 chars/token × 10 tokens = 40 chars minimum to exceed limit of 10 tokens
        big_content = "x" * 200  # 50 tokens — well above limit of 10
        state = _make_router_state([HumanMessage(content=big_content)])

        mock_model = MagicMock()
        mock_model.ainvoke = AsyncMock()

        result = await run_router_node(
            state,
            model=mock_model,
            settings=settings,
            plugin_bundles={},
        )

        assert result.get("error_state") is not None
        mock_model.ainvoke.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_router_continues_when_context_within_budget(self):
        """Router proceeds normally when token count is within max_context_window."""
        from cadence.engine.impl.langgraph.supervisor.nodes import RoutingDecision as RD

        settings = LangGraphSupervisorSettings.model_validate(
            {"max_context_window": 1000}
        )
        state = _make_router_state([HumanMessage(content="hello")])

        mock_model = MagicMock()
        mock_model.ainvoke = AsyncMock(return_value=RD(route="conversational"))

        result = await run_router_node(
            state,
            model=mock_model,
            settings=settings,
            plugin_bundles={},
        )

        assert result.get("error_state") is None
        assert result.get("routing_decision") == "conversational"
