"""Unit tests for the LangGraph 7-node supervisor implementation.

Covers:
- Graph builds without errors
- _route_from_supervisor: facilitator, conversational, control_tools routing
- _route_from_control_tools: validation routing
- _route_from_validation: synthesizer vs facilitator based on passed flag
- _error_handler_node: returns a user-friendly AIMessage on exception state
- ValidationResponse model construction
- LangGraphSupervisorSettings: defaults and model_validate
- Per-node model resolution: node llm_config_id, instance default_llm_config_id
- Prompt overrides: custom template used when set, default when not
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import StructuredTool

# Pre-load engine module to avoid circular import issues
import cadence.engine.factory  # noqa: F401
from cadence.engine.impl.langgraph.supervisor.core import (
    LangGraphSupervisor,
    ValidationResponse,
)
from cadence.engine.impl.langgraph.supervisor.settings import (
    LangGraphSupervisorSettings,
    NodeConfig,
)
from cadence.engine.impl.langgraph.supervisor.tool_collector import (
    SupervisorToolCollector,
)

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
    # Use a real LangChain tool so ToolNode doesn't complain
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
        assert settings.parallel_tool_calls is True
        assert settings.invoke_timeout == 60
        assert settings.use_llm_validation is False
        assert settings.enable_synthesizer is True
        assert settings.enable_facilitator is True
        assert settings.enable_conversational is True
        assert settings.supervisor_timeout == 60

    def test_node_defaults(self):
        settings = LangGraphSupervisorSettings.model_validate({})
        assert settings.supervisor_node.llm_config_id is None
        assert settings.supervisor_node.prompt_override is None
        assert settings.synthesizer_node.llm_config_id is None
        assert settings.validation_node.llm_config_id is None
        assert settings.facilitator_node.llm_config_id is None
        assert settings.conversational_node.llm_config_id is None
        assert settings.error_handler_node.llm_config_id is None

    def test_node_config_from_dict(self):
        settings = LangGraphSupervisorSettings.model_validate(
            {
                "max_agent_hops": 5,
                "supervisor_node": {"llm_config_id": 3, "prompt_override": "custom"},
                "synthesizer_node": {"llm_config_id": 2},
            }
        )
        assert settings.max_agent_hops == 5
        assert settings.supervisor_node.llm_config_id == 3
        assert settings.supervisor_node.prompt_override == "custom"
        assert settings.synthesizer_node.llm_config_id == 2
        assert settings.synthesizer_node.prompt_override is None


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

    def test_health_check_includes_node_flags(self):
        supervisor = _make_supervisor({"enable_facilitator": False})
        result = asyncio.get_event_loop().run_until_complete(supervisor.health_check())
        assert result["enable_facilitator"] is False


# ---------------------------------------------------------------------------
# Per-node model resolution
# ---------------------------------------------------------------------------


class TestPerNodeModelResolution:
    @pytest.mark.asyncio
    async def test_node_falls_back_to_default_llm_config_id(self):
        """Node with llm_config_id=None uses resolved_config default_llm_config_id."""
        supervisor = await _make_supervisor_async(default_llm_config_id=42)
        # All node configs have llm_config_id=None by default → should use 42
        supervisor.llm_factory.create_model_by_id.assert_awaited()
        calls = supervisor.llm_factory.create_model_by_id.await_args_list
        # Every call should have used config_id=42
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
        # At least one call should have used config_id=99 (synthesizer)
        config_ids_used = [c.args[1] for c in calls]
        assert 99 in config_ids_used

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
            await supervisor._create_model_for_node(NodeConfig())


# ---------------------------------------------------------------------------
# Prompt overrides
# ---------------------------------------------------------------------------


class TestPromptOverrides:
    @pytest.mark.asyncio
    async def test_default_prompt_used_when_no_override(self):
        from cadence.engine.impl.langgraph.supervisor.prompts import SupervisorPrompts

        supervisor = await _make_supervisor_async()
        # supervisor_node has no prompt_override → default template used
        node_settings = supervisor.mode_config.settings.supervisor_node
        template = node_settings.prompt_override or SupervisorPrompts.SUPERVISOR
        assert template is SupervisorPrompts.SUPERVISOR

    @pytest.mark.asyncio
    async def test_custom_prompt_used_when_override_set(self):
        custom = (
            "Custom supervisor {current_time} {plugin_descriptions} {tool_descriptions}"
        )
        mode_config = {
            "supervisor_node": {"prompt_override": custom},
        }
        supervisor = await _make_supervisor_async(mode_config=mode_config)
        node_settings = supervisor.mode_config.settings.supervisor_node
        assert node_settings.prompt_override == custom

    @pytest.mark.asyncio
    async def test_supervisor_node_uses_override_in_node_method(self):
        """supervisor_node.prompt_override is applied inside _supervisor_node."""
        custom = "Custom {current_time} {plugin_descriptions} {tool_descriptions}"
        mode_config = {"supervisor_node": {"prompt_override": custom}}
        supervisor = await _make_supervisor_async(mode_config=mode_config)

        state = {
            "messages": [HumanMessage(content="hello")],
            "agent_hops": 0,
            "current_agent": "",
            "error_state": None,
            "validation_result": None,
            "used_plugins": [],
            "route_to_facilitator": False,
            "route_to_conversational": False,
        }
        # Capture the system message passed to ainvoke
        captured_messages = []

        async def capture_ainvoke(messages):
            captured_messages.extend(messages)
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "call_facilitator",
                        "args": {},
                        "id": "tc1",
                        "type": "tool_call",
                    }
                ],
            )

        supervisor._supervisor_model.ainvoke = capture_ainvoke
        await supervisor._supervisor_node(state)
        assert captured_messages, "No messages captured"
        system_content = captured_messages[0].content
        assert system_content.startswith("Custom ")


# ---------------------------------------------------------------------------
# Routing: _route_from_supervisor
# ---------------------------------------------------------------------------


class TestRouteFromSupervisor:
    def _make_state(self, messages, agent_hops=0, error_state=None):
        return {
            "messages": messages,
            "agent_hops": agent_hops,
            "current_agent": "",
            "error_state": error_state,
            "validation_result": None,
            "used_plugins": [],
            "route_to_facilitator": False,
            "route_to_conversational": False,
        }

    def test_routes_to_error_handler_on_error_state(self):
        supervisor = _make_supervisor()
        state = self._make_state(
            [], error_state={"node": "supervisor", "error_type": "SystemError"}
        )
        assert supervisor._route_from_supervisor(state) == "error_handler"

    def test_routes_to_facilitator_on_call_facilitator_tool(self):
        supervisor = _make_supervisor()
        msg = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "call_facilitator",
                    "args": {},
                    "id": "tc1",
                    "type": "tool_call",
                }
            ],
        )
        state = self._make_state([msg])
        assert supervisor._route_from_supervisor(state) == "facilitator"

    def test_routes_to_conversational_on_call_conversational_tool(self):
        supervisor = _make_supervisor()
        msg = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "call_conversational",
                    "args": {},
                    "id": "tc1",
                    "type": "tool_call",
                }
            ],
        )
        state = self._make_state([msg])
        assert supervisor._route_from_supervisor(state) == "conversational"

    def test_routes_to_control_tools_on_real_tool_call(self):
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
        assert supervisor._route_from_supervisor(state) == "control_tools"

    def test_routes_to_facilitator_on_max_hops(self):
        supervisor = _make_supervisor({"max_agent_hops": 2})
        msg = AIMessage(content="no tools")
        state = self._make_state([msg], agent_hops=10)
        result = supervisor._route_from_supervisor(state)
        assert result in ("facilitator", "error_handler")

    def test_routes_to_synthesizer_when_no_tool_calls_and_synthesizer_enabled(self):
        supervisor = _make_supervisor({"enable_synthesizer": True})
        msg = AIMessage(content="direct answer")
        state = self._make_state([msg])
        assert supervisor._route_from_supervisor(state) == "synthesizer"


# ---------------------------------------------------------------------------
# Routing: _route_from_control_tools
# ---------------------------------------------------------------------------


class TestRouteFromControlTools:
    def _make_state(self, error_state=None):
        return {
            "messages": [],
            "agent_hops": 0,
            "current_agent": "control_tools",
            "error_state": error_state,
            "validation_result": None,
            "used_plugins": [],
            "route_to_facilitator": False,
            "route_to_conversational": False,
        }

    def test_routes_to_validation_normally(self):
        supervisor = _make_supervisor()
        assert supervisor._route_from_control_tools(self._make_state()) == "validation"

    def test_routes_to_error_handler_on_error(self):
        supervisor = _make_supervisor()
        state = self._make_state(error_state={"node": "control_tools"})
        assert supervisor._route_from_control_tools(state) == "error_handler"


# ---------------------------------------------------------------------------
# Routing: _route_from_validation
# ---------------------------------------------------------------------------


class TestRouteFromValidation:
    def _make_state(self, validation_result=None, error_state=None):
        return {
            "messages": [],
            "agent_hops": 0,
            "current_agent": "validation",
            "error_state": error_state,
            "validation_result": validation_result,
            "used_plugins": [],
            "route_to_facilitator": False,
            "route_to_conversational": False,
        }

    def test_routes_to_synthesizer_when_passed(self):
        supervisor = _make_supervisor()
        state = self._make_state({"passed": True})
        assert supervisor._route_from_validation(state) == "synthesizer"

    def test_routes_to_facilitator_when_failed(self):
        supervisor = _make_supervisor()
        state = self._make_state({"passed": False})
        assert supervisor._route_from_validation(state) == "facilitator"

    def test_routes_to_error_handler_on_error(self):
        supervisor = _make_supervisor()
        state = self._make_state(error_state={"node": "validation"})
        assert supervisor._route_from_validation(state) == "error_handler"


# ---------------------------------------------------------------------------
# _error_handler_node
# ---------------------------------------------------------------------------


class TestErrorHandlerNode:
    @pytest.mark.asyncio
    async def test_returns_ai_message_on_exception_state(self):
        supervisor = await _make_supervisor_async()
        state = {
            "messages": [HumanMessage(content="find me something")],
            "agent_hops": 0,
            "current_agent": "supervisor",
            "error_state": {
                "node": "supervisor",
                "error_type": "SystemError",
                "error_message": "Connection refused",
                "timestamp": "2026-01-01T00:00:00Z",
            },
            "validation_result": None,
            "used_plugins": [],
            "route_to_facilitator": False,
            "route_to_conversational": False,
        }
        result = await supervisor._error_handler_node(state)
        assert "messages" in result
        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], AIMessage)

    @pytest.mark.asyncio
    async def test_fallback_on_error_model_failure(self):
        supervisor = await _make_supervisor_async()
        # Make error model raise
        supervisor._error_model = MagicMock()
        supervisor._error_model.ainvoke = AsyncMock(
            side_effect=RuntimeError("model down")
        )

        state = {
            "messages": [HumanMessage(content="help")],
            "agent_hops": 0,
            "current_agent": "supervisor",
            "error_state": {
                "node": "supervisor",
                "error_type": "SystemError",
                "error_message": "boom",
            },
            "validation_result": None,
            "used_plugins": [],
            "route_to_facilitator": False,
            "route_to_conversational": False,
        }
        result = await supervisor._error_handler_node(state)
        assert "messages" in result
        assert isinstance(result["messages"][0], AIMessage)
        assert (
            "apologise" in result["messages"][0].content.lower()
            or "encountered" in result["messages"][0].content.lower()
        )
