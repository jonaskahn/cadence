"""LangChain/LangGraph adapter for SDK types (v1.0+).

This module provides bidirectional conversion between Cadence SDK types
and LangChain/LangGraph native types using LangChain v1.0+ patterns.
"""

from typing import Any, List

from cadence_sdk.types.sdk_messages import (
    ToolCall,
    UvAIMessage,
    UvHumanMessage,
    UvMessage,
    UvSystemMessage,
    UvToolMessage,
)
from cadence_sdk.types.sdk_tools import UvTool
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool, StructuredTool
from langchain_core.tools import tool as tool_decorator
from langgraph.prebuilt import ToolNode

from cadence.engine.base import OrchestratorAdapter


class LangChainAdapter(OrchestratorAdapter):
    """Adapter for LangChain/LangGraph orchestration backend.

    Converts between SDK types (UvMessage, UvTool) and LangChain types
    (BaseMessage, BaseTool).
    """

    def __init__(self):
        """Initialize LangChain adapter."""
        super().__init__(framework_type="langgraph")

    def sdk_message_to_orchestrator(self, sdk_msg: UvMessage) -> BaseMessage:
        """Convert SDK message to LangChain message.

        Args:
            sdk_msg: UvMessage instance

        Returns:
            LangChain BaseMessage instance

        Raises:
            ValueError: If message type is unknown
        """
        if isinstance(sdk_msg, UvHumanMessage):
            return HumanMessage(content=sdk_msg.content)

        if isinstance(sdk_msg, UvAIMessage):
            tool_calls = []
            if sdk_msg.tool_calls:
                tool_calls = [
                    {
                        "id": tc.id,
                        "name": tc.name,
                        "args": tc.args,
                    }
                    for tc in sdk_msg.tool_calls
                ]
            return AIMessage(content=sdk_msg.content, tool_calls=tool_calls)

        if isinstance(sdk_msg, UvSystemMessage):
            return SystemMessage(content=sdk_msg.content)

        if isinstance(sdk_msg, UvToolMessage):
            return ToolMessage(
                content=sdk_msg.content,
                tool_call_id=sdk_msg.tool_call_id,
                name=sdk_msg.tool_name,
            )

        raise ValueError(f"Unknown message type: {type(sdk_msg)}")

    def orchestrator_message_to_sdk(self, orch_msg: BaseMessage) -> UvMessage:
        """Convert LangChain message to SDK message.

        Args:
            orch_msg: LangChain BaseMessage instance

        Returns:
            UvMessage instance

        Raises:
            ValueError: If message type is unknown
        """
        if isinstance(orch_msg, HumanMessage):
            return UvHumanMessage(content=orch_msg.content)

        if isinstance(orch_msg, AIMessage):
            tool_calls = []
            if hasattr(orch_msg, "tool_calls") and orch_msg.tool_calls:
                tool_calls = [
                    ToolCall(
                        id=tc.get("id", ""),
                        name=tc.get("name", ""),
                        args=tc.get("args", {}),
                    )
                    for tc in orch_msg.tool_calls
                ]
            return UvAIMessage(content=orch_msg.content, tool_calls=tool_calls)

        if isinstance(orch_msg, SystemMessage):
            return UvSystemMessage(content=orch_msg.content)

        if isinstance(orch_msg, ToolMessage):
            return UvToolMessage(
                content=orch_msg.content,
                tool_call_id=orch_msg.tool_call_id,
                tool_name=orch_msg.name if hasattr(orch_msg, "name") else "",
            )

        raise ValueError(f"Unknown message type: {type(orch_msg)}")

    def uvtool_to_orchestrator(self, uvtool: UvTool) -> BaseTool:
        """Convert UvTool to LangChain tool (v1.0+ pattern).

        Uses @tool decorator pattern for v1.0+ compatibility.
        Creates StructuredTool with args_schema if provided.

        Args:
            uvtool: SDK tool definition

        Returns:
            LangChain BaseTool instance
        """
        if uvtool.args_schema:
            if uvtool.is_async:
                return StructuredTool.from_function(
                    name=uvtool.name,
                    description=uvtool.description,
                    coroutine=uvtool.func,
                    args_schema=uvtool.args_schema,
                )
            else:
                return StructuredTool.from_function(
                    name=uvtool.name,
                    description=uvtool.description,
                    func=uvtool.func,
                    args_schema=uvtool.args_schema,
                )

        decorated_tool = tool_decorator(
            name_or_callable=uvtool.name,
            description=uvtool.description,
        )(uvtool.func)

        return decorated_tool

    def bind_tools_to_model(self, model: Any, tools: List[UvTool], **kwargs) -> Any:
        """Bind tools to LangChain model.

        Args:
            model: LangChain BaseChatModel instance
            tools: List of UvTool instances
            **kwargs: Additional binding parameters

        Returns:
            Model with tools bound
        """
        lc_tools = [self.uvtool_to_orchestrator(tool) for tool in tools]
        return model.bind_tools(lc_tools, **kwargs)

    def create_tool_node(self, tools: List[UvTool]) -> ToolNode:
        """Create LangGraph ToolNode.

        Args:
            tools: List of UvTool instances

        Returns:
            LangGraph ToolNode instance
        """
        lc_tools = [self.uvtool_to_orchestrator(tool) for tool in tools]
        return ToolNode(lc_tools)
