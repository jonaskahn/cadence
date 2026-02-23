"""Root-level pytest configuration and shared fixtures.

Adds the src/ directory to sys.path so cadence can be imported without installation.
Provides common mock factories and pytest fixtures used across all test suites.

Key exports:
    - Mock factory functions (make_org_repo, make_instance_repo, etc.)
    - Pytest fixtures for every mock dependency
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ---------------------------------------------------------------------------
# Mock repository factories
# ---------------------------------------------------------------------------


def make_mock_org(
    org_id: str = "org_test",
    name: str = "Test Org",
    status: str = "active",
) -> MagicMock:
    """Build a mock Organization ORM object.

    Args:
        org_id: Organization identifier.
        name: Organization name.
        status: Organization status.

    Returns:
        MagicMock with org_id, name, status, created_at attributes.
    """
    from datetime import datetime, timezone

    org = MagicMock()
    org.id = org_id
    org.name = name
    org.status = status
    org.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return org


def make_org_repo(
    org_data: Optional[MagicMock] = None,
    list_data: Optional[List[Any]] = None,
) -> MagicMock:
    """Build a mock OrganizationRepository with sensible defaults.

    Args:
        org_data: Override for the single-org return value (ORM mock).
        list_data: Override for get_all return value.

    Returns:
        Configured MagicMock with all async methods set up.
    """
    repo = MagicMock()
    default_org = org_data or make_mock_org()
    updated_org = make_mock_org(name="Updated Org")
    repo.create = AsyncMock(return_value=default_org)
    repo.get_by_id = AsyncMock(return_value=default_org)
    repo.get_all = AsyncMock(return_value=list_data or [default_org])
    repo.update = AsyncMock(return_value=updated_org)
    repo.update_status = AsyncMock(return_value=updated_org)
    repo.delete = AsyncMock(return_value=None)
    return repo


def make_org_settings_repo(
    settings: Optional[List[Any]] = None,
) -> MagicMock:
    """Build a mock OrganizationSettingsRepository.

    Args:
        settings: Override for get_all_for_org return value.

    Returns:
        Configured MagicMock with all async methods set up.
    """

    def _make_setting(key: str, value: Any) -> MagicMock:
        s = MagicMock()
        s.key = key
        s.value = value
        return s

    repo = MagicMock()
    default_setting = _make_setting("theme", "dark")
    default_settings = settings or [default_setting]
    repo.get_by_key = AsyncMock(return_value=default_setting)
    repo.upsert = AsyncMock(return_value=None)
    repo.get_all_for_org = AsyncMock(return_value=default_settings)
    repo.delete = AsyncMock(return_value=None)
    return repo


def make_org_llm_config_repo(
    configs: Optional[List[Dict[str, Any]]] = None,
) -> MagicMock:
    """Build a mock OrganizationLLMConfigRepository.

    Args:
        configs: Override for get_all_for_org return value.

    Returns:
        Configured MagicMock with all async methods set up.
    """
    repo = MagicMock()
    default_configs = configs or [
        {
            "id": "cfg_1",
            "org_id": "org_test",
            "name": "production",
            "provider": "openai",
            "api_key_encrypted": "sk-secret",
            "base_url": None,
            "is_active": True,
        }
    ]
    repo.create = AsyncMock(return_value=default_configs[0])
    repo.get_all_for_org = AsyncMock(return_value=list(default_configs))
    repo.delete = AsyncMock(return_value=None)
    return repo


def make_global_settings_repo(
    settings: Optional[List[Any]] = None,
) -> MagicMock:
    """Build a mock GlobalSettingsRepository.

    Args:
        settings: Override for get_all return value (ORM-like objects).

    Returns:
        Configured MagicMock with all async methods set up.
    """

    def _default_setting():
        s = MagicMock()
        s.key = "max_tokens"
        s.value = 4096
        s.value_type = "number"
        s.description = "Max tokens"
        return s

    repo = MagicMock()
    default_setting = _default_setting()
    repo.get_by_key = AsyncMock(return_value=default_setting)
    repo.get_all = AsyncMock(return_value=settings or [default_setting])
    repo.upsert = AsyncMock(return_value=None)
    repo.delete = AsyncMock(return_value=None)
    return repo


def make_instance_repo(
    instance_data: Optional[Dict[str, Any]] = None,
) -> MagicMock:
    """Build a mock OrchestratorInstanceRepository.

    Args:
        instance_data: Override for the single-instance return value.

    Returns:
        Configured MagicMock with all async methods set up.
    """
    repo = MagicMock()
    default_instance = instance_data or {
        "instance_id": "inst_test",
        "org_id": "org_test",
        "name": "Test Instance",
        "framework_type": "langgraph",
        "mode": "supervisor",
        "status": "active",
        "config": {"active_plugins": ["com.example.search"]},
        "tier": "cold",
        "plugin_settings": {"com.example.search": {}},
        "config_hash": "abc123",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "created_by": None,
        "updated_by": None,
    }
    repo.create = AsyncMock(return_value=default_instance)
    repo.get_by_id = AsyncMock(return_value=default_instance)
    repo.list_for_org = AsyncMock(return_value=[default_instance])
    repo.list_all = AsyncMock(return_value=[default_instance])
    repo.list_by_tier = AsyncMock(return_value=[default_instance])
    repo.update_config = AsyncMock(return_value=None)
    repo.update_status = AsyncMock(return_value=None)
    repo.update_plugin_settings = AsyncMock(return_value=default_instance)
    repo.delete = AsyncMock(return_value=None)
    return repo


def make_system_plugin_repo(
    plugins: Optional[List[Dict[str, Any]]] = None,
) -> MagicMock:
    """Build a mock SystemPluginRepository.

    Args:
        plugins: Override for list_all return value.

    Returns:
        Configured MagicMock with all async methods set up.
    """
    repo = MagicMock()
    default_plugin = MagicMock()
    default_plugin.id = "00000000-0000-0000-0000-000000000001"
    default_plugin.pid = "com.example.search"
    default_plugin.version = "1.0.0"
    default_plugin.name = "Search Plugin"
    default_plugin.description = "A search plugin"
    default_plugin.tag = None
    default_plugin.is_latest = True
    default_plugin.s3_path = "plugins/system/com.example.search/1.0.0/plugin.zip"
    default_plugin.default_settings = {"api_key": None}
    default_plugin.capabilities = ["search"]
    default_plugin.agent_type = "specialized"
    default_plugin.stateless = True
    default_plugin.is_active = True

    repo.upload = AsyncMock(return_value=default_plugin)
    repo.get_latest = AsyncMock(return_value=default_plugin)
    repo.get_by_version = AsyncMock(return_value=default_plugin)
    repo.get_by_id = AsyncMock(return_value=default_plugin)
    repo.list_all = AsyncMock(return_value=[default_plugin])
    repo.soft_delete = AsyncMock(return_value=True)
    return repo


def make_org_plugin_repo(
    plugins: Optional[List[Dict[str, Any]]] = None,
) -> MagicMock:
    """Build a mock OrgPluginRepository.

    Args:
        plugins: Override for list_available return value.

    Returns:
        Configured MagicMock with all async methods set up.
    """
    repo = MagicMock()
    default_plugin = MagicMock()
    default_plugin.id = "00000000-0000-0000-0000-000000000010"
    default_plugin.org_id = "org_test"
    default_plugin.pid = "com.example.custom"
    default_plugin.version = "2.0.0"
    default_plugin.name = "Custom Plugin"
    default_plugin.description = "An org-specific plugin"
    default_plugin.tag = "custom"
    default_plugin.is_latest = True
    default_plugin.s3_path = (
        "plugins/tenants/org_test/com.example.custom/2.0.0/plugin.zip"
    )
    default_plugin.default_settings = {"endpoint": None}
    default_plugin.capabilities = []
    default_plugin.agent_type = "specialized"
    default_plugin.stateless = True
    default_plugin.is_active = True

    repo.upload = AsyncMock(return_value=default_plugin)
    repo.get_latest = AsyncMock(return_value=None)
    repo.get_by_version = AsyncMock(return_value=default_plugin)
    repo.get_by_id = AsyncMock(return_value=default_plugin)
    repo.list_available = AsyncMock(return_value=[default_plugin])
    repo.soft_delete = AsyncMock(return_value=True)
    return repo


def make_conversation_store(
    messages: Optional[List[Any]] = None,
) -> MagicMock:
    """Build a mock MongoDB ConversationStore.

    Args:
        messages: Override for get_messages return value.

    Returns:
        Configured MagicMock with all async methods set up.
    """
    store = MagicMock()
    store.get_messages = AsyncMock(return_value=messages or [])
    store.save_message = AsyncMock(return_value=None)
    store.delete_conversation = AsyncMock(return_value=None)
    return store


def make_conversation_repo(
    conversations: Optional[List[Dict[str, Any]]] = None,
) -> MagicMock:
    """Build a mock PostgreSQL ConversationRepository.

    Args:
        conversations: Override for list_for_user return value.

    Returns:
        Configured MagicMock with all async methods set up.
    """
    repo = MagicMock()
    default_conversations = conversations or [
        {"conversation_id": "conv_test", "org_id": "org_test", "user_id": "user_test"}
    ]
    repo.create = AsyncMock(return_value=None)
    repo.list_for_user = AsyncMock(return_value=default_conversations)
    repo.delete = AsyncMock(return_value=None)
    return repo


def make_redis_pubsub() -> MagicMock:
    """Build a mock RedisPubSub with publish support.

    Returns:
        Configured MagicMock with publish async method.
    """
    pubsub = MagicMock()
    pubsub.publish = AsyncMock(return_value=None)
    return pubsub


def make_orchestrator_pool(instance: Optional[MagicMock] = None) -> MagicMock:
    """Build a mock OrchestratorPool with full lifecycle support.

    Args:
        instance: Override for the orchestrator returned by pool.get().

    Returns:
        Configured MagicMock with all async methods set up.
    """
    pool = MagicMock()
    default_instance = instance or make_mock_orchestrator()
    pool.get = AsyncMock(return_value=default_instance)
    pool.create_instance = AsyncMock(return_value=default_instance)
    pool.reload_instance = AsyncMock(return_value=None)
    pool.remove_instance = AsyncMock(return_value=None)
    pool.list_all = AsyncMock(return_value=["inst_test"])
    pool.health_check_all = AsyncMock(return_value={"inst_test": {"status": "healthy"}})
    pool.get_stats = MagicMock(
        return_value={
            "total_instances": 1,
            "instance_ids": ["inst_test"],
            "tier": "hot",
        }
    )
    return pool


def make_mock_orchestrator(
    framework: str = "langgraph",
    mode: str = "supervisor",
) -> MagicMock:
    """Build a mock BaseOrchestrator that returns a single AI message.

    Args:
        framework: Framework type to report (e.g. 'langgraph').
        mode: Orchestration mode to report (e.g. 'supervisor').

    Returns:
        Configured MagicMock implementing the BaseOrchestrator interface.
    """
    from cadence_sdk.types.sdk_messages import UvAIMessage

    orchestrator = MagicMock()
    orchestrator.framework_type = framework
    orchestrator.mode = mode
    orchestrator.is_ready = True
    orchestrator.plugin_pids = []

    final_state = {
        "messages": [UvAIMessage(content="Hello from AI")],
        "agent_hops": 1,
        "current_agent": "agent_a",
    }
    orchestrator.ask = AsyncMock(return_value=final_state)
    orchestrator.cleanup = AsyncMock(return_value=None)
    orchestrator.health_check = AsyncMock(
        return_value={"status": "healthy", "framework": framework, "mode": mode}
    )
    orchestrator.rebuild = AsyncMock(return_value=None)
    return orchestrator


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def org_repo() -> MagicMock:
    """Provide a mock OrganizationRepository."""
    return make_org_repo()


@pytest.fixture
def org_settings_repo() -> MagicMock:
    """Provide a mock OrganizationSettingsRepository."""
    return make_org_settings_repo()


@pytest.fixture
def org_llm_config_repo() -> MagicMock:
    """Provide a mock OrganizationLLMConfigRepository."""
    return make_org_llm_config_repo()


@pytest.fixture
def global_settings_repo() -> MagicMock:
    """Provide a mock GlobalSettingsRepository."""
    return make_global_settings_repo()


@pytest.fixture
def instance_repo() -> MagicMock:
    """Provide a mock OrchestratorInstanceRepository."""
    return make_instance_repo()


@pytest.fixture
def conversation_store() -> MagicMock:
    """Provide a mock MongoDB ConversationStore."""
    return make_conversation_store()


@pytest.fixture
def conversation_repo() -> MagicMock:
    """Provide a mock PostgreSQL ConversationRepository."""
    return make_conversation_repo()


@pytest.fixture
def redis_pubsub() -> MagicMock:
    """Provide a mock RedisPubSub."""
    return make_redis_pubsub()


@pytest.fixture
def mock_orchestrator() -> MagicMock:
    """Provide a mock BaseOrchestrator (langgraph/supervisor)."""
    return make_mock_orchestrator()


@pytest.fixture
def orchestrator_pool(mock_orchestrator: MagicMock) -> MagicMock:
    """Provide a mock OrchestratorPool pre-loaded with one orchestrator."""
    return make_orchestrator_pool(mock_orchestrator)


@pytest.fixture
def system_plugin_repo() -> MagicMock:
    """Provide a mock SystemPluginRepository."""
    return make_system_plugin_repo()


@pytest.fixture
def org_plugin_catalog_repo() -> MagicMock:
    """Provide a mock OrgPluginRepository."""
    return make_org_plugin_repo()
