"""Centralized state management for conversation context and metadata.

Handles all state mutations, tracking, and validation throughout the
conversation lifecycle. Ensures state consistency across node transitions.
"""

from typing import Any, Dict

from cadence_sdk.base.loggable import Loggable
from cadence_sdk.types import AgentState
from langchain_core.messages import AIMessage


class ConversationStateManager(Loggable):
    """Centralized state management for conversation context and metadata.
    
    Handles all state mutations, tracking, and validation throughout the
    conversation lifecycle. Ensures state consistency across node transitions.
    
    Responsibilities:
    - Agent hop tracking and validation
    - Plugin context management
    - State update creation and validation
    - Conversation metadata handling
    """

    def __init__(self) -> None:
        super().__init__()

    def create_state_update(
        self,
        message: AIMessage,
        agent_hops: int,
        state: Dict[str, Any]=None
    ) -> Dict[str, Any]:
        """Create standardized state update structure for graph node responses.
        
        Args:
            message: AI message to include in the update
            agent_hops: Current agent hop count
            state: Optional existing state to preserve certain fields
            
        Returns:
            dict: Standardized state update structure
        """
        update = {
            "messages": [message],
            "agent_hops": agent_hops,
        }

        if state:
            # Preserve important state fields
            for key in ["current_agent", "plugin_context", "thread_id", "metadata"]:
                if key in state:
                    update[key] = state[key]

        self.logger.debug(f"Created state update with {len(update)} fields")
        return update

    def update_agent_hops(self, state: AgentState, new_hops: int) -> AgentState:
        """Update agent hop count in conversation state.
        
        Args:
            state: Current conversation state
            new_hops: New hop count to set
            
        Returns:
            Updated conversation state
        """
        updated_state = dict(state)
        updated_state["agent_hops"] = new_hops
        
        self.logger.debug(f"Updated agent hops: {state.get('agent_hops', 0)} -> {new_hops}")
        return updated_state

    def update_plugin_context(self, state: AgentState, plugin_context: Dict[str, Any]) -> AgentState:
        """Update plugin context in conversation state.
        
        Args:
            state: Current conversation state
            plugin_context: New plugin context to set
            
        Returns:
            Updated conversation state
        """
        updated_state = dict(state)
        updated_state["plugin_context"] = plugin_context
        
        self.logger.debug(f"Updated plugin context with {len(plugin_context)} fields")
        return updated_state

    def get_agent_hops(self, state: AgentState) -> int:
        """Get current agent hop count from state.
        
        Args:
            state: Conversation state
            
        Returns:
            int: Current agent hop count
        """
        return state.get("agent_hops", 0)

    def get_plugin_context(self, state: AgentState) -> Dict[str, Any]:
        """Get plugin context from conversation state.
        
        Args:
            state: Conversation state
            
        Returns:
            dict: Plugin context dictionary
        """
        return dict(state.get("plugin_context", {}) or {})

    def get_conversation_metadata(self, state: AgentState) -> Dict[str, Any]:
        """Get conversation metadata from state.
        
        Args:
            state: Conversation state
            
        Returns:
            dict: Conversation metadata
        """
        return dict(state.get("metadata", {}) or {})

    def get_requested_tone(self, state: AgentState) -> str:
        """Get requested response tone from conversation metadata.
        
        Args:
            state: Conversation state
            
        Returns:
            str: Requested tone, defaults to "natural"
        """
        metadata = self.get_conversation_metadata(state)
        return metadata.get("tone", "natural") or "natural"

    def set_current_agent(self, state: AgentState, agent_name: str) -> AgentState:
        """Set the current active agent in conversation state.
        
        Args:
            state: Current conversation state
            agent_name: Name of the current agent
            
        Returns:
            Updated conversation state
        """
        updated_state = dict(state)
        updated_state["current_agent"] = agent_name
        
        self.logger.debug(f"Set current agent: {agent_name}")
        return updated_state

    def get_current_agent(self, state: AgentState) -> str:
        """Get the current active agent from conversation state.
        
        Args:
            state: Conversation state
            
        Returns:
            str: Current agent name, or empty string if not set
        """
        return state.get("current_agent", "")

    def validate_state_structure(self, state: AgentState) -> bool:
        """Validate that conversation state has required structure.
        
        Args:
            state: Conversation state to validate
            
        Returns:
            bool: True if state structure is valid
        """
        try:
            # Check for required fields
            if not isinstance(state, dict):
                self.logger.error("State is not a dictionary")
                return False
                
            # Validate messages field
            messages = state.get("messages", [])
            if not isinstance(messages, list):
                self.logger.error("Messages field is not a list")
                return False
                
            # Validate agent_hops field
            agent_hops = state.get("agent_hops", 0)
            if not isinstance(agent_hops, int) or agent_hops < 0:
                self.logger.error(f"Invalid agent_hops value: {agent_hops}")
                return False
                
            # Validate plugin_context if present
            plugin_context = state.get("plugin_context")
            if plugin_context is not None and not isinstance(plugin_context, dict):
                self.logger.error("Plugin context is not a dictionary")
                return False
                
            # Validate metadata if present
            metadata = state.get("metadata")
            if metadata is not None and not isinstance(metadata, dict):
                self.logger.error("Metadata is not a dictionary")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating state structure: {e}")
            return False

    def merge_state_updates(self, base_state: AgentState, updates: Dict[str, Any]) -> AgentState:
        """Merge state updates into base state.
        
        Args:
            base_state: Base conversation state
            updates: Updates to merge
            
        Returns:
            Merged conversation state
        """
        merged_state = dict(base_state)
        
        for key, value in updates.items():
            if key == "messages":
                # Append new messages to existing ones
                existing_messages = merged_state.get("messages", [])
                if isinstance(value, list):
                    merged_state["messages"] = existing_messages + value
                else:
                    merged_state["messages"] = existing_messages + [value]
            elif key == "plugin_context":
                # Merge plugin context dictionaries
                existing_context = merged_state.get("plugin_context", {}) or {}
                if isinstance(value, dict):
                    merged_context = dict(existing_context)
                    merged_context.update(value)
                    merged_state["plugin_context"] = merged_context
                else:
                    merged_state["plugin_context"] = value
            else:
                # Direct assignment for other fields
                merged_state[key] = value
                
        self.logger.debug(f"Merged state updates: {list(updates.keys())}")
        return merged_state

    def get_state_summary(self, state: AgentState) -> Dict[str, Any]:
        """Get a summary of the current conversation state.
        
        Args:
            state: Conversation state
            
        Returns:
            dict: State summary for debugging/monitoring
        """
        messages = state.get("messages", [])
        plugin_context = self.get_plugin_context(state)
        
        return {
            "message_count": len(messages),
            "agent_hops": self.get_agent_hops(state),
            "current_agent": self.get_current_agent(state),
            "requested_tone": self.get_requested_tone(state),
            "plugin_context_keys": list(plugin_context.keys()),
            "thread_id": state.get("thread_id"),
            "has_metadata": bool(state.get("metadata")),
            "state_valid": self.validate_state_structure(state)
        }

    def clean_state_for_processing(self, state: AgentState) -> AgentState:
        """Clean state by removing or fixing problematic fields for processing.
        
        Args:
            state: Conversation state to clean
            
        Returns:
            Cleaned conversation state
        """
        cleaned_state = dict(state)
        
        # Ensure plugin_context is a proper dictionary
        plugin_context = cleaned_state.get("plugin_context")
        if plugin_context is None:
            cleaned_state["plugin_context"] = {}
        elif not isinstance(plugin_context, dict):
            self.logger.warning("Invalid plugin_context type, resetting to empty dict")
            cleaned_state["plugin_context"] = {}
            
        # Ensure agent_hops is a valid integer
        agent_hops = cleaned_state.get("agent_hops", 0)
        if not isinstance(agent_hops, int) or agent_hops < 0:
            self.logger.warning(f"Invalid agent_hops value {agent_hops}, resetting to 0")
            cleaned_state["agent_hops"] = 0
            
        # Ensure messages is a list
        messages = cleaned_state.get("messages", [])
        if not isinstance(messages, list):
            self.logger.warning("Invalid messages type, resetting to empty list")
            cleaned_state["messages"] = []
            
        return cleaned_state
