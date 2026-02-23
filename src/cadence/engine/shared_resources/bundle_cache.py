"""Shared bundle cache for memory-efficient plugin bundle reuse.

This module provides a shared registry for plugin bundles with reference counting.
Only stateless plugins are cached to prevent state pollution between instances.
Bundles are keyed by (plugin_pid, version, settings_hash, adapter_type).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any, Dict, Tuple

from cadence.engine.shared_resources.base_cache import BaseSharedCache

if TYPE_CHECKING:
    from cadence.infrastructure.plugins.plugin_manager import SDKPluginBundle

logger = logging.getLogger(__name__)


class SharedBundleCache(BaseSharedCache):
    """Shared cache for plugin bundles with reference counting.

    Only stateless plugins (metadata.stateless=True) are cached.
    Bundles are keyed by (plugin_pid, version, settings_hash, adapter_type).

    Attributes:
        _registry: Dict mapping bundle key to (bundle, ref_count) tuple
        _lock: Thread lock for concurrent access safety
    """

    def __init__(self):
        """Initialize shared bundle cache."""
        self._registry: Dict[Tuple, Tuple[SDKPluginBundle, int]] = {}
        self._lock = asyncio.Lock()

    def _compute_settings_hash(self, settings: Dict[str, Any]) -> str:
        """Compute hash of plugin settings.

        Args:
            settings: Plugin settings dictionary

        Returns:
            Hash string
        """
        settings_json = json.dumps(settings, sort_keys=True)
        return hashlib.sha256(settings_json.encode()).hexdigest()[:16]

    def _compute_key(
        self,
        plugin_pid: str,
        version: str,
        settings: Dict[str, Any],
        adapter_type: str,
    ) -> Tuple:
        """Compute cache key for bundle.

        Args:
            plugin_pid: Reverse-domain plugin identifier
            version: Plugin version
            settings: Plugin settings
            adapter_type: Adapter type (langchain, openai, google)

        Returns:
            Cache key tuple
        """
        settings_hash = self._compute_settings_hash(settings)
        return plugin_pid, version, settings_hash, adapter_type

    async def get_or_create(
        self,
        plugin_pid: str,
        version: str,
        settings: Dict[str, Any],
        adapter_type: str,
        is_stateless: bool,
        bundle_factory: Callable[[], Coroutine[Any, Any, SDKPluginBundle]],
    ) -> Tuple[SDKPluginBundle, bool]:
        """Get existing bundle or create new one.

        Only caches stateless bundles.

        Args:
            plugin_pid: Reverse-domain plugin identifier
            version: Plugin version
            settings: Plugin settings
            adapter_type: Adapter type
            is_stateless: Whether plugin is stateless
            bundle_factory: Callable to create bundle if not cached

        Returns:
            Tuple of (bundle, from_cache)
        """
        if not is_stateless:
            logger.debug(f"Plugin {plugin_pid} is stateful, not caching")
            bundle = await bundle_factory()
            return bundle, False

        key = self._compute_key(plugin_pid, version, settings, adapter_type)

        async with self._lock:
            if key in self._registry:
                bundle, ref_count = self._registry[key]
                self._registry[key] = (bundle, ref_count + 1)
                logger.debug(
                    f"Reusing bundle {plugin_pid}@{version}, ref_count={ref_count + 1}"
                )
                return bundle, True

            logger.info(f"Creating new bundle {plugin_pid}@{version}")
            bundle = await bundle_factory()

            self._registry[key] = (bundle, 1)
            return bundle, False

    async def increment_ref(
        self,
        plugin_pid: str,
        version: str,
        settings: Dict[str, Any],
        adapter_type: str,
    ) -> None:
        """Increment reference count for bundle.

        Args:
            plugin_pid: Reverse-domain plugin identifier
            version: Plugin version
            settings: Plugin settings
            adapter_type: Adapter type
        """
        key = self._compute_key(plugin_pid, version, settings, adapter_type)

        async with self._lock:
            if key in self._registry:
                bundle, ref_count = self._registry[key]
                self._registry[key] = (bundle, ref_count + 1)
                logger.debug(
                    f"Incremented ref for {plugin_pid}, ref_count={ref_count + 1}"
                )

    async def decrement_ref(
        self,
        plugin_pid: str,
        version: str,
        settings: Dict[str, Any],
        adapter_type: str,
    ) -> None:
        """Decrement reference count and cleanup if zero.

        Args:
            plugin_pid: Reverse-domain plugin identifier
            version: Plugin version
            settings: Plugin settings
            adapter_type: Adapter type
        """
        key = self._compute_key(plugin_pid, version, settings, adapter_type)

        async with self._lock:
            if key not in self._registry:
                return

            bundle, ref_count = self._registry[key]
            new_count = ref_count - 1

            if new_count <= 0:
                logger.info(f"Removing bundle {plugin_pid} (ref_count=0)")
                if hasattr(bundle, "cleanup"):
                    await bundle.cleanup()
                del self._registry[key]
            else:
                self._registry[key] = (bundle, new_count)
                logger.debug(f"Decremented ref for {plugin_pid}, ref_count={new_count}")

    async def cleanup(self) -> None:
        """Force cleanup of all bundles."""
        async with self._lock:
            count = len(self._registry)
            for bundle, _ in self._registry.values():
                if hasattr(bundle, "cleanup"):
                    try:
                        await bundle.cleanup()
                    except Exception as e:
                        logger.error(f"Bundle cleanup error: {e}")

            self._registry.clear()
            logger.info(f"Cleaned up {count} bundles from cache")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Statistics dictionary
        """
        total_bundles = len(self._registry)
        total_refs = sum(ref_count for _, ref_count in self._registry.values())

        return {
            "total_bundles": total_bundles,
            "total_references": total_refs,
            "average_refs_per_bundle": (
                total_refs / total_bundles if total_bundles > 0 else 0
            ),
        }
