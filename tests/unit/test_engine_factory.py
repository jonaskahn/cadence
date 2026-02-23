"""Unit tests for OrchestratorFactory.

Verifies that the factory correctly initialises its registry with all nine
supported (framework, mode) combinations, selects the right component classes
when creating orchestrators, rejects unsupported combinations, and supports
custom backend registration.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cadence.engine.factory import OrchestratorFactory

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def llm_factory() -> MagicMock:
    """Provide a minimal mock LLM factory."""
    mock = MagicMock()
    mock_model = MagicMock()
    mock_model.bind_tools = MagicMock(return_value=mock_model)
    mock.create_model_by_id = AsyncMock(return_value=mock_model)
    return mock


@pytest.fixture
def factory(llm_factory: MagicMock) -> OrchestratorFactory:
    """Provide an OrchestratorFactory with a mock LLM factory."""
    return OrchestratorFactory(
        llm_factory=llm_factory,
        tenant_plugins_root="/tmp/plugins",
        system_plugins_dir="/tmp/sys_plugins",
    )


def _make_plugin_manager_mock() -> MagicMock:
    """Return a mock SDKPluginManager with load_plugins wired as AsyncMock."""
    pm = MagicMock()
    pm.load_plugins = AsyncMock(return_value=None)
    return pm


def _patch_all_component_constructors():
    """Return a context manager that replaces all adapter/orchestrator/streaming/plugin constructors."""
    return patch.multiple(
        "cadence.engine.factory",
        LangChainAdapter=MagicMock(return_value=MagicMock()),
        OpenAIAgentsAdapter=MagicMock(return_value=MagicMock()),
        GoogleADKAdapter=MagicMock(return_value=MagicMock()),
        LangGraphSupervisor=MagicMock(return_value=MagicMock()),
        LangGraphCoordinator=MagicMock(return_value=MagicMock()),
        LangGraphHandoff=MagicMock(return_value=MagicMock()),
        OpenAISupervisor=MagicMock(return_value=MagicMock()),
        OpenAICoordinator=MagicMock(return_value=MagicMock()),
        OpenAIHandoff=MagicMock(return_value=MagicMock()),
        GoogleADKSupervisor=MagicMock(return_value=MagicMock()),
        GoogleADKCoordinator=MagicMock(return_value=MagicMock()),
        GoogleADKHandoff=MagicMock(return_value=MagicMock()),
        LangGraphStreamingWrapper=MagicMock(return_value=MagicMock()),
        OpenAIAgentsStreamingWrapper=MagicMock(return_value=MagicMock()),
        GoogleADKStreamingWrapper=MagicMock(return_value=MagicMock()),
        SDKPluginManager=MagicMock(return_value=_make_plugin_manager_mock()),
    )


# ---------------------------------------------------------------------------
# Registry initialization
# ---------------------------------------------------------------------------


class TestRegistryInitialization:
    """Tests that the factory registers all supported framework/mode combinations."""

    def test_registers_all_langgraph_modes(self, factory: OrchestratorFactory) -> None:
        """Factory registers supervisor, coordinator, and handoff modes for LangGraph."""
        assert ("langgraph", "supervisor") in factory.registry
        assert ("langgraph", "coordinator") in factory.registry
        assert ("langgraph", "handoff") in factory.registry

    def test_total_combinations_is_nine(self, factory: OrchestratorFactory) -> None:
        """Factory initializes exactly nine (framework, mode) registry entries."""
        assert len(factory.registry) == 9

    def test_every_entry_has_required_component_keys(
        self, factory: OrchestratorFactory
    ) -> None:
        """Every registry entry contains adapter_class, orchestrator_class, and streaming_wrapper_class."""
        for combination, components in factory.registry.items():
            assert (
                "adapter_class" in components
            ), f"Missing adapter_class for {combination}"
            assert (
                "orchestrator_class" in components
            ), f"Missing orchestrator_class for {combination}"
            assert (
                "streaming_wrapper_class" in components
            ), f"Missing streaming_wrapper_class for {combination}"


# ---------------------------------------------------------------------------
# list_supported_backends
# ---------------------------------------------------------------------------


class TestListSupportedBackends:
    """Tests for OrchestratorFactory.list_supported_backends."""

    def test_includes_all_three_frameworks(self, factory: OrchestratorFactory) -> None:
        """list_supported_backends returns entries for langgraph, openai_agents, and google_adk."""
        supported = factory.list_supported_backends()

        assert "langgraph" in supported
        assert "openai_agents" in supported
        assert "google_adk" in supported

    def test_each_framework_exposes_three_modes(
        self, factory: OrchestratorFactory
    ) -> None:
        """list_supported_backends lists exactly three modes per framework."""
        supported = factory.list_supported_backends()

        for framework, modes in supported.items():
            assert len(modes) == 3, f"{framework} should have 3 modes"

    def test_langgraph_exposes_supervisor_coordinator_handoff(
        self, factory: OrchestratorFactory
    ) -> None:
        """list_supported_backends includes supervisor, coordinator, and handoff for LangGraph."""
        langgraph_modes = factory.list_supported_backends()["langgraph"]

        assert "supervisor" in langgraph_modes
        assert "coordinator" in langgraph_modes
        assert "handoff" in langgraph_modes


# ---------------------------------------------------------------------------
# register_backend
# ---------------------------------------------------------------------------


class TestRegisterBackend:
    """Tests for OrchestratorFactory.register_backend."""

    def test_adds_new_entry_to_registry(self, factory: OrchestratorFactory) -> None:
        """register_backend makes the new (framework, mode) combination discoverable."""
        factory.register_backend(
            "custom_fw", "custom_mode", MagicMock(), MagicMock(), MagicMock()
        )

        assert ("custom_fw", "custom_mode") in factory.registry

    def test_stores_provided_component_classes(
        self, factory: OrchestratorFactory
    ) -> None:
        """register_backend stores adapter, orchestrator, and streaming wrapper classes."""
        custom_adapter = MagicMock()
        custom_orchestrator = MagicMock()
        custom_streaming = MagicMock()

        factory.register_backend(
            "fw2", "mode2", custom_adapter, custom_orchestrator, custom_streaming
        )

        stored_components = factory.registry[("fw2", "mode2")]
        assert stored_components["adapter_class"] is custom_adapter
        assert stored_components["orchestrator_class"] is custom_orchestrator
        assert stored_components["streaming_wrapper_class"] is custom_streaming

    def test_overrides_existing_entry(self, factory: OrchestratorFactory) -> None:
        """register_backend replaces a previously registered entry for the same combination."""
        replacement_adapter = MagicMock()

        factory.register_backend(
            "langgraph", "supervisor", replacement_adapter, MagicMock(), MagicMock()
        )

        assert (
            factory.registry[("langgraph", "supervisor")]["adapter_class"]
            is replacement_adapter
        )


# ---------------------------------------------------------------------------
# create() – validation
# ---------------------------------------------------------------------------


class TestCreateValidation:
    """Tests for OrchestratorFactory.create — input validation."""

    async def test_raises_for_unsupported_framework(
        self, factory: OrchestratorFactory
    ) -> None:
        """create raises ValueError when the framework type is not registered."""
        with pytest.raises(ValueError, match="Unsupported orchestrator"):
            await factory.create(
                framework_type="unknown_fw",
                mode="supervisor",
                org_id="org_test",
                instance_config={},
                resolved_config={},
            )

    async def test_raises_for_unsupported_mode(
        self, factory: OrchestratorFactory
    ) -> None:
        """create raises ValueError when the mode is not registered for the framework."""
        with pytest.raises(ValueError, match="Unsupported orchestrator"):
            await factory.create(
                framework_type="langgraph",
                mode="unknown_mode",
                org_id="org_test",
                instance_config={},
                resolved_config={},
            )


# ---------------------------------------------------------------------------
# create() – orchestrator instantiation
# ---------------------------------------------------------------------------


class TestCreateOrchestrator:
    """Tests for OrchestratorFactory.create — successful orchestrator creation."""

    async def test_creates_langgraph_supervisor(
        self, factory: OrchestratorFactory
    ) -> None:
        """create produces a LangGraph supervisor orchestrator without errors."""
        with _patch_all_component_constructors():
            result = await factory.create(
                framework_type="langgraph",
                mode="supervisor",
                org_id="org_test",
                instance_config={"active_plugins": []},
                resolved_config={"default_llm_config_id": 1, "org_id": "org_test"},
            )

        assert result is not None

    async def test_loads_active_plugins_from_instance_config(
        self, factory: OrchestratorFactory
    ) -> None:
        """create passes active_plugins pids from instance_config to the plugin manager."""
        with _patch_all_component_constructors():
            mock_plugin_manager = _make_plugin_manager_mock()
            import cadence.engine.factory as factory_module

            factory_module.SDKPluginManager.return_value = mock_plugin_manager

            await factory.create(
                framework_type="langgraph",
                mode="supervisor",
                org_id="org_test",
                instance_config={
                    "active_plugins": [
                        "com.example.plugin_a",
                        "com.example.plugin_b",
                    ]
                },
                resolved_config={"default_llm_config_id": 1, "org_id": "org_test"},
            )

        mock_plugin_manager.load_plugins.assert_awaited_once()
        loaded_plugin_specs = mock_plugin_manager.load_plugins.call_args[0][0]
        assert "com.example.plugin_a" in loaded_plugin_specs
        assert "com.example.plugin_b" in loaded_plugin_specs
