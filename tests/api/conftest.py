"""Shared fixtures for API (controller) tests.

Builds a minimal FastAPI test application with all services injected via
app.state. Permission dependencies are overridden so tests focus on
controller routing and response shaping, not auth mechanics.

Key exports:
    - sys_admin_context / org_admin_context: pre-built TenantContext fixtures
    - mock_tenant_service / mock_settings_service / mock_orchestrator_service
    - mock_pool, mock_postgres_repo, mock_redis_client, mock_mongo_client
    - app: FastAPI instance with all routers mounted and mocks injected
    - client: synchronous httpx TestClient using sys_admin context
    - org_admin_client: TestClient using org_admin context
"""

import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

TEST_ORG_ID = "org_test"
TEST_USER_ID = "user_test"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sys_admin_context() -> Any:
    """Build a sys_admin TenantContext for tests.

    Returns:
        TenantContext with is_sys_admin=True
    """
    from cadence.middleware.tenant_context_middleware import TenantContext

    return TenantContext(
        org_id=TEST_ORG_ID,
        user_id=TEST_USER_ID,
        is_sys_admin=True,
        is_org_admin=True,
    )


def _make_org_admin_context() -> Any:
    """Build an org_admin TenantContext for tests.

    Returns:
        TenantContext with is_org_admin=True and is_sys_admin=False
    """
    from cadence.middleware.tenant_context_middleware import TenantContext

    return TenantContext(
        org_id=TEST_ORG_ID,
        user_id=TEST_USER_ID,
        is_sys_admin=False,
        is_org_admin=True,
    )


def _make_test_app(
    mock_tenant_service: MagicMock,
    mock_settings_service: MagicMock,
    mock_orchestrator_service: MagicMock,
    mock_pool: MagicMock,
    mock_postgres_repo: MagicMock,
    mock_redis_client: MagicMock,
    mock_mongo_client: MagicMock,
    mock_system_plugin_repo: MagicMock,
    mock_org_plugin_repo: MagicMock,
    mock_plugin_service: MagicMock,
    mock_instance_repo: MagicMock,
    context: Any,
) -> FastAPI:
    """Build a minimal FastAPI app with mocked state and overridden permissions.

    Args:
        mock_tenant_service: Mocked TenantService.
        mock_settings_service: Mocked SettingsService.
        mock_orchestrator_service: Mocked OrchestratorService.
        mock_pool: Mocked OrchestratorPool.
        mock_postgres_repo: Mocked PostgreSQL repository.
        mock_redis_client: Mocked Redis client.
        mock_mongo_client: Mocked MongoDB client.
        mock_system_plugin_repo: Mocked SystemPluginRepository.
        mock_org_plugin_repo: Mocked OrgPluginRepository.
        mock_plugin_service: Mocked PluginService.
        mock_instance_repo: Mocked OrchestratorInstanceRepository.
        context: TenantContext to inject via all permission dependency overrides.

    Returns:
        Configured FastAPI test application.
    """
    import cadence.middleware.authorization_middleware as perms
    from cadence.controller import (
        admin_controller,
        auth_controller,
        chat_controller,
        health_controller,
        orchestrator_controller,
        tenant_controller,
    )

    _app = FastAPI()

    _app.state.tenant_service = mock_tenant_service
    _app.state.settings_service = mock_settings_service
    _app.state.orchestrator_service = mock_orchestrator_service
    _app.state.pool = mock_pool
    _app.state.orchestrator_pool = mock_pool
    _app.state.postgres_repo = mock_postgres_repo
    _app.state.redis_client = mock_redis_client
    _app.state.mongo_client = mock_mongo_client
    _app.state.system_plugin_repo = mock_system_plugin_repo
    _app.state.org_plugin_repo = mock_org_plugin_repo
    _app.state.plugin_service = mock_plugin_service
    _app.state.instance_repo = mock_instance_repo
    _app.state.auth_service = MagicMock()

    def _ctx():
        return context

    _app.dependency_overrides[perms.require_sys_admin] = _ctx
    _app.dependency_overrides[perms.require_org_admin_access] = _ctx
    _app.dependency_overrides[perms.require_org_member] = _ctx
    _app.dependency_overrides[perms.require_authenticated] = _ctx

    _app.include_router(health_controller.router)
    _app.include_router(auth_controller.router)
    _app.include_router(chat_controller.router)
    _app.include_router(tenant_controller.router)
    _app.include_router(orchestrator_controller.router)
    _app.include_router(admin_controller.router)

    return _app


