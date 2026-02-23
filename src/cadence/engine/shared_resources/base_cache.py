"""Base class for shared resource caches with reference counting."""

import logging
from abc import ABC
from collections.abc import Hashable
from typing import Any, Dict

logger = logging.getLogger(__name__)


class BaseSharedCache(ABC):
    """Mixin providing reference-counted registry operations.

    Subclasses hold a ``_registry`` dict mapping hashable keys to
    ``(resource, ref_count)`` tuples and a ``_lock`` asyncio lock.
    """

    def _increment_ref(self, key: Hashable) -> None:
        """Increment reference count for registry entry.

        Args:
            key: Registry key
        """
        if key in self._registry:
            resource, ref_count = self._registry[key]
            self._registry[key] = (resource, ref_count + 1)

    def _decrement_ref(self, key: Hashable) -> bool:
        """Decrement reference count and remove entry if zero.

        Args:
            key: Registry key

        Returns:
            True if the entry was removed (ref_count reached zero)
        """
        if key not in self._registry:
            return False

        resource, ref_count = self._registry[key]
        new_count = ref_count - 1

        if new_count <= 0:
            del self._registry[key]
            return True

        self._registry[key] = (resource, new_count)
        return False

    def _is_referenced(self, key: Hashable) -> bool:
        """Check if a registry entry has active references.

        Args:
            key: Registry key

        Returns:
            True if the entry exists and has ref_count > 0
        """
        if key not in self._registry:
            return False
        _, ref_count = self._registry[key]
        return ref_count > 0

    def _get_stats(self) -> Dict[str, Any]:
        """Compute reference count statistics.

        Returns:
            Dict with total_entries and total_references
        """
        total_entries = len(self._registry)
        total_refs = sum(ref_count for _, ref_count in self._registry.values())
        return {
            "total_entries": total_entries,
            "total_references": total_refs,
            "average_refs": total_refs / total_entries if total_entries > 0 else 0,
        }
