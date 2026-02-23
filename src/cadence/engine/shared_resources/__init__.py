"""Shared resource registries for memory-efficient orchestrator pool.

This package provides shared registries for models, plugin bundles, and
graph templates to minimize memory usage when running many orchestrator instances.
"""

from cadence.engine.shared_resources.bundle_cache import SharedBundleCache
from cadence.engine.shared_resources.model_pool import SharedModelPool
from cadence.engine.shared_resources.template_cache import SharedTemplateCache

__all__ = [
    "SharedBundleCache",
    "SharedModelPool",
    "SharedTemplateCache",
]
