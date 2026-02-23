"""Base orchestrator interface for all backends.

This module defines the abstract orchestrator interface that all orchestrator
implementations must follow, regardless of backend (LangGraph, OpenAI, Google).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, List, Optional

from cadence_sdk.types.sdk_state import UvState

from cadence.infrastructure.streaming import StreamEvent

if TYPE_CHECKING:
    from cadence.engine.base.adapter_base import OrchestratorAdapter
    from cadence.infrastructure.llm.factory import LLMModelFactory
    from cadence.infrastructure.plugins.plugin_manager import SDKPluginManager


class BaseOrchestrator(ABC):
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
        """Initialize orchestrator.

        Args:
            plugin_manager: Plugin manager instance
            llm_factory: LLM model factory
            resolved_config: Resolved configuration dictionary
            adapter: Backend adapter instance
            streaming_wrapper: Optional streaming event wrapper
        """
        self.plugin_manager = plugin_manager
        self.llm_factory = llm_factory
        self.resolved_config = resolved_config
        self.adapter = adapter
        self.streaming_wrapper = streaming_wrapper
        self.org_id: str = resolved_config.get("org_id", "")

    @abstractmethod
    async def ask(self, state: UvState) -> UvState:
        """Execute single-shot orchestration.

        Args:
            state: Input state with messages and context

        Returns:
            Updated state with response
        """
        pass

    @abstractmethod
    async def astream(self, state: UvState) -> AsyncIterator[StreamEvent]:
        """Execute streaming orchestration.

        Args:
            state: Input state with messages and context

        Yields:
            StreamEvent instances
        """
        pass

    @abstractmethod
    async def rebuild(self, config: Dict[str, Any]) -> None:
        """Hot-reload orchestrator with new configuration.

        Args:
            config: New configuration dictionary
        """
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """Release resources and cleanup."""
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check orchestrator health.

        Returns:
            Health status dictionary
        """
        pass

    @property
    @abstractmethod
    def mode(self) -> str:
        """Get orchestration mode (supervisor, coordinator, handoff).

        Returns:
            Mode identifier
        """
        pass

    @property
    @abstractmethod
    def framework_type(self) -> str:
        """Get framework type (langgraph, openai_agents, google_adk).

        Returns:
            Framework type identifier
        """
        pass

    @property
    @abstractmethod
    def plugin_pids(self) -> List[str]:
        """Get list of active plugin pids.

        Returns:
            List of reverse-domain plugin identifiers
        """
        pass

    @property
    @abstractmethod
    def is_ready(self) -> bool:
        """Check if orchestrator is ready to accept requests.

        Returns:
            True if ready, False otherwise
        """
        pass
