"""Message processing and validation utilities for conversation flows.

Handles message filtering, validation, and transformation operations
required throughout the conversation pipeline.
"""

from typing import Any, List

from cadence_sdk.base.loggable import Loggable
from langchain_core.messages import AIMessage


class ConversationMessageProcessor(Loggable):
    """Message processing and validation utilities for conversation flows.
    
    Handles message filtering, validation, and transformation operations
    required throughout the conversation pipeline.
    
    Responsibilities:
    - Message sequence validation
    - Tool call extraction and analysis
    - Message filtering for safe processing
    - Response formatting and structuring
    """

    def __init__(self) -> None:
        super().__init__()

    def has_tool_calls(self, messages: List[Any]) -> bool:
        """Check if message list contains tool calls that need processing.
        
        Args:
            messages: List of messages to check
            
        Returns:
            bool: True if tool calls are found, False otherwise
        """
        if not messages:
            self.logger.debug("No messages provided")
            return False

        last_message = messages[-1]
        tool_calls = getattr(last_message, "tool_calls", None)
        has_tool_calls = bool(tool_calls)

        self.logger.debug(f"Last message type: {type(last_message).__name__}, has tool_calls: {has_tool_calls}")
        if has_tool_calls:
            self.logger.debug(f"Tool calls found: {len(tool_calls)} calls")
            for i, tc in enumerate(tool_calls):
                self.logger.debug(f"  Tool call {i}: {getattr(tc, 'name', 'unknown')}")

        return has_tool_calls

    def extract_tool_calls_from_state(self, state: dict) -> List[Any]:
        """Extract tool calls from conversation state.
        
        Args:
            state: Conversation state containing messages
            
        Returns:
            List of tool calls from the last message, or empty list
        """
        messages = state.get("messages", [])
        if not messages:
            return []
            
        last_message = messages[-1]
        return getattr(last_message, "tool_calls", [])

    def is_valid_tool_message(self, message: Any) -> bool:
        """Validate message has required structure for tool routing.
        
        Args:
            message: Message to validate
            
        Returns:
            bool: True if message is valid for tool routing
        """
        return message and hasattr(message, "content")

    def filter_safe_messages(self, messages: List[Any]) -> List[Any]:
        """Remove messages with incomplete tool call sequences to prevent validation errors.
        
        This method removes the last AIMessage if it exists to prevent issues
        with incomplete tool call sequences during conversation processing.
        
        Args:
            messages: List of messages to filter
            
        Returns:
            List of safe messages for processing
        """
        if not messages:
            return []
            
        # Create a copy to avoid modifying the original list
        safe_messages = messages.copy()
        
        last_message = safe_messages[-1]
        if isinstance(last_message, AIMessage):
            safe_messages.pop()
            self.logger.debug("Removed last AIMessage for safe processing")
            
        return safe_messages

    def extract_tool_result_from_message(self, message: Any) -> str:
        """Extract tool result content from a message.
        
        Args:
            message: Message containing tool result
            
        Returns:
            str: Tool result content, or empty string if not found
        """
        if not self.is_valid_tool_message(message):
            self.logger.warning("Invalid tool message provided")
            return ""
            
        return getattr(message, "content", "")

    def analyze_tool_calls_for_agent_routing(self, tool_calls: List[Any]) -> dict:
        """Analyze tool calls to determine agent routing information.
        
        Args:
            tool_calls: List of tool calls to analyze
            
        Returns:
            dict: Analysis results including agent names and routing decisions
        """
        analysis = {
            "has_agent_routes": False,
            "agent_names": [],
            "has_finalize": False,
            "tool_count": len(tool_calls)
        }
        
        for tool_call in tool_calls:
            tool_name = self._get_tool_name(tool_call)
            if not tool_name:
                continue
                
            if tool_name == "goto_finalize":
                analysis["has_finalize"] = True
            elif tool_name.startswith("goto_"):
                analysis["has_agent_routes"] = True
                agent_name = tool_name[len("goto_"):]
                analysis["agent_names"].append(agent_name)
        
        self.logger.debug(f"Tool call analysis: {analysis}")
        return analysis

    def _get_tool_name(self, tool_call: Any) -> str:
        """Extract tool name from tool call object.
        
        Args:
            tool_call: Tool call object (dict or object with name attribute)
            
        Returns:
            str: Tool name or empty string if not found
        """
        try:
            if isinstance(tool_call, dict):
                return tool_call.get("name", "")
            return getattr(tool_call, "name", "")
        except Exception as e:
            self.logger.warning(f"Error extracting tool name: {e}")
            return ""

    def validate_message_sequence(self, messages: List[Any]) -> bool:
        """Validate that message sequence is properly formed.
        
        Args:
            messages: List of messages to validate
            
        Returns:
            bool: True if sequence is valid
        """
        if not messages:
            return True
            
        # Basic validation - ensure we have at least one message
        # and that the sequence doesn't end with incomplete tool calls
        try:
            last_message = messages[-1]
            
            # If last message has tool calls, ensure they're complete
            if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                # Tool calls should have required fields
                for tool_call in last_message.tool_calls:
                    if not self._get_tool_name(tool_call):
                        self.logger.warning("Found tool call without name")
                        return False
                        
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating message sequence: {e}")
            return False
