"""Shared template cache for LangGraph compiled StateGraphs.

This module provides a shared registry for compiled StateGraph templates
with reference counting, allowing multiple orchestrator instances to share
the same graph structure (not model bindings).
Keyed by (framework_type, mode, sorted_plugin_pids).
"""

import asyncio
import logging
from typing import Any, Dict, List, Tuple

from cadence.engine.constants import LANGGRAPH_FRAMEWORK
from cadence.engine.shared_resources.base_cache import BaseSharedCache

logger = logging.getLogger(__name__)


class SharedTemplateCache(BaseSharedCache):
    """Shared cache for LangGraph compiled StateGraph templates.

    Templates are keyed by (framework_type, mode, sorted_plugin_pids) tuple.
    This caches the graph structure, not model instances.

    Attributes:
        _registry: Dict mapping template key to (template, ref_count) tuple
        _lock: Thread lock for concurrent access safety
    """

    def __init__(self):
        """Initialize shared template cache."""
        self._registry: Dict[Tuple, Tuple[Any, int]] = {}
        self._lock = asyncio.Lock()

    def _compute_key(
        self,
        framework_type: str,
        mode: str,
        plugin_pids: List[str],
    ) -> Tuple:
        """Compute cache key for template.

        Args:
            framework_type: Framework type (langgraph, openai_agents, google_adk)
            mode: Orchestration mode (supervisor, coordinator, handoff)
            plugin_pids: List of plugin pids

        Returns:
            Cache key tuple
        """
        sorted_pids = tuple(sorted(plugin_pids))
        return (framework_type, mode, sorted_pids)

    async def get_or_create(
        self,
        framework_type: str,
        mode: str,
        plugin_pids: List[str],
        template_factory: Any,
    ) -> Tuple[Any, bool]:
        """Get existing template or create new one.

        Args:
            framework_type: Framework type
            mode: Orchestration mode
            plugin_pids: List of plugin pids
            template_factory: Callable to create template if not cached

        Returns:
            Tuple of (template, from_cache)
        """
        if framework_type != LANGGRAPH_FRAMEWORK:
            logger.debug(f"Template caching only for LangGraph, got {framework_type}")
            template = await template_factory()
            return template, False

        key = self._compute_key(framework_type, mode, plugin_pids)

        async with self._lock:
            if key in self._registry:
                template, ref_count = self._registry[key]
                self._registry[key] = (template, ref_count + 1)
                logger.debug(
                    f"Reusing template {framework_type}/{mode} "
                    f"({len(plugin_pids)} plugins), ref_count={ref_count + 1}"
                )
                return template, True

            logger.info(
                f"Creating new template {framework_type}/{mode} ({len(plugin_pids)} plugins)"
            )
            template = await template_factory()

            self._registry[key] = (template, 1)
            return template, False

    async def increment_ref(
        self,
        framework_type: str,
        mode: str,
        plugin_pids: List[str],
    ) -> None:
        """Increment reference count for template.

        Args:
            framework_type: Framework type
            mode: Orchestration mode
            plugin_pids: List of plugin pids
        """
        key = self._compute_key(framework_type, mode, plugin_pids)

        async with self._lock:
            if key in self._registry:
                template, ref_count = self._registry[key]
                self._registry[key] = (template, ref_count + 1)
                logger.debug(
                    f"Incremented ref for template {framework_type}/{mode}, ref_count={ref_count + 1}"
                )

    async def decrement_ref(
        self,
        framework_type: str,
        mode: str,
        plugin_pids: List[str],
    ) -> None:
        """Decrement reference count and cleanup if zero.

        Args:
            framework_type: Framework type
            mode: Orchestration mode
            plugin_pids: List of plugin pids
        """
        key = self._compute_key(framework_type, mode, plugin_pids)

        async with self._lock:
            if key not in self._registry:
                return

            template, ref_count = self._registry[key]
            new_count = ref_count - 1

            if new_count <= 0:
                logger.info(f"Removing template {framework_type}/{mode} (ref_count=0)")
                del self._registry[key]
            else:
                self._registry[key] = (template, new_count)
                logger.debug(
                    f"Decremented ref for template {framework_type}/{mode}, ref_count={new_count}"
                )

    async def cleanup(self) -> None:
        """Force cleanup of all templates."""
        async with self._lock:
            count = len(self._registry)
            self._registry.clear()
            logger.info(f"Cleaned up {count} templates from cache")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Statistics dictionary
        """
        total_templates = len(self._registry)
        total_refs = sum(ref_count for _, ref_count in self._registry.values())

        return {
            "total_templates": total_templates,
            "total_references": total_refs,
            "average_refs_per_template": (
                total_refs / total_templates if total_templates > 0 else 0
            ),
        }