# ---------------------------------------------------------------------------
# Fixtures — contexts
# ---------------------------------------------------------------------------


@pytest.fixture
def sys_admin_context() -> Any:
    """TenantContext with sys_admin rights."""
    return _make_sys_admin_context()


@pytest.fixture
def org_admin_context() -> Any:
    """TenantContext with org_admin rights (no sys_admin)."""
    return _make_org_admin_context()


# Backward-compat alias used in existing tests that referenced `tenant_context`
@pytest.fixture
def tenant_context() -> Any:
    """Default (sys_admin) TenantContext for backward compatibility."""
    return _make_sys_admin_context()


# ---------------------------------------------------------------------------
# Fixtures — services / repos
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_tenant_service() -> MagicMock:
    """Mock TenantService with all public methods as AsyncMocks."""
    svc = MagicMock()
    svc.create_org = AsyncMock(
        return_value={
            "org_id": TEST_ORG_ID,
            "name": "Test Org",
            "status": "active",
            "created_at": "2026-01-01T00:00:00Z",
        }
    )
    svc.list_orgs = AsyncMock(return_value=[])
    svc.update_org = AsyncMock(
        return_value={
            "org_id": TEST_ORG_ID,
            "name": "Updated Org",
            "status": "active",
            "created_at": "2026-01-01T00:00:00Z",
        }
    )
    svc.get_org = AsyncMock(
        return_value={
            "org_id": TEST_ORG_ID,
            "name": "Test Org",
            "status": "active",
            "created_at": "2026-01-01T00:00:00Z",
        }
    )
    svc.get_setting = AsyncMock(return_value="dark")
    svc.set_setting = AsyncMock(
        return_value={"key": "theme", "value": "dark", "value_type": "string"}
    )
    svc.list_settings = AsyncMock(
        return_value=[{"key": "theme", "value": "dark", "value_type": "string"}]
    )
    _llm_cfg = MagicMock()
    _llm_cfg.id = 1
    _llm_cfg.name = "production"
    _llm_cfg.provider = "openai"
    _llm_cfg.base_url = None
    _llm_cfg.additional_config = {}
    _llm_cfg.created_at.isoformat.return_value = "2026-01-01T00:00:00Z"
    svc.add_llm_config = AsyncMock(return_value=_llm_cfg)
    svc.list_llm_configs = AsyncMock(return_value=[])
    svc.delete_llm_config = AsyncMock(return_value=True)

    _default_user = {
        "user_id": "user_1",
        "username": "testuser",
        "email": "test@example.com",
        "is_sys_admin": False,
        "is_admin": False,
        "is_deleted": False,
        "created_at": "2026-01-01T00:00:00Z",
    }
    svc.create_user = AsyncMock(return_value=_default_user)
    svc.list_org_members = AsyncMock(return_value=[_default_user])
    svc.list_all_users = AsyncMock(return_value=[_default_user])
    svc.search_user = AsyncMock(return_value=_default_user)
    svc.update_user = AsyncMock(return_value=_default_user)
    svc.add_user_to_org = AsyncMock(
        return_value={"user_id": "user_1", "org_id": TEST_ORG_ID, "is_admin": False}
    )
    svc.add_existing_user_to_org = AsyncMock(return_value=_default_user)
    svc.get_org_member = AsyncMock(return_value=_default_user)
    svc.update_org_membership = AsyncMock(
        return_value={"user_id": "user_1", "org_id": TEST_ORG_ID, "is_admin": True}
    )
    svc.remove_user_from_org = AsyncMock(return_value=True)
    svc.delete_user = AsyncMock(return_value=True)
    svc.user_repo = MagicMock()
    svc.user_repo.get_by_id = AsyncMock(
        return_value=MagicMock(
            user_id="user_1",
            username="testuser",
            email="test@example.com",
            is_sys_admin=False,
            deleted=False,
            created_at=MagicMock(
                isoformat=MagicMock(return_value="2026-01-01T00:00:00Z")
            ),
        )
    )
    svc._serialize_user = MagicMock(return_value=_default_user)
    svc.serialize_user = MagicMock(return_value=_default_user)
    svc.list_orgs_for_user = AsyncMock(return_value=[])
    return svc


