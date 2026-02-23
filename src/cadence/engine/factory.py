"""Orchestrator factory for creating orchestrator instances.

This module provides a factory for building complete orchestrator instances
based on framework type (LangGraph, OpenAI, Google) and mode (supervisor, coordinator, handoff).
"""

import logging
from typing import Any, Type

from cadence.engine.base import BaseOrchestrator, OrchestratorAdapter
from cadence.engine.impl.google_adk import (
    GoogleADKAdapter,
    GoogleADKCoordinator,
    GoogleADKHandoff,
    GoogleADKStreamingWrapper,
    GoogleADKSupervisor,
)
from cadence.engine.impl.langgraph import (
    LangChainAdapter,
    LangGraphCoordinator,
    LangGraphHandoff,
    LangGraphStreamingWrapper,
    LangGraphSupervisor,
)
from cadence.engine.impl.openai_agents import (
    OpenAIAgentsAdapter,
    OpenAIAgentsStreamingWrapper,
    OpenAICoordinator,
    OpenAIHandoff,
    OpenAISupervisor,
)
from cadence.engine.shared_resources.bundle_cache import SharedBundleCache
from cadence.infrastructure.llm.factory import LLMModelFactory
from cadence.infrastructure.plugins import SDKPluginManager
from cadence.repository.plugin_store_repository import PluginStoreRepository

logger = logging.getLogger(__name__)


