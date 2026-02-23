"""Multi-tier orchestrator pool for memory-efficient scaling.

This module provides a three-tier pool architecture (Hot/Warm/Cold) with
shared resource registries to minimize memory usage when running thousands
of orchestrator instances.
"""

import asyncio
import logging
import time
from typing import Any, Optional

from cadence.constants import (
    BYTES_PER_MEGABYTE,
    COLD_TIER_ENTRY_BYTES_ESTIMATE,
    DEFAULT_PREWARM_COUNT,
    HOT_TIER_ENTRY_BYTES_ESTIMATE,
    WARM_TIER_ENTRY_BYTES_ESTIMATE,
)
from cadence.engine.base import BaseOrchestrator
from cadence.engine.constants import DEFAULT_MAX_HOT_POOL_SIZE, DEFAULT_WARM_TIER_TTL
from cadence.engine.factory import OrchestratorFactory
from cadence.engine.shared_resources import (
    SharedBundleCache,
    SharedModelPool,
    SharedTemplateCache,
)
from cadence.repository.orchestrator_instance_repository import (
    OrchestratorInstanceRepository,
)
from cadence.service import SettingsService

logger = logging.getLogger(__name__)


class MultiTierOrchestratorPool:
    """Multi-tier orchestrator pool with Hot/Warm/Cold tiers.

    Tier definitions:
    - Cold: Minimal metadata only (~100 bytes per instance)
    - Warm: Config cached in memory (~1-5 KB per instance)
    - Hot: Fully built orchestrator (~5-50 MB per instance)

    LRU eviction keeps Hot tier bounded while allowing on-demand promotion.

    Attributes:
        factory: Orchestrator factory
        instance_repo: Instance repository for loading configs
        settings_service: Settings service for resolving configs
        model_pool: Shared model pool
        bundle_cache: Shared bundle cache
        template_cache: Shared template cache
        max_hot_pool_size: Maximum Hot tier instances
        warm_tier_ttl: Warm tier expiration time in seconds
        prewarm_strategy: Strategy for prewarming (recent/all/none)
        prewarm_count: Number of instances to prewarm
        cold_tier: Dict[instance_id, metadata]
        warm_tier: Dict[instance_id, warm_data]
        hot_tier: Dict[instance_id, orchestrator]
        locks: Per-instance locks
        access_times: Dict[instance_id, last_access_time]
    """

    def __init__(
        self,
        factory: OrchestratorFactory,
        instance_repo: OrchestratorInstanceRepository,
        settings_service: SettingsService,
        max_hot_pool_size: int = DEFAULT_MAX_HOT_POOL_SIZE,
        warm_tier_ttl: int = DEFAULT_WARM_TIER_TTL,
        prewarm_strategy: str = "recent",
        prewarm_count: int = DEFAULT_PREWARM_COUNT,
    ):
        """Initialize multi-tier pool.

        Args:
            factory: Orchestrator factory
            instance_repo: Instance repository
            settings_service: Settings service
            max_hot_pool_size: Max Hot tier size (default: 200)
            warm_tier_ttl: Warm tier TTL in seconds (default: 3600)
            prewarm_strategy: Prewarming strategy (default: "recent")
            prewarm_count: Instances to prewarm (default: 100)
        """
        self.factory = factory
        self.instance_repo = instance_repo
        self.settings_service = settings_service

        self.max_hot_pool_size = max_hot_pool_size
        self.warm_tier_ttl = warm_tier_ttl
        self.prewarm_strategy = prewarm_strategy
        self.prewarm_count = prewarm_count

        self.model_pool = SharedModelPool()
        self.bundle_cache = SharedBundleCache()
        self.template_cache = SharedTemplateCache()
        self.factory.bundle_cache = self.bundle_cache

        self.cold_tier: dict[str, dict[str, Any]] = {}
        self.warm_tier: dict[str, dict[str, Any]] = {}
        self.hot_tier: dict[str, BaseOrchestrator] = {}

        self.locks: dict[str, asyncio.Lock] = {}
        self.access_times: dict[str, float] = {}
        self._hot_hashes: dict[str, str] = {}

    async def get(self, instance_id: str) -> BaseOrchestrator:
        """Get orchestrator instance, promoting through tiers if needed.

        Tier promotion flow:
        - If in Hot: Return immediately
        - If in Warm: Promote to Hot
        - If in Cold: Load to Warm, promote to Hot
        - If not found: Raise error

        Args:
            instance_id: Instance ID

        Returns:
            Orchestrator instance

        Raises:
            ValueError: If instance not found
        """
        self.access_times[instance_id] = time.time()

        if instance_id in self.hot_tier:
            logger.debug(f"Hot tier hit: {instance_id}")
            return self.hot_tier[instance_id]

        if instance_id in self.warm_tier:
            logger.info(f"Warm tier hit, promoting to Hot: {instance_id}")
            return await self._promote_warm_to_hot(instance_id)

        if instance_id in self.cold_tier:
            logger.info(f"Cold tier hit, loading to Warm then Hot: {instance_id}")
            await self._promote_cold_to_warm(instance_id)
            return await self._promote_warm_to_hot(instance_id)

        logger.info(f"Instance not in any tier, loading from DB: {instance_id}")
        return await self._load_from_db(instance_id)

    async def create_instance(
        self,
        instance_id: str,
        org_id: str,
        framework_type: str,
        mode: str,
        instance_config: dict[str, Any],
        resolved_config: dict[str, Any],
    ) -> BaseOrchestrator:
        """Create instance directly in Hot tier.

        Args:
            instance_id: Instance ID
            org_id: Organization ID
            framework_type: Framework type
            mode: Orchestration mode
            instance_config: Instance config
            resolved_config: Resolved config

        Returns:
            Created orchestrator
        """
        if self._instance_exists(instance_id):
            raise ValueError(f"Instance '{instance_id}' already exists")

        self._ensure_lock(instance_id)

        async with self.locks[instance_id]:
            await self._check_hot_tier_capacity()

            logger.info(f"Creating instance in Hot tier: {instance_id}")

            orchestrator = await self.factory.create(
                framework_type=framework_type,
                mode=mode,
                org_id=org_id,
                instance_config=instance_config,
                resolved_config=resolved_config,
            )

            self.hot_tier[instance_id] = orchestrator
            self.access_times[instance_id] = time.time()

            return orchestrator

    def get_hash(self, instance_id: str) -> Optional[str]:
        """Return the config_hash stored when instance was last loaded into hot tier.

        Args:
            instance_id: Instance ID

        Returns:
            Config hash string or None if not in hot tier / no hash stored
        """
        return self._hot_hashes.get(instance_id)

    def set_hash(self, instance_id: str, config_hash: str) -> None:
        """Store a config_hash for a hot-tier instance.

        Args:
            instance_id: Instance ID
            config_hash: Config hash to store
        """
        self._hot_hashes[instance_id] = config_hash

    async def reload_instance(
        self,
        instance_id: str,
        org_id: str,
        framework_type: str,
        mode: str,
        instance_config: dict[str, Any],
        resolved_config: dict[str, Any],
    ) -> None:
        """Reload instance with new config.

        Args:
            instance_id: Instance ID
            org_id: Organization ID
            framework_type: Framework type
            mode: Orchestration mode
            instance_config: New instance config
            resolved_config: New resolved config
        """
        if not self._instance_exists(instance_id):
            raise ValueError(f"Instance '{instance_id}' not found")

        self._ensure_lock(instance_id)

        async with self.locks[instance_id]:
            logger.info(f"Reloading instance: {instance_id}")

            if instance_id in self.hot_tier:
                old_orchestrator = self.hot_tier[instance_id]
                await old_orchestrator.cleanup()
            elif instance_id in self.warm_tier:
                del self.warm_tier[instance_id]
            elif instance_id in self.cold_tier:
                del self.cold_tier[instance_id]

            orchestrator = await self.factory.create(
                framework_type=framework_type,
                mode=mode,
                org_id=org_id,
                instance_config=instance_config,
                resolved_config=resolved_config,
            )

            self.hot_tier[instance_id] = orchestrator
            self.access_times[instance_id] = time.time()

            logger.info(f"Instance reloaded: {instance_id}")

    async def remove_instance(self, instance_id: str) -> None:
        """Remove instance from pool.

        Args:
            instance_id: Instance ID
        """
        if not self._instance_exists(instance_id):
            raise ValueError(f"Instance '{instance_id}' not found")

        self._ensure_lock(instance_id)

        async with self.locks[instance_id]:
            logger.info(f"Removing instance: {instance_id}")

            if instance_id in self.hot_tier:
                await self.hot_tier[instance_id].cleanup()
                del self.hot_tier[instance_id]
            elif instance_id in self.warm_tier:
                del self.warm_tier[instance_id]
            elif instance_id in self.cold_tier:
                del self.cold_tier[instance_id]

            if instance_id in self.access_times:
                del self.access_times[instance_id]
            self._hot_hashes.pop(instance_id, None)
            del self.locks[instance_id]

            logger.info(f"Instance removed: {instance_id}")

    async def evict_to_warm(self, instance_id: str) -> None:
        """Demote instance from Hot to Warm tier.

        Args:
            instance_id: Instance ID
        """
        if instance_id not in self.hot_tier:
            return

        logger.info(f"Evicting to Warm tier: {instance_id}")

        orchestrator = self.hot_tier[instance_id]
        await orchestrator.cleanup()

        warm_data = {
            "org_id": getattr(orchestrator, "org_id", ""),
            "framework_type": orchestrator.framework_type,
            "mode": orchestrator.mode,
            "last_accessed": self.access_times.get(instance_id, time.time()),
        }

        self.warm_tier[instance_id] = warm_data
        del self.hot_tier[instance_id]

    async def prewarm(self, instance_ids: list[str]) -> None:
        """Prewarm instances to Hot tier.

        Args:
            instance_ids: List of instance IDs to prewarm
        """
        logger.info(f"Prewarming {len(instance_ids)} instances")

        for instance_id in instance_ids:
            try:
                if instance_id not in self.hot_tier:
                    await self.get(instance_id)
            except Exception as e:
                logger.error(f"Failed to prewarm {instance_id}: {e}")

    async def cleanup_all(self) -> None:
        """Cleanup all tiers."""
        logger.info("Cleaning up all tiers")

        for orchestrator in self.hot_tier.values():
            try:
                await orchestrator.cleanup()
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

        self.hot_tier.clear()
        self.warm_tier.clear()
        self.cold_tier.clear()
        self.access_times.clear()
        self._hot_hashes.clear()

        await self.model_pool.cleanup()
        await self.bundle_cache.cleanup()
        await self.template_cache.cleanup()

    def get_stats(self) -> dict[str, Any]:
        """Get pool statistics.

        Returns:
            Statistics dictionary
        """
        model_stats = self.model_pool.get_stats()
        bundle_stats = self.bundle_cache.get_stats()
        template_stats = self.template_cache.get_stats()

        return {
            "total_instances": len(self.cold_tier)
            + len(self.warm_tier)
            + len(self.hot_tier),
            "hot_tier_count": len(self.hot_tier),
            "warm_tier_count": len(self.warm_tier),
            "cold_tier_count": len(self.cold_tier),
            "shared_model_count": model_stats["total_models"],
            "shared_bundle_count": bundle_stats["total_bundles"],
            "shared_template_count": template_stats["total_templates"],
            "memory_estimate_mb": self._estimate_memory(),
        }

    async def health_check_all(self) -> dict[str, dict[str, Any]]:
        """Health check all Hot tier instances.

        Returns:
            Dict mapping instance_id to health status
        """
        health_results = {}

        for instance_id, orchestrator in self.hot_tier.items():
            try:
                health = await orchestrator.health_check()
                health_results[instance_id] = {
                    "status": "healthy",
                    "tier": "hot",
                    "details": health,
                }
            except Exception as e:
                logger.error(f"Health check failed for {instance_id}: {e}")
                health_results[instance_id] = {
                    "status": "unhealthy",
                    "tier": "hot",
                    "error": str(e),
                }

        return health_results

    async def _promote_warm_to_hot(self, instance_id: str) -> BaseOrchestrator:
        """Promote instance from Warm to Hot tier.

        Args:
            instance_id: Instance ID

        Returns:
            Orchestrator instance
        """
        await self._check_hot_tier_capacity()

        instance = await self.instance_repo.get_by_id(instance_id)
        if not instance:
            raise ValueError(f"Instance {instance_id} not found in database")

        resolved_config = {**instance["config"], "org_id": instance["org_id"]}

        orchestrator = await self.factory.create(
            framework_type=instance["framework_type"],
            mode=instance["mode"],
            org_id=instance["org_id"],
            instance_config=instance["config"],
            resolved_config=resolved_config,
        )

        self.hot_tier[instance_id] = orchestrator
        del self.warm_tier[instance_id]

        return orchestrator

    async def _promote_cold_to_warm(self, instance_id: str) -> None:
        """Promote instance from Cold to Warm tier.

        Args:
            instance_id: Instance ID
        """
        instance = await self.instance_repo.get_by_id(instance_id)
        if not instance:
            raise ValueError(f"Instance {instance_id} not found in database")

        warm_data = {
            "org_id": instance["org_id"],
            "framework_type": instance["framework_type"],
            "mode": instance["mode"],
            "config": instance["config"],
            "last_accessed": time.time(),
        }

        self.warm_tier[instance_id] = warm_data
        del self.cold_tier[instance_id]

    async def _load_from_db(self, instance_id: str) -> BaseOrchestrator:
        """Load instance directly from DB into Hot tier (no warm tier transition).

        Used when an instance exists in DB but is not in any in-memory tier,
        e.g. after a restart when only hot instances were pre-loaded.

        Args:
            instance_id: Instance ID

        Returns:
            Orchestrator instance

        Raises:
            ValueError: If instance not found in database
        """
        await self._check_hot_tier_capacity()

        instance = await self.instance_repo.get_by_id(instance_id)
        if not instance:
            raise ValueError(f"Instance '{instance_id}' not found in pool or database")

        resolved_config = {**instance["config"], "org_id": instance["org_id"]}

        orchestrator = await self.factory.create(
            framework_type=instance["framework_type"],
            mode=instance["mode"],
            org_id=instance["org_id"],
            instance_config=instance["config"],
            resolved_config=resolved_config,
        )

        self.hot_tier[instance_id] = orchestrator
        self.access_times[instance_id] = time.time()
        return orchestrator

    async def _check_hot_tier_capacity(self) -> None:
        """Check Hot tier capacity and evict LRU if needed."""
        if len(self.hot_tier) >= self.max_hot_pool_size:
            logger.warning(
                f"Hot tier at capacity ({self.max_hot_pool_size}), evicting LRU"
            )
            await self._evict_lru()

    async def _evict_lru(self) -> None:
        """Evict least recently used instance from Hot to Warm."""
        if not self.hot_tier:
            return

        lru_instance_id = min(
            self.hot_tier.keys(),
            key=lambda instance_id: self.access_times.get(instance_id, 0),
        )

        await self.evict_to_warm(lru_instance_id)
        logger.info(f"Evicted LRU instance: {lru_instance_id}")

    def _estimate_memory(self) -> float:
        """Estimate total memory usage in MB.

        Returns:
            Estimated memory in MB
        """
        cold_bytes = len(self.cold_tier) * COLD_TIER_ENTRY_BYTES_ESTIMATE
        warm_bytes = len(self.warm_tier) * WARM_TIER_ENTRY_BYTES_ESTIMATE
        hot_bytes = len(self.hot_tier) * HOT_TIER_ENTRY_BYTES_ESTIMATE

        total_bytes = cold_bytes + warm_bytes + hot_bytes
        return total_bytes / BYTES_PER_MEGABYTE

    def _instance_exists(self, instance_id: str) -> bool:
        """Return True if instance is present in any tier."""
        return (
            instance_id in self.cold_tier
            or instance_id in self.warm_tier
            or instance_id in self.hot_tier
        )

    def _ensure_lock(self, instance_id: str) -> None:
        """Ensure lock exists for instance.

        Args:
            instance_id: Instance ID
        """
        if instance_id not in self.locks:
            self.locks[instance_id] = asyncio.Lock()
