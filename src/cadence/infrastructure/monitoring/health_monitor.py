"""Health monitoring service for orchestrators.

This module provides background health checks with auto-recovery
for orchestrator instances.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from cadence.constants import (
    HEALTH_MONITOR_INTERVAL_SECONDS,
    HEALTH_MONITOR_MAX_FAILURES,
    HEALTH_MONITOR_RECOVERY_INTERVAL,
)
from cadence.engine.pool import OrchestratorPool

logger = logging.getLogger(__name__)


class HealthMonitor:
    """Background health monitor for orchestrator pool.

    Periodically checks health of all orchestrators and attempts
    auto-recovery for failed instances.

    Attributes:
        pool: OrchestratorPool instance
        check_interval: Seconds between health checks
        failure_threshold: Consecutive failures before marking as error
        recovery_backoff: Seconds to wait before retry after failure
        _running: Whether monitor is running
        _task: Background task handle
        _failure_counts: Dict tracking consecutive failures per instance
        _recovery_attempts: Dict tracking recovery attempts per instance
    """

    def __init__(
        self,
        pool: OrchestratorPool,
        check_interval: int = HEALTH_MONITOR_INTERVAL_SECONDS,
        failure_threshold: int = HEALTH_MONITOR_MAX_FAILURES,
        recovery_backoff: int = HEALTH_MONITOR_RECOVERY_INTERVAL,
    ):
        """Initialize health monitor.

        Args:
            pool: OrchestratorPool instance
            check_interval: Seconds between health checks (default 60)
            failure_threshold: Consecutive failures before error (default 3)
            recovery_backoff: Seconds before retry (default 300 = 5 min)
        """
        self.pool = pool
        self.check_interval = check_interval
        self.failure_threshold = failure_threshold
        self.recovery_backoff = recovery_backoff

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._failure_counts: Dict[str, int] = {}
        self._recovery_attempts: Dict[str, Dict[str, Any]] = {}

        logger.info(
            f"Initialized HealthMonitor: interval={check_interval}s, "
            f"threshold={failure_threshold}, backoff={recovery_backoff}s"
        )

    async def start(self) -> None:
        """Start background health monitoring."""
        if self._running:
            logger.warning("HealthMonitor already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())

        logger.info("HealthMonitor started")

    async def stop(self) -> None:
        """Stop background health monitoring."""
        if not self._running:
            return

        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("HealthMonitor stopped")

    async def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        logger.info("HealthMonitor loop started")

        while self._running:
            try:
                await self._run_health_checks()
                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                logger.info("HealthMonitor loop cancelled")
                break

            except Exception as e:
                logger.error(f"HealthMonitor loop error: {e}", exc_info=True)
                await asyncio.sleep(self.check_interval)

    async def _run_health_checks(self) -> None:
        """Run health checks on all orchestrators."""
        try:
            instance_ids = await self.pool.list_all()

            if not instance_ids:
                logger.debug("No orchestrators to check")
                return

            logger.debug(f"Running health checks for {len(instance_ids)} instances")

            for instance_id in instance_ids:
                await self._check_instance_health(instance_id)

        except Exception as e:
            logger.error(f"Health check batch failed: {e}", exc_info=True)

    async def _check_instance_health(self, instance_id: str) -> None:
        """Check health of single orchestrator instance.

        Args:
            instance_id: Instance ID
        """
        try:
            orchestrator = await self.pool.get(instance_id)
            health_status = await orchestrator.health_check()

            if health_status.get("is_ready", False):
                self._record_success(instance_id)
                logger.debug(f"Health check PASS: {instance_id}")
            else:
                self._handle_health_check_failure(instance_id, health_status)

        except Exception as e:
            self._record_failure(instance_id)
            logger.error(
                f"Health check ERROR: {instance_id}, error={e}",
                exc_info=True,
            )

            if self._should_attempt_recovery(instance_id):
                await self._attempt_recovery(instance_id)

    async def _handle_health_check_failure(
        self, instance_id: str, health_status: Dict[str, Any]
    ) -> None:
        """Handle failed health check.

        Args:
            instance_id: Instance ID
            health_status: Health status dictionary
        """
        self._record_failure(instance_id)
        logger.warning(f"Health check FAIL: {instance_id}, " f"status={health_status}")

        if self._should_attempt_recovery(instance_id):
            await self._attempt_recovery(instance_id)

    def _record_success(self, instance_id: str) -> None:
        """Record successful health check.

        Args:
            instance_id: Instance ID
        """
        self._failure_counts[instance_id] = 0

        if instance_id in self._recovery_attempts:
            logger.info(f"Instance recovered: {instance_id}")
            del self._recovery_attempts[instance_id]

    def _record_failure(self, instance_id: str) -> None:
        """Record failed health check.

        Args:
            instance_id: Instance ID
        """
        current_count = self._failure_counts.get(instance_id, 0)
        self._failure_counts[instance_id] = current_count + 1

        logger.warning(
            f"Health check failure recorded: {instance_id}, "
            f"count={self._failure_counts[instance_id]}/{self.failure_threshold}"
        )

    def _should_attempt_recovery(self, instance_id: str) -> bool:
        """Check if recovery should be attempted.

        Args:
            instance_id: Instance ID

        Returns:
            True if recovery should be attempted
        """
        failure_count = self._failure_counts.get(instance_id, 0)
        if failure_count < self.failure_threshold:
            return False

        if instance_id in self._recovery_attempts:
            return self._check_recovery_backoff(instance_id)

        return True

    def _check_recovery_backoff(self, instance_id: str) -> bool:
        """Check if recovery backoff period has passed.

        Args:
            instance_id: Instance ID

        Returns:
            True if backoff period has passed
        """
        last_attempt = self._recovery_attempts[instance_id]
        last_attempt_time = last_attempt["last_attempt_time"]
        time_since_attempt = (datetime.now() - last_attempt_time).total_seconds()

        if time_since_attempt < self.recovery_backoff:
            logger.debug(
                f"Recovery backoff active: {instance_id}, "
                f"wait={self.recovery_backoff - time_since_attempt:.0f}s"
            )
            return False

        return True

    def _track_recovery_attempt(self, instance_id: str) -> None:
        """Track recovery attempt for instance.

        Args:
            instance_id: Instance ID
        """
        if instance_id not in self._recovery_attempts:
            self._recovery_attempts[instance_id] = {
                "first_attempt_time": datetime.now(),
                "attempt_count": 0,
            }

        self._recovery_attempts[instance_id]["last_attempt_time"] = datetime.now()
        self._recovery_attempts[instance_id]["attempt_count"] += 1

    async def _attempt_recovery(self, instance_id: str) -> None:
        """Attempt to recover failed orchestrator.

        Args:
            instance_id: Instance ID
        """
        logger.info(f"Attempting recovery: {instance_id}")

        try:
            self._track_recovery_attempt(instance_id)
            attempt_count = self._recovery_attempts[instance_id]["attempt_count"]
            await self.pool.reload_instance(instance_id)

            logger.info(
                f"Recovery attempt completed: {instance_id}, "
                f"attempt={attempt_count}"
            )

        except Exception as e:
            logger.error(
                f"Recovery attempt failed: {instance_id}, error={e}",
                exc_info=True,
            )

    def get_stats(self) -> Dict[str, Any]:
        """Get health monitor statistics.

        Returns:
            Dict with monitor stats
        """
        failed_instances = [
            instance_id
            for instance_id, count in self._failure_counts.items()
            if count >= self.failure_threshold
        ]

        recovering_instances = list(self._recovery_attempts.keys())

        return {
            "is_running": self._running,
            "check_interval": self.check_interval,
            "failure_threshold": self.failure_threshold,
            "recovery_backoff": self.recovery_backoff,
            "total_monitored": len(self._failure_counts),
            "failed_instances": failed_instances,
            "failed_count": len(failed_instances),
            "recovering_instances": recovering_instances,
            "recovering_count": len(recovering_instances),
        }

    def get_instance_status(self, instance_id: str) -> Dict[str, Any]:
        """Get health status for specific instance.

        Args:
            instance_id: Instance ID

        Returns:
            Dict with instance health status
        """
        failure_count = self._failure_counts.get(instance_id, 0)
        is_failed = failure_count >= self.failure_threshold
        recovery_info = self._recovery_attempts.get(instance_id)

        status = {
            "instance_id": instance_id,
            "failure_count": failure_count,
            "is_failed": is_failed,
            "is_recovering": recovery_info is not None,
        }

        if recovery_info:
            status["recovery_info"] = {
                "attempt_count": recovery_info["attempt_count"],
                "first_attempt_time": recovery_info["first_attempt_time"].isoformat(),
                "last_attempt_time": recovery_info["last_attempt_time"].isoformat(),
            }

        return status
