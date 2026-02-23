"""Base class for shared resource caches with reference counting."""

from abc import ABC, abstractmethod
from collections.abc import Hashable
from typing import Any, Dict

from cadence_sdk import Loggable


class BaseSharedCache(Loggable, ABC):
    """Mixin providing reference-counted registry operations.

    Subclasses hold a ``_registry`` dict mapping hashable keys to
    ``(resource, ref_count)`` tuples and a ``_lock`` asyncio lock.
    """

    @abstractmethod
    def get_registry(self):
        pass

    def _increment_ref(self, key: Hashable) -> None:
        """Increment reference count for registry entry.

        Args:
            key: Registry key
        """
        if key in self.get_registry():
            resource, ref_count = self.get_registry()[key]
            self.get_registry()[key] = (resource, ref_count + 1)

    def _decrement_ref(self, key: Hashable) -> bool:
        """Decrement reference count and remove entry if zero.

        Args:
            key: Registry key

        Returns:
            True if the entry was removed (ref_count reached zero)
        """
        if key not in self.get_registry():
            return False

        resource, ref_count = self.get_registry()[key]
        new_count = ref_count - 1

        if new_count <= 0:
            del self.get_registry()[key]
            return True

        self.get_registry()[key] = (resource, new_count)
        return False

    def _is_referenced(self, key: Hashable) -> bool:
        """Check if a registry entry has active references.

        Args:
            key: Registry key

        Returns:
            True if the entry exists and has ref_count > 0
        """
        if key not in self.get_registry():
            return False
        _, ref_count = self.get_registry()[key]
        return ref_count > 0

    def _get_stats(self) -> Dict[str, Any]:
        """Compute reference count statistics.

        Returns:
            Dict with total_entries and total_references
        """
        total_entries = len(self.get_registry())
        total_refs = sum(ref_count for _, ref_count in self.get_registry().values())
        return {
            "total_entries": total_entries,
            "total_references": total_refs,
            "average_refs": total_refs / total_entries if total_entries > 0 else 0,
        }