class OrchestratorFactory:
    """Factory for creating orchestrator instances.

    The factory maintains a registry mapping (framework_type, mode) pairs
    to appropriate adapter, orchestrator, and streaming wrapper classes.

    Attributes:
        registry: Dict mapping (framework, mode) to component classes
        llm_factory: LLM model factory
        tenant_plugins_root: Root directory for tenant plugins
        system_plugins_dir: System-wide plugins directory
    """

    def __init__(
        self,
        llm_factory: LLMModelFactory,
        tenant_plugins_root: str,
        system_plugins_dir: str | None = None,
        plugin_store: PluginStoreRepository | None = None,
        bundle_cache: SharedBundleCache | None = None,
    ):
        """Initialize orchestrator factory.

        Args:
            llm_factory: LLM model factory
            tenant_plugins_root: Root directory for tenant plugins
            system_plugins_dir: Optional system plugins directory
            plugin_store: Optional PluginStore for S3-backed plugin downloads
            bundle_cache: Optional SharedBundleCache for stateless bundle reuse
        """
        self.llm_factory = llm_factory
        self.tenant_plugins_root = tenant_plugins_root
        self.system_plugins_dir = system_plugins_dir
        self.plugin_store = plugin_store
        self.bundle_cache = bundle_cache

        self.registry: dict[tuple[str, str], dict[str, Type]] = {}
        self._initialize_registry()

    def _initialize_registry(self) -> None:
        """Initialize backend registry with available implementations."""
        self.registry[("langgraph", "supervisor")] = {
            "adapter_class": LangChainAdapter,
            "orchestrator_class": LangGraphSupervisor,
            "streaming_wrapper_class": LangGraphStreamingWrapper,
        }

        self.registry[("langgraph", "coordinator")] = {
            "adapter_class": LangChainAdapter,
            "orchestrator_class": LangGraphCoordinator,
            "streaming_wrapper_class": LangGraphStreamingWrapper,
        }

        self.registry[("langgraph", "handoff")] = {
            "adapter_class": LangChainAdapter,
            "orchestrator_class": LangGraphHandoff,
            "streaming_wrapper_class": LangGraphStreamingWrapper,
        }

        self.registry[("openai_agents", "supervisor")] = {
            "adapter_class": OpenAIAgentsAdapter,
            "orchestrator_class": OpenAISupervisor,
            "streaming_wrapper_class": OpenAIAgentsStreamingWrapper,
        }

        self.registry[("openai_agents", "coordinator")] = {
            "adapter_class": OpenAIAgentsAdapter,
            "orchestrator_class": OpenAICoordinator,
            "streaming_wrapper_class": OpenAIAgentsStreamingWrapper,
        }

        self.registry[("openai_agents", "handoff")] = {
            "adapter_class": OpenAIAgentsAdapter,
            "orchestrator_class": OpenAIHandoff,
            "streaming_wrapper_class": OpenAIAgentsStreamingWrapper,
        }

        self.registry[("google_adk", "supervisor")] = {
            "adapter_class": GoogleADKAdapter,
            "orchestrator_class": GoogleADKSupervisor,
            "streaming_wrapper_class": GoogleADKStreamingWrapper,
        }

        self.registry[("google_adk", "coordinator")] = {
            "adapter_class": GoogleADKAdapter,
            "orchestrator_class": GoogleADKCoordinator,
            "streaming_wrapper_class": GoogleADKStreamingWrapper,
        }

        self.registry[("google_adk", "handoff")] = {
            "adapter_class": GoogleADKAdapter,
            "orchestrator_class": GoogleADKHandoff,
            "streaming_wrapper_class": GoogleADKStreamingWrapper,
        }

    async def create(
        self,
        framework_type: str,
        mode: str,
        org_id: str,
        instance_config: dict[str, Any],
        resolved_config: dict[str, Any],
    ) -> BaseOrchestrator:
        """Create orchestrator instance.

        Creation pipeline:
        1. Lookup component classes in registry by (framework_type, mode)
        2. Instantiate adapter
        3. Instantiate plugin manager with adapter
        4. Load plugins from instance config
        5. Instantiate streaming wrapper
        6. Instantiate orchestrator with all dependencies
        7. Return ready orchestrator

        Args:
            framework_type: Framework type (langgraph, openai_agents, google_adk)
            mode: Mode (supervisor, coordinator, handoff)
            org_id: Organization ID for tenant isolation
            instance_config: Instance-specific configuration
            resolved_config: Fully resolved configuration (3-tier merged)

        Returns:
            BaseOrchestrator instance

        Raises:
            ValueError: If framework/mode combination not supported
        """
        registry_key = (framework_type, mode)

        if registry_key not in self.registry:
            raise ValueError(
                f"Unsupported orchestrator: framework={framework_type}, mode={mode}. "
                f"Available: {list(self.registry.keys())}"
            )

        components = self.registry[registry_key]

        adapter_class = components["adapter_class"]
        orchestrator_class = components["orchestrator_class"]
        streaming_wrapper_class = components["streaming_wrapper_class"]

        logger.info(f"Creating orchestrator: {framework_type}/{mode} for org {org_id}")

        adapter = adapter_class()

        plugin_manager = SDKPluginManager(
            adapter=adapter,
            llm_factory=self.llm_factory,
            org_id=org_id,
            tenant_plugins_root=self.tenant_plugins_root,
            system_plugins_dir=self.system_plugins_dir,
            plugin_store=self.plugin_store,
            bundle_cache=self.bundle_cache,
        )

        plugin_specs = instance_config.get("active_plugins", [])
        if not plugin_specs:
            logger.warning("No active plugins configured for instance")

        await plugin_manager.load_plugins(plugin_specs, instance_config)

        streaming_wrapper = streaming_wrapper_class()

        orchestrator = orchestrator_class(
            plugin_manager=plugin_manager,
            llm_factory=self.llm_factory,
            resolved_config=resolved_config,
            adapter=adapter,
            streaming_wrapper=streaming_wrapper,
        )

        await orchestrator.initialize()

        logger.info(
            f"Orchestrator created successfully: {orchestrator.framework_type}/{orchestrator.mode}"
        )

        return orchestrator

    def register_backend(
        self,
        framework_type: str,
        mode: str,
        adapter_class: Type[OrchestratorAdapter],
        orchestrator_class: Type[BaseOrchestrator],
        streaming_wrapper_class: Type,
    ) -> None:
        """Register custom backend implementation.

        Allows adding new backends without modifying factory code.

        Args:
            framework_type: Framework type identifier
            mode: Mode identifier
            adapter_class: Adapter class
            orchestrator_class: Orchestrator class
            streaming_wrapper_class: Streaming wrapper class
        """
        registry_key = (framework_type, mode)
        self.registry[registry_key] = {
            "adapter_class": adapter_class,
            "orchestrator_class": orchestrator_class,
            "streaming_wrapper_class": streaming_wrapper_class,
        }

        logger.info(f"Registered custom backend: {framework_type}/{mode}")

    def list_supported_backends(self) -> dict[str, list]:
        """List all supported framework/mode combinations.

        Returns:
            Dictionary mapping framework types to list of supported modes
        """
        backends: dict[str, list] = {}

        for framework_type, mode in self.registry.keys():
            if framework_type not in backends:
                backends[framework_type] = []
            backends[framework_type].append(mode)

        return backends
