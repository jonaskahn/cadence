"""Tool collection and plugin-tool mapping for the LangGraph supervisor.

Manages collecting orchestrator_tools from all loaded SDKPluginBundles and
maintaining reverse lookup from tool name to plugin pid.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from cadence.infrastructure.plugins import SDKPluginBundle

logger = logging.getLogger(__name__)


class SupervisorToolCollector:
    """Collects and indexes orchestrator tools from plugin bundles.

    Provides centralized tool management:
    - Collects all orchestrator_tools from loaded plugin bundles
    - Maintains tool-to-plugin mapping for tracking which plugin was called
    - Enables queries by plugin pid or tool name
    - Aggregates plugin capabilities for prompt building
    """

    def __init__(self, bundles: Dict[str, SDKPluginBundle]) -> None:
        """Initialize with a dict of loaded plugin bundles.

        Args:
            bundles: Dict mapping pid to SDKPluginBundle
        """
        self._bundles = bundles
        self._tool_to_plugin_map: Dict[str, str] = {}

    def collect_all_tools(self) -> List[Any]:
        """Collect all orchestrator_tools from all bundles.

        Returns:
            Flat list of LangChain-compatible tools across all plugins
        """
        all_tools: List[Any] = []
        self._tool_to_plugin_map.clear()

        for pid, bundle in self._bundles.items():
            tools = self._collect_bundle_tools(pid, bundle)
            all_tools.extend(tools)

        logger.info(
            "Collected %d tools from %d plugin bundles",
            len(all_tools),
            len(self._bundles),
        )
        return all_tools

    def _collect_bundle_tools(self, pid: str, bundle: SDKPluginBundle) -> List[Any]:
        """Collect tools from a single bundle.

        Args:
            pid: Plugin identifier
            bundle: Plugin bundle

        Returns:
            List of tools, empty if collection fails
        """
        try:
            tools = bundle.orchestrator_tools
            for tool in tools:
                self._tool_to_plugin_map[tool.name] = pid
            logger.debug("Collected %d tools from plugin: %s", len(tools), pid)
            return tools
        except Exception as e:
            logger.error("Failed to collect tools from plugin %s: %s", pid, e)
            return []

    def get_plugin_for_tool(self, tool_name: str) -> Optional[str]:
        """Get the plugin pid that owns the specified tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Plugin pid or None if not found
        """
        return self._tool_to_plugin_map.get(tool_name)

    def get_tools_for_plugin(self, pid: str) -> List[Any]:
        """Get all tools belonging to the specified plugin.

        Args:
            pid: Plugin identifier

        Returns:
            List of tools or empty list if plugin not found
        """
        bundle = self._bundles.get(pid)
        return bundle.orchestrator_tools if bundle else []

    def get_plugin_capabilities(self) -> Dict[str, List[str]]:
        """Get capability listings for all plugins.

        Returns:
            Dict mapping pid to list of capability strings
        """
        return {
            pid: (bundle.metadata.capabilities or [])
            for pid, bundle in self._bundles.items()
        }
