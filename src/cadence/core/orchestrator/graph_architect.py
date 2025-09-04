"""Specialized builder for constructing LangGraph conversation workflows.

Transforms plugin configurations and routing requirements into executable
graph structures. Handles both static core nodes and dynamic plugin integration.
"""

from typing import Any, Callable, Dict

from cadence_sdk.base.loggable import Loggable
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from ...infrastructure.plugins.sdk_manager import SDKPluginManager
from .routing_intelligence import RoutingDecision


class GraphNodeNames:
    """Names of nodes in the conversation graph."""

    COORDINATOR = "coordinator"
    CONTROL_TOOLS = "control_tools"
    SUSPEND = "suspend"
    FINALIZER = "finalizer"


class ConversationGraphArchitect(Loggable):
    """Specialized builder for constructing LangGraph conversation workflows.
    
    Transforms plugin configurations and routing requirements into executable
    graph structures. Handles both static core nodes and dynamic plugin integration.
    
    Responsibilities:
    - Graph topology construction
    - Node and edge registration
    - Plugin integration into graph structure
    - Graph compilation and validation
    """

    def __init__(
        self,
        plugin_manager: SDKPluginManager,
        checkpointer: Any=None
    ) -> None:
        super().__init__()
        self.plugin_manager = plugin_manager
        self.checkpointer = checkpointer

    def build_conversation_graph(
        self,
        coordinator_node: Callable,
        suspend_node: Callable,
        finalizer_node: Callable,
        coordinator_routing_logic: Callable,
        plugin_route_resolver: Callable
    ) -> StateGraph:
        """Construct LangGraph workflow for multi-agent orchestration.
        
        Args:
            coordinator_node: Function for coordinator node execution
            suspend_node: Function for suspend node execution
            finalizer_node: Function for finalizer node execution
            coordinator_routing_logic: Function for coordinator routing decisions
            plugin_route_resolver: Function for resolving plugin routes
            
        Returns:
            Compiled StateGraph ready for execution
        """
        from cadence_sdk.types import AgentState
        
        graph = StateGraph(AgentState)

        self.register_core_nodes(graph, coordinator_node, suspend_node, finalizer_node)
        self.integrate_plugin_nodes(graph)
        
        graph.set_entry_point(GraphNodeNames.COORDINATOR)
        self.establish_routing_edges(graph, coordinator_routing_logic, plugin_route_resolver)

        compiled_graph = self._compile_graph(graph)
        
        self.logger.debug(f"Graph built with \n{compiled_graph.get_graph().draw_mermaid()}")
        return compiled_graph

    def register_core_nodes(
        self,
        graph: StateGraph,
        coordinator_node: Callable,
        suspend_node: Callable,
        finalizer_node: Callable
    ) -> None:
        """Add core orchestration nodes to conversation graph.
        
        Args:
            graph: StateGraph to add nodes to
            coordinator_node: Coordinator node function
            suspend_node: Suspend node function
            finalizer_node: Finalizer node function
        """
        graph.add_node(GraphNodeNames.COORDINATOR, coordinator_node)
        graph.add_node(GraphNodeNames.CONTROL_TOOLS, ToolNode(tools=self.plugin_manager.get_coordinator_tools()))
        graph.add_node(GraphNodeNames.SUSPEND, suspend_node)
        graph.add_node(GraphNodeNames.FINALIZER, finalizer_node)
        
        self.logger.debug("Registered core orchestration nodes")

    def integrate_plugin_nodes(self, graph: StateGraph) -> None:
        """Dynamically add plugin nodes and connections to graph.
        
        Args:
            graph: StateGraph to add plugin nodes to
        """
        plugin_count = 0
        
        for plugin_bundle in self.plugin_manager.plugin_bundles.values():
            plugin_name = plugin_bundle.metadata.name

            graph.add_node(f"{plugin_name}_agent", plugin_bundle.agent_node)
            graph.add_node(f"{plugin_name}_tools", plugin_bundle.tool_node)
            plugin_count += 1

        self.logger.debug(f"Integrated {plugin_count} plugin nodes")

    def establish_routing_edges(
        self,
        graph: StateGraph,
        coordinator_routing_logic: Callable,
        plugin_route_resolver: Callable
    ) -> None:
        """Add conditional routing edges between graph nodes.
        
        Args:
            graph: StateGraph to add edges to
            coordinator_routing_logic: Function for coordinator routing
            plugin_route_resolver: Function for plugin route resolution
        """
        self._add_coordinator_routing_edges(graph, coordinator_routing_logic)
        self._add_control_tools_routing_edges(graph, plugin_route_resolver)
        self._add_plugin_routing_edges(graph)
        
        self.logger.debug("Established all routing edges")

    def _add_coordinator_routing_edges(self, graph: StateGraph, coordinator_routing_logic: Callable) -> None:
        """Add conditional edges from coordinator to other nodes.
        
        Args:
            graph: StateGraph to add edges to
            coordinator_routing_logic: Function for routing decisions
        """
        graph.add_conditional_edges(
            GraphNodeNames.COORDINATOR,
            coordinator_routing_logic,
            {
                RoutingDecision.CONTINUE: GraphNodeNames.CONTROL_TOOLS,
                RoutingDecision.DONE: GraphNodeNames.FINALIZER,
                RoutingDecision.SUSPEND: GraphNodeNames.SUSPEND,
                RoutingDecision.TERMINATE: END,
            },
        )
        graph.add_edge(GraphNodeNames.SUSPEND, END)
        graph.add_edge(GraphNodeNames.FINALIZER, END)
        
        self.logger.debug("Added coordinator routing edges")

    def _add_control_tools_routing_edges(self, graph: StateGraph, plugin_route_resolver: Callable) -> None:
        """Add conditional edges from control tools to plugin agents and finalizer.
        
        Args:
            graph: StateGraph to add edges to
            plugin_route_resolver: Function for resolving plugin routes
        """
        route_mapping = {}

        for plugin_bundle in self.plugin_manager.plugin_bundles.values():
            route_mapping[plugin_bundle.metadata.name] = f"{plugin_bundle.metadata.name}_agent"

        route_mapping[RoutingDecision.DONE] = GraphNodeNames.FINALIZER

        graph.add_conditional_edges(GraphNodeNames.CONTROL_TOOLS, plugin_route_resolver, route_mapping)
        
        self.logger.debug(f"Added control tools routing edges for {len(route_mapping)} routes")

    def _add_plugin_routing_edges(self, graph: StateGraph) -> None:
        """Add edges from plugin agents back to coordinator using bundle edge definitions.
        
        Args:
            graph: StateGraph to add edges to
        """
        edge_count = 0
        
        for plugin_bundle in self.plugin_manager.plugin_bundles.values():
            edges = plugin_bundle.get_graph_edges()

            self.logger.debug(f"Adding edges for plugin {plugin_bundle.metadata.name}: {edges}")

            for node_name, edge_config in edges["conditional_edges"].items():
                self.logger.debug(f"Adding conditional edge: {node_name} -> {edge_config['mapping']}")
                graph.add_conditional_edges(node_name, edge_config["condition"], edge_config["mapping"])
                edge_count += 1

            for from_node, to_node in edges["direct_edges"]:
                self.logger.debug(f"Adding direct edge: {from_node} -> {to_node}")
                graph.add_edge(from_node, to_node)
                edge_count += 1
                
        self.logger.debug(f"Added {edge_count} plugin routing edges")

    def _compile_graph(self, graph: StateGraph) -> Any:
        """Compile the graph with optional checkpointing.
        
        Args:
            graph: StateGraph to compile
            
        Returns:
            Compiled graph ready for execution
        """
        compilation_options = {"checkpointer": self.checkpointer} if self.checkpointer else {}
        compiled_graph = graph.compile(**compilation_options)
        
        self.logger.info(f"Graph compiled with checkpointer: {self.checkpointer is not None}")
        return compiled_graph

    def get_graph_info(self) -> Dict[str, Any]:
        """Get information about the graph structure.
        
        Returns:
            dict: Graph structure information
        """
        plugin_bundles = list(self.plugin_manager.plugin_bundles.values())
        
        return {
            "core_nodes": [
                GraphNodeNames.COORDINATOR,
                GraphNodeNames.CONTROL_TOOLS,
                GraphNodeNames.SUSPEND,
                GraphNodeNames.FINALIZER
            ],
            "plugin_count": len(plugin_bundles),
            "plugin_names": [bundle.metadata.name for bundle in plugin_bundles],
            "total_nodes": 4 + (len(plugin_bundles) * 2),  # 4 core + 2 per plugin (agent + tools)
            "has_checkpointer": self.checkpointer is not None,
            "coordinator_tools_count": len(self.plugin_manager.get_coordinator_tools())
        }

    def validate_graph_structure(self) -> Dict[str, Any]:
        """Validate that the graph can be properly constructed.
        
        Returns:
            dict: Validation results
        """
        validation_results = {
            "valid": True,
            "issues": [],
            "warnings": []
        }

        try:
            # Check plugin manager state
            if not self.plugin_manager:
                validation_results["valid"] = False
                validation_results["issues"].append("Plugin manager not available")
                return validation_results

            # Check for available plugins
            available_plugins = self.plugin_manager.get_available_plugins()
            if not available_plugins:
                validation_results["warnings"].append("No plugins available")

            # Check coordinator tools
            coordinator_tools = self.plugin_manager.get_coordinator_tools()
            if not coordinator_tools:
                validation_results["warnings"].append("No coordinator tools available")

            # Validate plugin bundles
            for plugin_name, plugin_bundle in self.plugin_manager.plugin_bundles.items():
                if not hasattr(plugin_bundle, 'agent_node'):
                    validation_results["issues"].append(f"Plugin {plugin_name} missing agent_node")
                    validation_results["valid"] = False
                    
                if not hasattr(plugin_bundle, 'tool_node'):
                    validation_results["issues"].append(f"Plugin {plugin_name} missing tool_node")
                    validation_results["valid"] = False

        except Exception as e:
            validation_results["valid"] = False
            validation_results["issues"].append(f"Validation error: {str(e)}")

        return validation_results

    def rebuild_graph_structure(
        self,
        coordinator_node: Callable,
        suspend_node: Callable,
        finalizer_node: Callable,
        coordinator_routing_logic: Callable,
        plugin_route_resolver: Callable
    ) -> StateGraph:
        """Rebuild the entire graph structure with updated components.
        
        This method is useful when plugins are reloaded or configuration changes.
        
        Args:
            coordinator_node: Updated coordinator node function
            suspend_node: Updated suspend node function
            finalizer_node: Updated finalizer node function
            coordinator_routing_logic: Updated coordinator routing logic
            plugin_route_resolver: Updated plugin route resolver
            
        Returns:
            Newly compiled StateGraph
        """
        self.logger.info("Rebuilding graph structure...")
        
        # Validate before rebuilding
        validation = self.validate_graph_structure()
        if not validation["valid"]:
            self.logger.error(f"Graph validation failed: {validation['issues']}")
            raise ValueError(f"Cannot rebuild invalid graph: {validation['issues']}")
            
        if validation["warnings"]:
            self.logger.warning(f"Graph warnings: {validation['warnings']}")

        # Build new graph
        new_graph = self.build_conversation_graph(
            coordinator_node=coordinator_node,
            suspend_node=suspend_node,
            finalizer_node=finalizer_node,
            coordinator_routing_logic=coordinator_routing_logic,
            plugin_route_resolver=plugin_route_resolver
        )
        
        self.logger.info("Graph structure rebuilt successfully")
        return new_graph
