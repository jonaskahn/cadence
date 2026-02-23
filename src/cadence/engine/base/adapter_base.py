"""Base adapter interface for orchestrator backends.

This module defines the abstract adapter interface that all orchestrator backends
must implement. Adapters handle bidirectional conversion between SDK types
(UvMessage, UvTool) and orchestrator-native types (LangChain, OpenAI, Google).
"""

from abc import ABC, abstractmethod
from typing import Any

from cadence_sdk import Loggable
from cadence_sdk.types.sdk_messages import UvMessage
from cadence_sdk.types.sdk_tools import UvTool


class OrchestratorAdapter(Loggable, ABC):
    """Abstract adapter for converting between SDK and orchestrator types.

    Each orchestrator backend (LangGraph, OpenAI Agents, Google ADK) must
    implement this interface to bridge SDK types with native types.

    Attributes:
        framework_type: Name of the orchestrator framework (e.g., "langgraph")
    """

    def __init__(self, framework_type: str):
        self.framework_type = framework_type

    @abstractmethod
    def sdk_message_to_orchestrator(self, sdk_msg: UvMessage) -> Any:
        """Convert SDK message to orchestrator-native message."""
        pass

    @abstractmethod
    def orchestrator_message_to_sdk(self, orch_msg: Any) -> UvMessage:
        """Convert orchestrator-native message to SDK message."""
        pass

    @abstractmethod
    def uvtool_to_orchestrator(self, uvtool: UvTool) -> Any:
        """Convert UvTool to orchestrator-native tool."""
        pass
