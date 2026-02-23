"""Base adapter interface for orchestrator backends.

This module defines the abstract adapter interface that all orchestrator backends
must implement. Adapters handle bidirectional conversion between SDK types
(UvMessage, UvTool) and orchestrator-native types (LangChain, OpenAI, Google).
"""

from abc import ABC, abstractmethod
from typing import Any, List

from cadence_sdk.types.sdk_messages import UvMessage
from cadence_sdk.types.sdk_tools import UvTool


class OrchestratorAdapter(ABC):
    """Abstract adapter for converting between SDK and orchestrator types.

    Each orchestrator backend (LangGraph, OpenAI Agents, Google ADK) must
    implement this interface to bridge SDK types with native types.

    Attributes:
        framework_type: Name of the orchestrator framework (e.g., "langgraph")
    """

    def __init__(self, framework_type: str):
        """Initialize adapter.

        Args:
            framework_type: Name of the orchestrator framework
        """
        self.framework_type = framework_type

    @abstractmethod
    def sdk_message_to_orchestrator(self, sdk_msg: UvMessage) -> Any:
        """Convert SDK message to orchestrator-native message.

        Args:
            sdk_msg: UvMessage (UvHumanMessage, UvAIMessage, etc.)

        Returns:
            Orchestrator-native message object
        """
        pass

    @abstractmethod
    def orchestrator_message_to_sdk(self, orch_msg: Any) -> UvMessage:
        """Convert orchestrator-native message to SDK message.

        Args:
            orch_msg: Orchestrator-native message object

        Returns:
            UvMessage instance
        """
        pass

    @abstractmethod
    def uvtool_to_orchestrator(self, uvtool: UvTool) -> Any:
        """Convert UvTool to orchestrator-native tool.

        Args:
            uvtool: SDK tool definition

        Returns:
            Orchestrator-native tool object
        """
        pass

    @abstractmethod
    def bind_tools_to_model(self, model: Any, tools: List[UvTool], **kwargs) -> Any:
        """Bind tools to model.

        For LangGraph: Returns model.bind_tools(tools)
        For OpenAI Agents/Google ADK: Returns tools list (binding happens at agent construction)

        Args:
            model: LLM model instance
            tools: List of UvTool instances
            **kwargs: Additional binding parameters

        Returns:
            Bound model (LangGraph) or tools list (OpenAI/Google)
        """
        pass

    @abstractmethod
    def create_tool_node(self, tools: List[UvTool]) -> Any:
        """Create tool execution node.

        For LangGraph: Returns ToolNode instance
        For OpenAI Agents/Google ADK: Returns None (tools executed by framework)

        Args:
            tools: List of UvTool instances

        Returns:
            ToolNode instance or None
        """
        pass
