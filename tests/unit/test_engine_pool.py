"""Unit tests for OrchestratorPool.

Verifies instance lifecycle management: creation, retrieval, hot-reload
(atomic swap with failure safety), removal, health checks, and statistics.
Also verifies per-instance lock creation and concurrency safety.
Covers DB fallback in get() for instances not yet loaded into the pool.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from cadence.engine.pool import OrchestratorPool

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_factory() -> MagicMock:
    """Provide a mock OrchestratorFactory with an async create method."""
    factory = MagicMock()
    factory.create = AsyncMock()
    return factory


@pytest.fixture
def pool(mock_factory: MagicMock) -> OrchestratorPool:
    """Provide an empty OrchestratorPool backed by a mock factory."""
    return OrchestratorPool(
        factory=mock_factory,
        db_repositories={},
    )


@pytest.fixture
def pool_with_instance(
    pool: OrchestratorPool,
    mock_orchestrator: MagicMock,
    mock_factory: MagicMock,
) -> OrchestratorPool:
    """Provide an OrchestratorPool pre-populated with one orchestrator instance."""
    pool.instances["inst_test"] = mock_orchestrator
    pool.locks["inst_test"] = asyncio.Lock()
    mock_factory.create.return_value = mock_orchestrator
    return pool


# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------


class TestGet:
    """Tests for OrchestratorPool.get."""

    async def test_returns_registered_instance(
        self, pool_with_instance: OrchestratorPool, mock_orchestrator: MagicMock
    ) -> None:
        """get returns the orchestrator that was previously registered under the given ID."""
        result = await pool_with_instance.get("inst_test")

        assert result is mock_orchestrator

    async def test_raises_when_not_in_pool_and_no_repo_configured(
        self, pool: OrchestratorPool
    ) -> None:
        """get raises ValueError when instance is not in pool and db_repositories is empty."""
        with pytest.raises(ValueError, match="not found in pool"):
            await pool.get("unknown_inst")

    async def test_loads_from_db_when_not_in_pool(
        self,
        pool: OrchestratorPool,
        mock_factory: MagicMock,
        mock_orchestrator: MagicMock,
    ) -> None:
        """get falls back to DB load and returns the orchestrator when found in DB."""
        instance_repo = MagicMock()
        instance_repo.get_by_id = AsyncMock(
            return_value={
                "framework_type": "langgraph",
                "mode": "supervisor",
                "org_id": "org_test",
                "config": {"active_plugins": []},
            }
        )
        mock_factory.create.return_value = mock_orchestrator
        pool.db_repositories = {
            "orchestrator_instance_repo": instance_repo,
        }

        result = await pool.get("550e8400-e29b-41d4-a716-446655440000")

        assert result is mock_orchestrator

    async def test_db_fallback_registers_instance_in_pool(
        self,
        pool: OrchestratorPool,
        mock_factory: MagicMock,
        mock_orchestrator: MagicMock,
    ) -> None:
        """After a DB fallback load, the instance is stored in the pool for subsequent gets."""
        instance_repo = MagicMock()
        instance_repo.get_by_id = AsyncMock(
            return_value={
                "framework_type": "langgraph",
                "mode": "supervisor",
                "org_id": "org_test",
                "config": {},
            }
        )
        mock_factory.create.return_value = mock_orchestrator
        pool.db_repositories = {
            "orchestrator_instance_repo": instance_repo,
        }

        await pool.get("550e8400-e29b-41d4-a716-446655440000")

        assert "550e8400-e29b-41d4-a716-446655440000" in pool.instances

    async def test_raises_when_not_in_pool_and_not_in_db(
        self,
        pool: OrchestratorPool,
    ) -> None:
        """get raises ValueError when instance is not in pool or database."""
        instance_repo = MagicMock()
        instance_repo.get_by_id = AsyncMock(return_value=None)
        pool.db_repositories = {
            "orchestrator_instance_repo": instance_repo,
        }

        with pytest.raises(ValueError, match="not found in pool or database"):
            await pool.get("nonexistent_inst")


# ---------------------------------------------------------------------------
# create_instance()
# ---------------------------------------------------------------------------


class TestCreateInstance:
    """Tests for OrchestratorPool.create_instance."""

    async def test_registers_new_instance_in_pool(
        self,
        pool: OrchestratorPool,
        mock_factory: MagicMock,
        mock_orchestrator: MagicMock,
    ) -> None:
        """create_instance stores the orchestrator in the pool registry."""
        mock_factory.create.return_value = mock_orchestrator

        await pool.create_instance(
            instance_id="inst_new",
            org_id="org_test",
            framework_type="langgraph",
            mode="supervisor",
            instance_config={"active_plugins": []},
            resolved_config={},
        )

        assert "inst_new" in pool.instances

    async def test_returns_created_orchestrator(
        self,
        pool: OrchestratorPool,
        mock_factory: MagicMock,
        mock_orchestrator: MagicMock,
    ) -> None:
        """create_instance returns the orchestrator produced by the factory."""
        mock_factory.create.return_value = mock_orchestrator

        result = await pool.create_instance(
            instance_id="inst_new",
            org_id="org_test",
            framework_type="langgraph",
            mode="supervisor",
            instance_config={},
            resolved_config={},
        )

        assert result is mock_orchestrator

    async def test_calls_factory_with_correct_arguments(
        self,
        pool: OrchestratorPool,
        mock_factory: MagicMock,
        mock_orchestrator: MagicMock,
    ) -> None:
        """create_instance forwards all parameters to the factory."""
        mock_factory.create.return_value = mock_orchestrator

        await pool.create_instance(
            instance_id="inst_new",
            org_id="org_test",
            framework_type="langgraph",
            mode="coordinator",
            instance_config={"key": "val"},
            resolved_config={"resolved": True},
        )

        mock_factory.create.assert_awaited_once_with(
            framework_type="langgraph",
            mode="coordinator",
            org_id="org_test",
            instance_config={"key": "val"},
            resolved_config={"resolved": True},
        )

    async def test_raises_when_instance_id_already_registered(
        self, pool_with_instance: OrchestratorPool
    ) -> None:
        """create_instance raises ValueError when an instance with the same ID already exists."""
        with pytest.raises(ValueError, match="already exists"):
            await pool_with_instance.create_instance(
                instance_id="inst_test",
                org_id="org_test",
                framework_type="langgraph",
                mode="supervisor",
                instance_config={},
                resolved_config={},
            )

    async def test_creates_asyncio_lock_for_new_instance(
        self,
        pool: OrchestratorPool,
        mock_factory: MagicMock,
        mock_orchestrator: MagicMock,
    ) -> None:
        """create_instance allocates an asyncio.Lock for the new instance."""
        mock_factory.create.return_value = mock_orchestrator

        await pool.create_instance(
            "inst_new", "org_test", "langgraph", "supervisor", {}, {}
        )

        assert "inst_new" in pool.locks
        assert isinstance(pool.locks["inst_new"], asyncio.Lock)


# ---------------------------------------------------------------------------
# reload_instance()
# ---------------------------------------------------------------------------


class TestReloadInstance:
    """Tests for OrchestratorPool.reload_instance."""

    async def test_replaces_orchestrator_with_new_instance(
        self,
        pool_with_instance: OrchestratorPool,
        mock_factory: MagicMock,
    ) -> None:
        """reload_instance swaps out the old orchestrator for the newly created one."""
        new_orchestrator = MagicMock()
        new_orchestrator.cleanup = AsyncMock()
        mock_factory.create.return_value = new_orchestrator

        await pool_with_instance.reload_instance(
            instance_id="inst_test",
            org_id="org_test",
            framework_type="langgraph",
            mode="supervisor",
            instance_config={},
            resolved_config={},
        )

        assert pool_with_instance.instances["inst_test"] is new_orchestrator

    async def test_cleans_up_old_orchestrator_during_swap(
        self,
        pool_with_instance: OrchestratorPool,
        mock_factory: MagicMock,
        mock_orchestrator: MagicMock,
    ) -> None:
        """reload_instance calls cleanup on the outgoing orchestrator."""
        new_orchestrator = MagicMock()
        new_orchestrator.cleanup = AsyncMock()
        mock_factory.create.return_value = new_orchestrator

        await pool_with_instance.reload_instance(
            "inst_test", "org_test", "langgraph", "supervisor", {}, {}
        )

        mock_orchestrator.cleanup.assert_awaited_once()

    async def test_raises_when_instance_not_registered(
        self, pool: OrchestratorPool
    ) -> None:
        """reload_instance raises ValueError when the instance ID is not in the pool."""
        with pytest.raises(ValueError, match="not found"):
            await pool.reload_instance(
                "missing_inst", "org", "langgraph", "supervisor", {}, {}
            )

    async def test_preserves_old_instance_when_factory_fails(
        self,
        pool_with_instance: OrchestratorPool,
        mock_factory: MagicMock,
        mock_orchestrator: MagicMock,
    ) -> None:
        """reload_instance keeps the existing orchestrator when the factory raises."""
        mock_factory.create.side_effect = RuntimeError("factory broke")

        with pytest.raises(RuntimeError):
            await pool_with_instance.reload_instance(
                "inst_test", "org", "langgraph", "supervisor", {}, {}
            )

        assert pool_with_instance.instances["inst_test"] is mock_orchestrator


# ---------------------------------------------------------------------------
# remove_instance()
# ---------------------------------------------------------------------------


class TestRemoveInstance:
    """Tests for OrchestratorPool.remove_instance."""

    async def test_removes_instance_from_registry(
        self, pool_with_instance: OrchestratorPool
    ) -> None:
        """remove_instance deregisters the orchestrator from the pool."""
        await pool_with_instance.remove_instance("inst_test")

        assert "inst_test" not in pool_with_instance.instances

    async def test_cleans_up_orchestrator_on_removal(
        self,
        pool_with_instance: OrchestratorPool,
        mock_orchestrator: MagicMock,
    ) -> None:
        """remove_instance calls cleanup on the orchestrator before deregistering."""
        await pool_with_instance.remove_instance("inst_test")

        mock_orchestrator.cleanup.assert_awaited_once()

    async def test_removes_associated_lock(
        self, pool_with_instance: OrchestratorPool
    ) -> None:
        """remove_instance also removes the asyncio.Lock for the instance."""
        await pool_with_instance.remove_instance("inst_test")

        assert "inst_test" not in pool_with_instance.locks

    async def test_raises_when_instance_not_registered(
        self, pool: OrchestratorPool
    ) -> None:
        """remove_instance raises ValueError when the instance ID is not in the pool."""
        with pytest.raises(ValueError, match="not found"):
            await pool.remove_instance("missing_inst")


# ---------------------------------------------------------------------------
# list_all()
# ---------------------------------------------------------------------------


class TestListAll:
    """Tests for OrchestratorPool.list_all."""

    async def test_returns_id_of_registered_instance(
        self, pool_with_instance: OrchestratorPool
    ) -> None:
        """list_all includes the ID of every instance currently in the pool."""
        result = await pool_with_instance.list_all()

        assert "inst_test" in result

    async def test_returns_empty_list_for_empty_pool(
        self, pool: OrchestratorPool
    ) -> None:
        """list_all returns an empty list when no instances are registered."""
        result = await pool.list_all()

        assert result == []

    async def test_returns_all_registered_instance_ids(
        self, pool: OrchestratorPool
    ) -> None:
        """list_all returns every registered instance ID."""
        pool.instances["inst_a"] = MagicMock()
        pool.instances["inst_b"] = MagicMock()

        result = await pool.list_all()

        assert set(result) == {"inst_a", "inst_b"}


# ---------------------------------------------------------------------------
# health_check_all()
# ---------------------------------------------------------------------------


class TestHealthCheckAll:
    """Tests for OrchestratorPool.health_check_all."""

    async def test_reports_healthy_status_for_passing_checks(
        self,
        pool_with_instance: OrchestratorPool,
        mock_orchestrator: MagicMock,
    ) -> None:
        """health_check_all marks instances as 'healthy' when health_check succeeds."""
        mock_orchestrator.health_check.return_value = {"status": "ok"}

        result = await pool_with_instance.health_check_all()

        assert result["inst_test"]["status"] == "healthy"

    async def test_reports_unhealthy_status_when_health_check_raises(
        self,
        pool_with_instance: OrchestratorPool,
        mock_orchestrator: MagicMock,
    ) -> None:
        """health_check_all marks an instance as 'unhealthy' when health_check raises."""
        mock_orchestrator.health_check.side_effect = RuntimeError("health check failed")

        result = await pool_with_instance.health_check_all()

        assert result["inst_test"]["status"] == "unhealthy"
        assert "error" in result["inst_test"]

    async def test_returns_empty_dict_for_empty_pool(
        self, pool: OrchestratorPool
    ) -> None:
        """health_check_all returns an empty dict when no instances are registered."""
        result = await pool.health_check_all()

        assert result == {}

    async def test_checks_every_registered_instance(
        self, pool: OrchestratorPool
    ) -> None:
        """health_check_all runs a health check for each registered instance."""
        instance_a = MagicMock()
        instance_a.health_check = AsyncMock(return_value={"status": "ok"})
        instance_b = MagicMock()
        instance_b.health_check = AsyncMock(return_value={"status": "ok"})
        pool.instances = {"a": instance_a, "b": instance_b}

        result = await pool.health_check_all()

        assert len(result) == 2
        assert result["a"]["status"] == "healthy"
        assert result["b"]["status"] == "healthy"


# ---------------------------------------------------------------------------
# get_stats()
# ---------------------------------------------------------------------------


class TestGetStats:
    """Tests for OrchestratorPool.get_stats."""

    def test_total_instances_reflects_pool_size(
        self, pool_with_instance: OrchestratorPool
    ) -> None:
        """get_stats reports the correct total number of registered instances."""
        stats = pool_with_instance.get_stats()

        assert stats["total_instances"] == 1

    def test_instance_ids_list_contains_registered_ids(
        self, pool_with_instance: OrchestratorPool
    ) -> None:
        """get_stats includes each registered instance ID in the instance_ids list."""
        stats = pool_with_instance.get_stats()

        assert "inst_test" in stats["instance_ids"]

    def test_tier_is_hot(self, pool_with_instance: OrchestratorPool) -> None:
        """get_stats reports 'hot' as the current tier (MVP single-tier pool)."""
        stats = pool_with_instance.get_stats()

        assert stats["tier"] == "hot"

    def test_reports_zero_instances_for_empty_pool(
        self, pool: OrchestratorPool
    ) -> None:
        """get_stats reports zero total instances when no orchestrators are registered."""
        stats = pool.get_stats()

        assert stats["total_instances"] == 0
        assert stats["instance_ids"] == []
