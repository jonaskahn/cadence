"""Graph building logic for conversation orchestration."""

from cadence_sdk.types import AgentState
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from .constants import GraphNodeNames, RoutingDecision


class ConversationGraphBuilder:
    """Builds LangGraph workflow for multi-agent orchestration."""

    def __init__(self, plugin_manager, router):
        """Initialize with plugin manager and router."""
        self.plugin_manager = plugin_manager
        self.router = router

    def build_conversation_graph(
        self, coordinator_node, suspend_node, synthesizer_node, checkpointer=None
    ) -> StateGraph:
        """Construct LangGraph workflow for multi-agent orchestration."""
        graph = StateGraph(AgentState)

        self._add_core_orchestration_nodes(graph, coordinator_node, suspend_node, synthesizer_node)
        self._add_dynamic_plugin_nodes(graph)

        graph.set_entry_point(GraphNodeNames.COORDINATOR)
        self._add_conditional_routing_edges(graph)

        compilation_options = {"checkpointer": checkpointer} if checkpointer else {}
        compiled_graph = graph.compile(**compilation_options)

        return compiled_graph

    def _add_core_orchestration_nodes(
        self, graph: StateGraph, coordinator_node, suspend_node, synthesizer_node
    ) -> None:
        """Add core orchestration nodes to conversation graph."""
        graph.add_node(GraphNodeNames.COORDINATOR, coordinator_node)
        graph.add_node(GraphNodeNames.CONTROL_TOOLS, ToolNode(tools=self.plugin_manager.get_coordinator_tools()))
        graph.add_node(GraphNodeNames.SUSPEND, suspend_node)
        graph.add_node(GraphNodeNames.SYNTHESIZER, synthesizer_node)

    def _add_dynamic_plugin_nodes(self, graph: StateGraph) -> None:
        """Dynamically add plugin nodes and connections to graph."""
        for plugin_bundle in self.plugin_manager.plugin_bundles.values():
            plugin_name = plugin_bundle.metadata.name

            graph.add_node(f"{plugin_name}_agent", plugin_bundle.agent_node)
            graph.add_node(f"{plugin_name}_tools", plugin_bundle.tool_node)

    def _add_conditional_routing_edges(self, graph: StateGraph) -> None:
        """Add conditional routing edges between graph nodes."""
        self._add_coordinator_routing_edges(graph)
        self._add_control_tools_routing_edges(graph)
        self._add_plugin_routing_edges(graph)

    def _add_coordinator_routing_edges(self, graph: StateGraph) -> None:
        """Add conditional edges from coordinator to other nodes."""
        graph.add_conditional_edges(
            GraphNodeNames.COORDINATOR,
            self.router.determine_routing_decision,
            {
                RoutingDecision.CONTINUE: GraphNodeNames.CONTROL_TOOLS,
                RoutingDecision.DONE: GraphNodeNames.SYNTHESIZER,
                RoutingDecision.SUSPEND: GraphNodeNames.SUSPEND,
                RoutingDecision.TERMINATE: END,
            },
        )
        graph.add_edge(GraphNodeNames.SUSPEND, END)
        graph.add_edge(GraphNodeNames.SYNTHESIZER, END)

    def _add_control_tools_routing_edges(self, graph: StateGraph) -> None:
        """Add conditional edges from control tools to plugin agents and synthesizer."""
        route_mapping = {}

        for plugin_bundle in self.plugin_manager.plugin_bundles.values():
            route_mapping[plugin_bundle.metadata.name] = f"{plugin_bundle.metadata.name}_agent"

        route_mapping[RoutingDecision.DONE] = GraphNodeNames.SYNTHESIZER

        graph.add_conditional_edges(
            GraphNodeNames.CONTROL_TOOLS,
            lambda state: self.router.determine_plugin_route(state, self.plugin_manager.plugin_bundles),
            route_mapping,
        )

    def _add_plugin_routing_edges(self, graph: StateGraph) -> None:
        """Add edges from plugin agents back to coordinator using bundle edge definitions."""
        for plugin_bundle in self.plugin_manager.plugin_bundles.values():
            edges = plugin_bundle.get_graph_edges()

            for node_name, edge_config in edges["conditional_edges"].items():
                graph.add_conditional_edges(node_name, edge_config["condition"], edge_config["mapping"])

            for from_node, to_node in edges["direct_edges"]:
                graph.add_edge(from_node, to_node)
