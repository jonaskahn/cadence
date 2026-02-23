"""Orchestrator pool for managing multiple orchestrator instances.

This module provides a simple pool implementation (single tier) for MVP.
Phase 8 will extend this with Hot/Warm/Cold tiers and shared resources.
"""

import asyncio
import logging
from typing import Any, Optional

from cadence.engine.base import BaseOrchestrator
from cadence.engine.factory import OrchestratorFactory

logger = logging.getLogger(__name__)


class OrchestratorPool:
    """Simple orchestrator pool for MVP.

    Manages multiple orchestrator instances with hot-reload support.
    All instances kept in Hot tier (fully built and ready).

    Phase 8 will add Warm/Cold tiers and shared resource optimization.

    Attributes:
        factory: Orchestrator factory for creating instances
        db_repositories: Database repositories for loading instance config
        instances: Dict mapping instance_id to orchestrator
        locks: Per-instance locks for concurrency safety
    """

    def __init__(
        self,
        factory: OrchestratorFactory,
        db_repositories: dict[str, Any],
    ):
        """Initialize orchestrator pool.

        Args:
            factory: Orchestrator factory
            db_repositories: Database repositories (orchestrator_instance_repo, etc.)
        """
        self.factory = factory
        self.db_repositories = db_repositories
        self.instances: dict[str, BaseOrchestrator] = {}
        self.locks: dict[str, asyncio.Lock] = {}
        self._hashes: dict[str, str] = {}

    async def get(self, instance_id: str) -> BaseOrchestrator:
        """Get orchestrator instance.

        Args:
            instance_id: Orchestrator instance ID

        Returns:
            Orchestrator instance

        Raises:
            ValueError: If instance not found
        """
        if instance_id not in self.instances:
            logger.info(f"Instance not in pool, loading from DB: {instance_id}")
            return await self._load_from_db(instance_id)

        return self.instances[instance_id]

    async def create_instance(
        self,
        instance_id: str,
        org_id: str,
        framework_type: str,
        mode: str,
        instance_config: dict[str, Any],
        resolved_config: dict[str, Any],
    ) -> BaseOrchestrator:
        """Create and register new orchestrator instance.

        Args:
            instance_id: Unique instance identifier
            org_id: Organization ID
            framework_type: Framework type (langgraph, openai_agents, google_adk)
            mode: Orchestration mode (supervisor, coordinator, handoff)
            instance_config: Instance-specific configuration
            resolved_config: Fully resolved configuration (3-tier merged)

        Returns:
            Created orchestrator instance

        Raises:
            ValueError: If instance already exists
        """
        if instance_id in self.instances:
            raise ValueError(f"Instance '{instance_id}' already exists")

        self._ensure_lock(instance_id)

        async with self.locks[instance_id]:
            logger.info(f"Creating orchestrator instance: {instance_id}")

            orchestrator = await self.factory.create(
                framework_type=framework_type,
                mode=mode,
                org_id=org_id,
                instance_config=instance_config,
                resolved_config=resolved_config,
            )

            self.instances[instance_id] = orchestrator

            logger.info(f"Instance created: {instance_id} ({framework_type}/{mode})")

            return orchestrator

    async def reload_instance(
        self,
        instance_id: str,
        org_id: str,
        framework_type: str,
        mode: str,
        instance_config: dict[str, Any],
        resolved_config: dict[str, Any],
    ) -> None:
        """Hot-reload orchestrator instance with new configuration.

        Atomic swap procedure:
        1. Acquire lock for instance
        2. Build new orchestrator with updated config
        3. Cleanup old orchestrator
        4. Replace in registry atomically
        5. Release lock

        Args:
            instance_id: Instance ID to reload
            org_id: Organization ID
            framework_type: Framework type
            mode: Orchestration mode
            instance_config: New instance configuration
            resolved_config: New resolved configuration
        """
        if instance_id not in self.instances:
            raise ValueError(f"Instance '{instance_id}' not found")

        self._ensure_lock(instance_id)

        async with self.locks[instance_id]:
            logger.info(f"Reloading orchestrator instance: {instance_id}")

            old_orchestrator = self.instances[instance_id]

            try:
                new_orchestrator = await self.factory.create(
                    framework_type=framework_type,
                    mode=mode,
                    org_id=org_id,
                    instance_config=instance_config,
                    resolved_config=resolved_config,
                )

                await old_orchestrator.cleanup()

                self.instances[instance_id] = new_orchestrator

                logger.info(f"Instance reloaded successfully: {instance_id}")

            except Exception as e:
                logger.error(
                    f"Failed to reload instance {instance_id}: {e}", exc_info=True
                )
                raise

    async def remove_instance(self, instance_id: str) -> None:
        """Remove orchestrator instance from pool.

        Args:
            instance_id: Instance ID to remove

        Raises:
            ValueError: If instance not found
        """
        if instance_id not in self.instances:
            raise ValueError(f"Instance '{instance_id}' not found")

        self._ensure_lock(instance_id)

        async with self.locks[instance_id]:
            logger.info(f"Removing orchestrator instance: {instance_id}")

            orchestrator = self.instances[instance_id]
            await orchestrator.cleanup()

            del self.instances[instance_id]
            del self.locks[instance_id]

            logger.info(f"Instance removed: {instance_id}")

    async def list_all(self) -> list[str]:
        """List all instance IDs in pool.

        Returns:
            List of instance IDs
        """
        return list(self.instances.keys())

    async def health_check_all(self) -> dict[str, dict[str, Any]]:
        """Check health of all instances.

        Returns:
            Dict mapping instance_id to health status
        """
        health_results = {}

        for instance_id, orchestrator in self.instances.items():
            try:
                health = await orchestrator.health_check()
                health_results[instance_id] = {
                    "status": "healthy",
                    "details": health,
                }
            except Exception as e:
                logger.error(f"Health check failed for {instance_id}: {e}")
                health_results[instance_id] = {
                    "status": "unhealthy",
                    "error": str(e),
                }

        return health_results

    def get_stats(self) -> dict[str, Any]:
        """Get pool statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "total_instances": len(self.instances),
            "instance_ids": list(self.instances.keys()),
            "tier": "hot",
        }

    @property
    def hot_tier(self) -> dict[str, BaseOrchestrator]:
        """Alias for instances dict (all instances are hot-tier in MVP)."""
        return self.instances

    async def cleanup_all(self) -> None:
        """Cleanup all orchestrator instances and clear pool."""
        for orch in list(self.instances.values()):
            try:
                await orch.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up orchestrator: {e}")
        self.instances.clear()
        self.locks.clear()
        self._hashes.clear()

    def get_hash(self, instance_id: str) -> Optional[str]:
        """Get stored config hash for an instance.

        Args:
            instance_id: Instance ID

        Returns:
            Config hash or None
        """
        return self._hashes.get(instance_id)

    def set_hash(self, instance_id: str, config_hash: str) -> None:
        """Store config hash for an instance.

        Args:
            instance_id: Instance ID
            config_hash: SHA-256 hash of configuration
        """
        self._hashes[instance_id] = config_hash

    async def _load_from_db(self, instance_id: str) -> BaseOrchestrator:
        """Load instance from DB into pool (Hot tier).

        Used when an instance exists in DB but has not been loaded into the
        in-memory pool, e.g. after a restart.

        Args:
            instance_id: Instance ID

        Returns:
            Orchestrator instance

        Raises:
            ValueError: If instance not found in database
        """
        instance_repo = self.db_repositories.get("orchestrator_instance_repo")

        if not instance_repo:
            raise ValueError(
                f"Orchestrator instance '{instance_id}' not found in pool "
                f"and no instance repository configured"
            )

        instance = await instance_repo.get_by_id(instance_id)
        if not instance:
            raise ValueError(
                f"Orchestrator instance '{instance_id}' not found in pool or database"
            )

        instance_config = {
            **instance["config"],
            "plugin_settings": instance.get("plugin_settings", {}),
        }
        resolved_config = {**instance_config, "org_id": instance["org_id"]}

        orchestrator = await self.factory.create(
            framework_type=instance["framework_type"],
            mode=instance["mode"],
            org_id=instance["org_id"],
            instance_config=instance_config,
            resolved_config=resolved_config,
        )

        self.instances[instance_id] = orchestrator
        return orchestrator

    def _ensure_lock(self, instance_id: str) -> None:
        """Ensure lock exists for instance.

        Args:
            instance_id: Instance ID
        """
        if instance_id not in self.locks:
            self.locks[instance_id] = asyncio.Lock()
