"""Decision engine for conversation flow routing and state transitions.

Encapsulates all routing logic, hop counting, and flow control decisions.
Provides deterministic routing based on conversation state and configuration.
"""

from typing import Any, Dict, List

from cadence_sdk.base.loggable import Loggable
from cadence_sdk.types import AgentState

from ...config.settings import Settings
from ...infrastructure.plugins.sdk_manager import SDKPluginManager
from .message_processor import ConversationMessageProcessor


class RoutingDecision:
    """Possible routing decisions in the conversation flow."""

    CONTINUE = "continue"
    SUSPEND = "suspend"
    DONE = "done"
    TERMINATE = "terminate"


class RoutingIntelligence(Loggable):
    """Decision engine for conversation flow routing and state transitions.
    
    Encapsulates all routing logic, hop counting, and flow control decisions.
    Provides deterministic routing based on conversation state and configuration.
    
    Responsibilities:
    - Route determination based on conversation state
    - Hop limit validation and enforcement
    - Tool call analysis and routing decisions
    - Plugin route resolution
    """

    def __init__(
        self,
        settings: Settings,
        plugin_manager: SDKPluginManager,
        message_processor: ConversationMessageProcessor
    ) -> None:
        super().__init__()
        self.settings = settings
        self.plugin_manager = plugin_manager
        self.message_processor = message_processor

    def determine_next_route(self, state: AgentState) -> str:
        """Determine next step in conversation flow based on current state.
        
        Args:
            state: Current conversation state
            
        Returns:
            str: Routing decision (CONTINUE, SUSPEND, DONE, TERMINATE)
        """
        if self.validate_hop_limits(state):
            self.logger.debug("Routing to SUSPEND due to hop limit reached")
            return RoutingDecision.SUSPEND
        elif self._is_consecutive_agent_route_limit_reached(state):
            self.logger.debug("Routing to SUSPEND due to consecutive coordinator->agent routing limit reached")
            return RoutingDecision.SUSPEND
        elif self.analyze_tool_requirements(state):
            self.logger.debug("Routing to CONTINUE due to tool calls present")
            return RoutingDecision.CONTINUE
        elif self.settings.allowed_coordinator_terminate:
            self.logger.debug("Routing to TERMINATE - coordinator allowed to terminate directly")
            return RoutingDecision.TERMINATE
        else:
            self.logger.debug("Routing to DONE - no tool calls, routing through finalizer")
            return RoutingDecision.DONE

    def validate_hop_limits(self, state: AgentState) -> bool:
        """Check if conversation has reached maximum allowed agent hops.
        
        Args:
            state: Current conversation state
            
        Returns:
            bool: True if hop limit is reached
        """
        agent_hops = state.get("agent_hops", 0)
        max_agent_hops = self.settings.max_agent_hops
        limit_reached = agent_hops >= max_agent_hops
        
        self.logger.debug(f"Hop limit check: current={agent_hops}, max={max_agent_hops}, reached={limit_reached}")
        return limit_reached

    def analyze_tool_requirements(self, state: AgentState) -> bool:
        """Check if last message contains tool calls that need processing.
        
        Args:
            state: Current conversation state
            
        Returns:
            bool: True if tool calls need processing
        """
        messages = state.get("messages", [])
        return self.message_processor.has_tool_calls(messages)

    def resolve_plugin_destination(self, state: AgentState) -> str:
        """Route to appropriate plugin agent based on tool results.
        
        Args:
            state: Current conversation state
            
        Returns:
            str: Plugin name or routing decision
        """
        messages = state.get("messages", [])
        if not messages:
            return RoutingDecision.DONE

        last_message = messages[-1]

        if not self.message_processor.is_valid_tool_message(last_message):
            self.logger.warning("No valid tool message found in routing")
            return RoutingDecision.DONE

        tool_result = self.message_processor.extract_tool_result_from_message(last_message)
        available_plugins = [bundle.metadata.name for bundle in self.plugin_manager.plugin_bundles.values()]
        
        self.logger.debug(f"Tool routing: tool_result='{tool_result}', available_plugins={available_plugins}")

        if tool_result in available_plugins:
            return tool_result
        elif tool_result == "finalize":
            return RoutingDecision.DONE
        else:
            self.logger.warning(f"Unknown tool result: '{tool_result}', routing to DONE")
            return RoutingDecision.DONE

    def calculate_agent_hops(self, current_agent_hops: int, tool_calls: List[Any]) -> int:
        """Calculate new agent hop count based on tool calls.
        
        Args:
            current_agent_hops: Current hop count
            tool_calls: List of tool calls to analyze
            
        Returns:
            int: Updated hop count
        """

        def _get_name(tc):
            try:
                if isinstance(tc, dict):
                    return tc.get("name")
                return getattr(tc, "name", None)
            except Exception:
                return None

        potential_tool_calls = [_get_name(tc) for tc in tool_calls]
        new_hops = current_agent_hops
        
        for potential_tool_call in potential_tool_calls:
            if potential_tool_call and potential_tool_call != "goto_finalize":
                new_hops += 1
                
        self.logger.debug(f"Hop calculation: {current_agent_hops} -> {new_hops}")
        return new_hops

    def is_routing_to_agent(self, tool_calls: List[Any]) -> bool:
        """Check if tool calls indicate routing to an agent.
        
        Args:
            tool_calls: List of tool calls to analyze
            
        Returns:
            bool: True if routing to an agent
        """
        analysis = self.message_processor.analyze_tool_calls_for_agent_routing(tool_calls)
        return analysis["has_agent_routes"]

    def update_same_agent_route_counter(
        self,
        plugin_context: Dict[str, Any],
        tool_calls: List[Any]
    ) -> Dict[str, Any]:
        """Update counter for consecutive routes to the same agent.
        
        Args:
            plugin_context: Current plugin context
            tool_calls: List of tool calls
            
        Returns:
            dict: Updated plugin context
        """
        plugin_context = dict(plugin_context or {})
        
        analysis = self.message_processor.analyze_tool_calls_for_agent_routing(tool_calls)
        
        if analysis["has_finalize"]:
            return self._reset_route_counters(plugin_context)
            
        if analysis["has_agent_routes"] and analysis["agent_names"]:
            selected_agent = analysis["agent_names"][0]  # Take first agent
            last_agent = plugin_context.get("last_routed_agent")
            
            if last_agent and last_agent == selected_agent:
                plugin_context["same_agent_consecutive_routes"] = (
                    int(plugin_context.get("same_agent_consecutive_routes", 0) or 0) + 1
                )
            else:
                plugin_context["same_agent_consecutive_routes"] = 1
                plugin_context["last_routed_agent"] = selected_agent
                
        return plugin_context

    def reset_route_counters(self, plugin_context: Dict[str, Any]) -> Dict[str, Any]:
        """Reset routing counters in plugin context.
        
        Args:
            plugin_context: Current plugin context
            
        Returns:
            dict: Plugin context with reset counters
        """
        return self._reset_route_counters(plugin_context)

    def _is_consecutive_agent_route_limit_reached(self, state: AgentState) -> bool:
        """Check if coordinator has routed to the SAME agent too many times consecutively.

        Tracks only coordinator tool routes to agents (excludes finalize) and
        requires that the selected agent is the same across consecutive decisions.
        
        Args:
            state: Current conversation state
            
        Returns:
            bool: True if consecutive limit is reached
        """
        plugin_context = state.get("plugin_context", {}) or {}
        same_agent_count = int(plugin_context.get("same_agent_consecutive_routes", 0) or 0)
        limit = int(self.settings.coordinator_consecutive_agent_route_limit or 0)
        
        try:
            reached = limit > 0 and same_agent_count >= limit
        except Exception:
            reached = False
            
        self.logger.debug(
            f"Same-agent consecutive route check: count={same_agent_count}, limit={limit}, reached={reached}"
        )
        return reached

    @staticmethod
    def _reset_route_counters(plugin_context: Dict[str, Any]) -> Dict[str, Any]:
        """Reset route counters in plugin context.
        
        Args:
            plugin_context: Plugin context to reset
            
        Returns:
            dict: Plugin context with reset counters
        """
        plugin_context = dict(plugin_context or {})
        plugin_context["same_agent_consecutive_routes"] = 0
        plugin_context["last_routed_agent"] = None
        return plugin_context

    def get_routing_info(self, state: AgentState) -> dict:
        """Get detailed routing information for debugging.
        
        Args:
            state: Current conversation state
            
        Returns:
            dict: Routing information and analysis
        """
        messages = state.get("messages", [])
        plugin_context = state.get("plugin_context", {}) or {}
        
        return {
            "agent_hops": state.get("agent_hops", 0),
            "max_agent_hops": self.settings.max_agent_hops,
            "hop_limit_reached": self.validate_hop_limits(state),
            "consecutive_routes": plugin_context.get("same_agent_consecutive_routes", 0),
            "consecutive_limit": self.settings.coordinator_consecutive_agent_route_limit,
            "consecutive_limit_reached": self._is_consecutive_agent_route_limit_reached(state),
            "has_tool_calls": self.message_processor.has_tool_calls(messages),
            "last_routed_agent": plugin_context.get("last_routed_agent"),
            "available_plugins": [bundle.metadata.name for bundle in self.plugin_manager.plugin_bundles.values()],
            "coordinator_can_terminate": self.settings.allowed_coordinator_terminate
        }
