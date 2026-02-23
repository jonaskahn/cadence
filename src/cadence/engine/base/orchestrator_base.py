"""Base orchestrator interface for all backends.

This module defines the abstract orchestrator interface that all orchestrator
implementations must follow, regardless of backend (LangGraph, OpenAI, Google).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, List, Optional

from cadence.engine.base.supervisor_node_config import SupervisorModeNodeConfig
from cadence_sdk import Loggable
from cadence_sdk.types.sdk_state import UvState

from cadence.constants import DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE
from cadence.infrastructure.streaming import StreamEvent

if TYPE_CHECKING:
    from cadence.engine.base.adapter_base import OrchestratorAdapter
    from cadence.infrastructure.llm.factory import LLMModelFactory
    from cadence.infrastructure.plugins.plugin_manager import SDKPluginManager


class BaseOrchestrator(Loggable, ABC):
    """Abstract base class for all orchestrator implementations.

    Each orchestrator backend (LangGraph, OpenAI Agents, Google ADK) must
    implement this interface to provide consistent behavior across modes.

    Attributes:
        plugin_manager: Plugin manager instance
        llm_factory: LLM model factory
        resolved_config: Resolved configuration dictionary
        adapter: Backend adapter instance
        streaming_wrapper: Streaming event wrapper
    """

    def __init__(
        self,
        plugin_manager: SDKPluginManager,
        llm_factory: LLMModelFactory,
        resolved_config: Dict[str, Any],
        adapter: OrchestratorAdapter,
        streaming_wrapper: Optional[Any] = None,
    ):
        self.plugin_manager = plugin_manager
        self.llm_factory = llm_factory
        self.resolved_config = resolved_config
        self.adapter = adapter
        self.streaming_wrapper = streaming_wrapper
        self.org_id: str = resolved_config.get("org_id", "")
        self._plugin_bundles = plugin_manager.bundles
        self._is_ready = False

    @abstractmethod
    async def astream(self, state: UvState) -> AsyncIterator[StreamEvent]:
        """Execute streaming orchestration."""
        pass

    @property
    @abstractmethod
    def mode(self) -> str:
        """Get orchestration mode (supervisor, coordinator, handoff)."""
        pass

    @property
    @abstractmethod
    def framework_type(self) -> str:
        """Get framework type (langgraph, openai_agents, google_adk)."""
        pass

    @property
    def plugin_pids(self) -> List[str]:
        return list(self._plugin_bundles.keys())

    @property
    def is_ready(self) -> bool:
        return self._is_ready

    @abstractmethod
    async def _build_resources(self) -> None:
        """Build framework-specific resources (models, graph, agents, pipeline)."""
        pass

    async def initialize(self) -> None:
        """Template: wraps _build_resources() with logging and error handling."""
        try:
            await self._build_resources()
            self._is_ready = True
            self.logger.info("%s/%s initialised", self.framework_type, self.mode)
        except Exception as e:
            self.logger.error(
                "Failed to init %s/%s: %s",
                self.framework_type,
                self.mode,
                e,
                exc_info=True,
            )
            raise

    async def _release_resources(self) -> None:
        """Hook: null out framework-specific resources. Override in subclasses."""

    async def cleanup(self) -> None:
        """Template: cleanup plugins, release resources, reset ready state."""
        self.logger.info("Cleaning up %s/%s", self.framework_type, self.mode)
        await self.plugin_manager.cleanup_all()
        await self._release_resources()
        self._is_ready = False

    def _on_config_update(self, config: Dict[str, Any]) -> None:
        """Hook: update framework-specific config (mode_config, settings)."""

    async def rebuild(self, config: Dict[str, Any]) -> None:
        """Template: cleanup → update config → reinitialize."""
        self.logger.info("Rebuilding %s/%s", self.framework_type, self.mode)
        await self.cleanup()
        self.resolved_config = config
        self._on_config_update(config)
        await self.initialize()
        self.logger.info("%s/%s rebuilt", self.framework_type, self.mode)

    def _extra_health_fields(self) -> Dict[str, Any]:
        """Hook: return additional health check fields."""
        return {}

    async def health_check(self) -> Dict[str, Any]:
        """Template: common fields + subclass-specific fields."""
        return {
            "framework_type": self.framework_type,
            "mode": self.mode,
            "is_ready": self._is_ready,
            "plugin_count": len(self._plugin_bundles),
            "plugins": list(self._plugin_bundles.keys()),
            **self._extra_health_fields(),
        }

    def _llm_factory_extra_kwargs(self) -> Dict[str, Any]:
        """Hook: extra kwargs for LLM factory. ADK overrides with framework kwarg."""
        return {}

    async def _create_model_for_node(
        self,
        node_config: SupervisorModeNodeConfig,
        temperature: Optional[float] = None,
    ) -> Any:
        """Create an LLM instance for a specific node via the factory."""
        resolved_temperature = (
            node_config.temperature
            if node_config.temperature is not None
            else (
                temperature
                if temperature is not None
                else self.resolved_config.get("temperature", DEFAULT_TEMPERATURE)
            )
        )
        max_tokens = (
            node_config.max_tokens
            if node_config.max_tokens is not None
            else self.resolved_config.get("max_tokens", DEFAULT_MAX_TOKENS)
        )
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
            "default_model_name", ""
        )

        return await self.llm_factory.create_model_by_id(
            org_id,
            config_id,
            model_name,
            resolved_temperature,
            max_tokens,
            **self._llm_factory_extra_kwargs(),
        )
