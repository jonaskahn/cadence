"""Routing logic for conversation flow decisions."""

from typing import Any, Dict, List

from cadence_sdk.types import AgentState
from cadence_sdk.types.state import PluginContext, PluginContextFields, RoutingHelpers, StateHelpers

from .constants import RoutingDecision


class ConversationRouter:
    """Handles routing decisions in conversation flow."""

    def __init__(self, settings):
        """Initialize router with settings."""
        self.settings = settings

    def determine_routing_decision(self, state: AgentState) -> str:
        """Determine next step in conversation flow based on current state."""
        if self._is_hop_limit_reached(state):
            return RoutingDecision.SUSPEND
        elif self._is_consecutive_agent_route_limit_reached(state):
            return RoutingDecision.SUSPEND
        elif self.has_tool_calls(state):
            return RoutingDecision.CONTINUE
        elif self.settings.allowed_coordinator_terminate:
            return RoutingDecision.TERMINATE
        else:
            return RoutingDecision.DONE

    def determine_plugin_route(self, state: AgentState, plugin_bundles) -> str:
        """Route to appropriate plugin agent based on tool results."""
        messages = StateHelpers.safe_get_messages(state)
        if not messages:
            return RoutingDecision.DONE

        last_message = messages[-1]

        if not self._is_valid_tool_message(last_message):
            return RoutingDecision.DONE

        tool_result = last_message.content

        if tool_result in [bundle.metadata.name for bundle in plugin_bundles.values()]:
            return tool_result
        elif tool_result == "synthesize":
            return RoutingDecision.DONE
        else:
            return RoutingDecision.DONE

    def _is_hop_limit_reached(self, state: AgentState) -> bool:
        """Check if conversation has reached maximum allowed agent hops."""
        agent_hops = StateHelpers.safe_get_agent_hops(state)
        max_agent_hops = self.settings.max_agent_hops
        return agent_hops >= max_agent_hops

    def _is_consecutive_agent_route_limit_reached(self, state: AgentState) -> bool:
        """Check if coordinator has routed to the SAME agent too many times consecutively."""
        limit = int(self.settings.coordinator_consecutive_agent_route_limit or 0)
        try:
            plugin_context = StateHelpers.get_plugin_context(state)
            consecutive_agent_counter = plugin_context.get(PluginContextFields.CONSECUTIVE_AGENT_REPEATS, 0)
            reached = 0 < limit <= consecutive_agent_counter
        except Exception:
            reached = False
        return reached

    def has_tool_calls(self, state: AgentState) -> bool:
        """Check if last message contains tool calls that need processing."""
        messages = StateHelpers.safe_get_messages(state)
        if not messages:
            return False

        last_message = messages[-1]
        tool_calls = getattr(last_message, "tool_calls", None)
        return bool(tool_calls)

    @staticmethod
    def _is_valid_tool_message(message: Any) -> bool:
        """Validate message has required structure for tool routing."""
        return message and hasattr(message, "content")


class RouteCounter:
    """Handles route counting and tracking logic."""

    @staticmethod
    def calculate_agent_hops(current_agent_hops, tool_calls):
        """Calculate agent hops based on tool calls."""

        def _get_name(tc):
            try:
                if isinstance(tc, dict):
                    return tc.get("name")
                return getattr(tc, "name", None)
            except Exception:
                return None

        potential_tool_calls = [_get_name(tc) for tc in tool_calls]
        for potential_tool_call in potential_tool_calls:
            if potential_tool_call and potential_tool_call != "goto_synthesize":
                current_agent_hops += 1
        return current_agent_hops

    @staticmethod
    def reset_route_counters(plugin_context: PluginContext) -> PluginContext:
        """Reset route counters using RoutingHelpers."""
        return RoutingHelpers.update_consecutive_routes(plugin_context, "goto_synthesize")

    @staticmethod
    def update_same_agent_route_counter(
        plugin_context: PluginContext, tool_calls: List[Dict[str, Any]]
    ) -> PluginContext:
        """Update route counter using RoutingHelpers."""
        routed_tools = [tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "") for tc in tool_calls]
        selected_tool = routed_tools[0] if routed_tools else ""

        updated_context = RoutingHelpers.update_consecutive_routes(plugin_context, selected_tool)
        if selected_tool:
            updated_context = RoutingHelpers.add_to_routing_history(updated_context, selected_tool)

        return updated_context