@pytest.fixture
def mock_settings_service() -> MagicMock:
    """Mock SettingsService with all public methods as AsyncMocks."""
    svc = MagicMock()
    svc.list_global_settings = AsyncMock(return_value=[])
    svc.update_global_setting = AsyncMock(
        return_value={
            "key": "k",
            "value": "v",
            "value_type": "str",
            "description": "test",
        }
    )
    _default_instance = {
        "instance_id": "inst_test",
        "org_id": TEST_ORG_ID,
        "name": "My Bot",
        "framework_type": "langgraph",
        "mode": "supervisor",
        "status": "active",
        "config": {},
        "tier": "cold",
        "plugin_settings": {},
        "config_hash": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    svc.create_instance = AsyncMock(return_value=_default_instance)
    svc.create_orchestrator_instance = AsyncMock(return_value=_default_instance)
    svc.list_instances_for_org = AsyncMock(return_value=[])
    svc.get_instance_config = AsyncMock(return_value=_default_instance)
    svc.update_instance_config = AsyncMock(
        return_value={
            **_default_instance,
            "config": {"temperature": 0.8},
            "updated_at": "2026-01-02T00:00:00Z",
        }
    )
    svc.update_orchestrator_config = AsyncMock(
        return_value={
            **_default_instance,
            "config": {"temperature": 0.8},
            "updated_at": "2026-01-02T00:00:00Z",
        }
    )
    svc.update_orchestrator_plugin_settings = AsyncMock(return_value=_default_instance)
    svc.sync_orchestrator_plugin_settings = AsyncMock(return_value=_default_instance)
    svc.update_instance_plugin_settings = AsyncMock(return_value=_default_instance)
    svc.update_instance_status = AsyncMock(
        return_value={**_default_instance, "status": "suspended"}
    )
    svc.delete_instance = AsyncMock(return_value=None)
    return svc


@pytest.fixture
def mock_orchestrator_service() -> MagicMock:
    """Mock OrchestratorService with process_chat wired to AsyncMock."""
    svc = MagicMock()
    svc.process_chat = AsyncMock(
        return_value={
            "conversation_id": "conv_test",
            "response": "Hello from AI",
            "messages": [],
            "metadata": {"agent_hops": 1, "current_agent": "agent_a"},
        }
    )
    svc.get_instance_org_id = AsyncMock(return_value=TEST_ORG_ID)
    return svc


@pytest.fixture
def mock_pool() -> MagicMock:
    """Mock OrchestratorPool with health_check_all and get_stats."""
    pool = MagicMock()
    pool.health_check_all = AsyncMock(
        return_value={
            "inst_test": {
                "framework_type": "langgraph",
                "mode": "supervisor",
                "is_ready": True,
                "plugin_count": 0,
                "plugins": [],
            }
        }
    )
    pool.get_stats = MagicMock(
        return_value={
            "total_instances": 1,
            "hot_tier_count": 1,
            "warm_tier_count": 0,
            "cold_tier_count": 0,
            "shared_model_count": 0,
            "shared_bundle_count": 0,
            "memory_estimate_mb": 64.0,
        }
    )
    return pool


@pytest.fixture
def mock_postgres_repo() -> MagicMock:
    """Mock PostgreSQL repository with async health_check."""
    repo = MagicMock()
    repo.health_check = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_redis_client() -> MagicMock:
    """Mock Redis client whose get_client().ping() is awaitable."""
    client = MagicMock()
    inner = MagicMock()
    inner.ping = AsyncMock(return_value=True)
    client.get_client = MagicMock(return_value=inner)
    return client


@pytest.fixture
def mock_mongo_client() -> MagicMock:
    """Mock MongoDB client with async admin.command."""
    client = MagicMock()
    inner_client = MagicMock()
    admin = MagicMock()
    admin.command = AsyncMock(return_value={"ok": 1})
    inner_client.admin = admin
    client.client = inner_client
    return client


@pytest.fixture
def mock_system_plugin_repo() -> MagicMock:
    """Mock SystemPluginRepository."""
    repo = MagicMock()
    repo.get_latest = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_org_plugin_repo() -> MagicMock:
    """Mock OrgPluginRepository."""
    repo = MagicMock()
    repo.get_latest = AsyncMock(return_value=None)
    repo.soft_delete = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def mock_plugin_service() -> MagicMock:
    """Mock PluginService."""
    svc = MagicMock()
    svc.build_initial_plugin_settings = MagicMock(return_value={})
    svc.list_available = AsyncMock(return_value=[])
    svc.resolve_plugin_rows = AsyncMock(return_value=([], []))
    svc.delete_org_plugin = AsyncMock(return_value=True)
    return svc


@pytest.fixture
def mock_instance_repo() -> MagicMock:
    """Mock OrchestratorInstanceRepository."""
    repo = MagicMock()
    repo.update_plugin_settings = AsyncMock(
        return_value={
            "instance_id": "inst_test",
            "org_id": TEST_ORG_ID,
            "name": "My Bot",
            "framework_type": "langgraph",
            "mode": "supervisor",
            "status": "active",
            "config": {},
            "tier": "cold",
            "plugin_settings": {},
            "config_hash": None,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
    )
    return repo


# ---------------------------------------------------------------------------
# Fixtures — apps and clients
# ---------------------------------------------------------------------------


@pytest.fixture
def app(
    mock_tenant_service: MagicMock,
    mock_settings_service: MagicMock,
    mock_orchestrator_service: MagicMock,
    mock_pool: MagicMock,
    mock_postgres_repo: MagicMock,
    mock_redis_client: MagicMock,
    mock_mongo_client: MagicMock,
    mock_system_plugin_repo: MagicMock,
    mock_org_plugin_repo: MagicMock,
    mock_plugin_service: MagicMock,
    mock_instance_repo: MagicMock,
    tenant_context: Any,
) -> FastAPI:
    """FastAPI test app with sys_admin context and all routers mounted."""
    return _make_test_app(
        mock_tenant_service=mock_tenant_service,
        mock_settings_service=mock_settings_service,
        mock_orchestrator_service=mock_orchestrator_service,
        mock_pool=mock_pool,
        mock_postgres_repo=mock_postgres_repo,
        mock_redis_client=mock_redis_client,
        mock_mongo_client=mock_mongo_client,
        mock_system_plugin_repo=mock_system_plugin_repo,
        mock_org_plugin_repo=mock_org_plugin_repo,
        mock_plugin_service=mock_plugin_service,
        mock_instance_repo=mock_instance_repo,
        context=tenant_context,
    )


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Synchronous TestClient for the sys_admin test app."""
    return TestClient(app)


@pytest.fixture
def org_admin_client(
    mock_tenant_service: MagicMock,
    mock_settings_service: MagicMock,
    mock_orchestrator_service: MagicMock,
    mock_pool: MagicMock,
    mock_postgres_repo: MagicMock,
    mock_redis_client: MagicMock,
    mock_mongo_client: MagicMock,
    mock_system_plugin_repo: MagicMock,
    mock_org_plugin_repo: MagicMock,
    mock_plugin_service: MagicMock,
    mock_instance_repo: MagicMock,
    org_admin_context: Any,
) -> TestClient:
    """TestClient whose tenant context has is_org_admin=True, is_sys_admin=False."""
    _app = _make_test_app(
        mock_tenant_service=mock_tenant_service,
        mock_settings_service=mock_settings_service,
        mock_orchestrator_service=mock_orchestrator_service,
        mock_pool=mock_pool,
        mock_postgres_repo=mock_postgres_repo,
        mock_redis_client=mock_redis_client,
        mock_mongo_client=mock_mongo_client,
        mock_system_plugin_repo=mock_system_plugin_repo,
        mock_org_plugin_repo=mock_org_plugin_repo,
        mock_plugin_service=mock_plugin_service,
        mock_instance_repo=mock_instance_repo,
        context=org_admin_context,
    )
    return TestClient(_app)
