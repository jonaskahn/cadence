"""Application startup, lifecycle, and initialization helpers."""

import logging
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI

from cadence.config.app_settings import AppSettings
from cadence.engine.factory import OrchestratorFactory
from cadence.engine.pool import OrchestratorPool
from cadence.infrastructure.llm.factory import LLMModelFactory
from cadence.infrastructure.messaging.orchestrator_events import (
    OrchestratorEventConsumer,
    OrchestratorEventPublisher,
)
from cadence.infrastructure.messaging.rabbitmq_client import RabbitMQClient
from cadence.infrastructure.persistence.mongodb.client import MongoDBClient
from cadence.infrastructure.persistence.postgresql.client import PostgreSQLClient
from cadence.infrastructure.persistence.redis.cache import RedisCache
from cadence.infrastructure.persistence.redis.client import RedisClient
from cadence.infrastructure.persistence.s3.client import S3Client
from cadence.repository.conversation_repository import ConversationRepository
from cadence.repository.global_settings_repository import GlobalSettingsRepository
from cadence.repository.message_repository import MessageRepository
from cadence.repository.orchestrator_instance_repository import (
    OrchestratorInstanceRepository,
)
from cadence.repository.org_plugin_repository import OrgPluginRepository
from cadence.repository.organization_llm_config_repository import (
    OrganizationLLMConfigRepository,
)
from cadence.repository.organization_repository import OrganizationRepository
from cadence.repository.organization_settings_repository import (
    OrganizationSettingsRepository,
)
from cadence.repository.plugin_store_repository import PluginStoreRepository
from cadence.repository.provider_model_config_repository import (
    ProviderModelConfigRepository,
)
from cadence.repository.session_store_repository import SessionStoreRepository
from cadence.repository.system_plugin_repository import SystemPluginRepository
from cadence.repository.user_org_membership_repository import (
    UserOrgMembershipRepository,
)
from cadence.repository.user_repository import UserRepository
from cadence.service.auth_service import AuthService
from cadence.service.conversation_service import ConversationService
from cadence.service.orchestrator_service import OrchestratorService
from cadence.service.plugin_service import PluginService
from cadence.service.settings_service import SettingsService
from cadence.service.tenant_service import TenantService

logger = logging.getLogger(__name__)


async def initialize_database_clients(
    settings: AppSettings,
) -> tuple[PostgreSQLClient, MongoDBClient, RedisClient]:
    """Initialize and connect all database clients."""
    postgres_client = PostgreSQLClient(settings.postgres_url)
    await postgres_client.connect()

    mongo_client = MongoDBClient(settings.mongo_url)
    await mongo_client.connect()

    redis_client = RedisClient(
        settings.redis_url,
        settings.redis_default_db,
    )
    await redis_client.connect()

    logger.info("Database connections established")
    return postgres_client, mongo_client, redis_client


def create_all_postgresql_repositories(
    postgres_client: PostgreSQLClient,
) -> dict[str, Any]:
    """Create all PostgreSQL repository instances."""
    return {
        "global_settings_repository": GlobalSettingsRepository(postgres_client),
        "organization_repository": OrganizationRepository(postgres_client),
        "organization_settings_repository": OrganizationSettingsRepository(
            postgres_client
        ),
        "organization_llm_config_repository": OrganizationLLMConfigRepository(
            postgres_client
        ),
        "provider_model_config_repository": ProviderModelConfigRepository(
            postgres_client
        ),
        "system_plugin_repository": SystemPluginRepository(postgres_client),
        "organization_plugin_catalog_repository": OrgPluginRepository(postgres_client),
        "orchestrator_instance_repository": OrchestratorInstanceRepository(
            postgres_client
        ),
        "user_repository": UserRepository(postgres_client),
        "user_org_membership_repository": UserOrgMembershipRepository(postgres_client),
        "conversation_repository": ConversationRepository(postgres_client),
    }


def create_redis_cache(redis_client: RedisClient) -> RedisCache:
    """Create Redis cache with the cadence namespace."""
    underlying_redis = redis_client.get_client()
    return RedisCache(underlying_redis, namespace="cadence")


def build_all_application_services(
    repositories: dict[str, Any],
    conversation_store: MessageRepository,
    plugin_store: Optional[PluginStoreRepository],
    session_store: SessionStoreRepository,
    settings: AppSettings,
) -> dict[str, Any]:
    """Build all application service instances from their dependencies."""
    tenant_service = TenantService(
        org_repo=repositories["organization_repository"],
        org_settings_repo=repositories["organization_settings_repository"],
        org_llm_config_repo=repositories["organization_llm_config_repository"],
        user_repo=repositories["user_repository"],
        membership_repo=repositories["user_org_membership_repository"],
        instance_repo=repositories["orchestrator_instance_repository"],
    )

    settings_service = SettingsService(
        global_settings_repo=repositories["global_settings_repository"],
        org_settings_repo=repositories["organization_settings_repository"],
        instance_repo=repositories["orchestrator_instance_repository"],
        org_repo=repositories["organization_repository"],
    )

    conversation_service = ConversationService(
        message_repo=conversation_store,
        conversation_repo=repositories["conversation_repository"],
    )

    plugin_service = PluginService(
        system_plugin_repo=repositories["system_plugin_repository"],
        org_plugin_repo=repositories["organization_plugin_catalog_repository"],
        plugin_store=plugin_store,
    )

    auth_service = AuthService(
        user_repo=repositories["user_repository"],
        membership_repo=repositories["user_org_membership_repository"],
        org_repo=repositories["organization_repository"],
        session_store=session_store,
        secret_key=settings.secret_key,
        algorithm=settings.jwt_algorithm,
        token_ttl_seconds=settings.access_token_expire_minutes * 60,
    )

    return {
        "tenant_service": tenant_service,
        "settings_service": settings_service,
        "conversation_service": conversation_service,
        "plugin_service": plugin_service,
        "auth_service": auth_service,
    }


def create_s3_client(settings: AppSettings) -> Optional[S3Client]:
    """Create S3Client if plugin S3 storage is enabled and credentials are configured."""
    if not settings.plugin_s3_enabled:
        logger.info("Plugin S3 storage disabled (CADENCE_PLUGIN_S3_ENABLED=false)")
        return None

    if not settings.s3_access_key_id or not settings.s3_secret_access_key:
        logger.warning(
            "Plugin S3 storage is enabled but credentials are not configured "
            "(CADENCE_S3_ACCESS_KEY_ID / CADENCE_S3_SECRET_ACCESS_KEY). "
            "Falling back to local filesystem only."
        )
        return None

    client = S3Client(
        endpoint_url=settings.s3_endpoint_url,
        access_key_id=settings.s3_access_key_id,
        secret_access_key=settings.s3_secret_access_key,
        bucket_name=settings.s3_bucket_name,
        region=settings.s3_region,
    )
    logger.info(
        f"S3 client configured: endpoint={settings.s3_endpoint_url or 'AWS'}, "
        f"bucket={settings.s3_bucket_name}"
    )
    return client


def create_plugin_store(
    settings: AppSettings, s3_client: Optional[S3Client]
) -> PluginStoreRepository:
    """Create PluginStore with optional S3 backend."""
    return PluginStoreRepository(
        tenant_plugins_root=str(settings.tenant_plugins_root),
        system_plugins_dir=str(settings.system_plugins_dir),
        s3_client=s3_client,
    )


def create_orchestrator_factory(
    settings: AppSettings,
    org_llm_config_repo: OrganizationLLMConfigRepository,
    plugin_store: Optional[PluginStoreRepository] = None,
) -> OrchestratorFactory:
    """Create orchestrator factory with LLM and plugin configuration."""
    llm_factory = LLMModelFactory(org_llm_config_repo)

    return OrchestratorFactory(
        llm_factory=llm_factory,
        tenant_plugins_root=str(settings.tenant_plugins_root),
        system_plugins_dir=str(settings.system_plugins_dir),
        plugin_store=plugin_store,
    )


def _parse_plugin_reference(plugin_ref: str) -> tuple[str, str]:
    """Extract plugin ID and version from a plugin reference string.

    Plugin references use the format 'plugin_id@version'.
    When no version is specified, 'latest' is assumed.

    Returns:
        Tuple of (plugin_id, version).
    """
    if "@" in plugin_ref:
        plugin_id, version = plugin_ref.split("@", 1)
        return plugin_id, version
    return plugin_ref, "latest"


async def _ensure_plugin_files_available(
    plugin_store: PluginStoreRepository,
    active_plugins: list[str],
    org_id: str,
) -> None:
    """Download any missing plugin files from S3 to local cache."""
    for plugin_ref in active_plugins:
        try:
            plugin_id, version = _parse_plugin_reference(plugin_ref)
            await plugin_store.ensure_local(
                pid=plugin_id, version=version, org_id=org_id
            )
        except Exception as e:
            logger.warning(f"Could not ensure local plugin {plugin_ref}: {e}")


async def load_hot_tier_instances(
    orchestrator_pool: OrchestratorPool,
    instance_repo: OrchestratorInstanceRepository,
    plugin_store: Optional[PluginStoreRepository],
) -> int:
    """Load all hot-tier instances into the pool at startup.

    Returns:
        Number of successfully loaded instances.
    """
    hot_instances = await instance_repo.list_by_tier("hot", status="active")
    loaded_count = 0

    for instance in hot_instances:
        instance_id = instance["instance_id"]
        try:
            active_plugins = instance.get("config", {}).get("active_plugins", [])
            if plugin_store is not None:
                await _ensure_plugin_files_available(
                    plugin_store, active_plugins, instance["org_id"]
                )

            instance_config = {
                **instance["config"],
                "plugin_settings": instance.get("plugin_settings", {}),
            }
            resolved_config = {**instance_config, "org_id": instance["org_id"]}

            await orchestrator_pool.create_instance(
                instance_id=instance_id,
                org_id=instance["org_id"],
                framework_type=instance["framework_type"],
                mode=instance["mode"],
                instance_config=instance_config,
                resolved_config=resolved_config,
            )

            if hasattr(orchestrator_pool, "set_hash") and instance.get("config_hash"):
                orchestrator_pool.set_hash(instance_id, instance["config_hash"])

            logger.info(f"Loaded hot-tier instance {instance_id}")
            loaded_count += 1
        except Exception as e:
            logger.error(f"Failed to load hot-tier instance {instance_id}: {e}")

    logger.info(f"Hot-tier pool initialized with {loaded_count} instances")
    return loaded_count


async def shutdown_orchestrator_pool(orchestrator_pool: OrchestratorPool) -> None:
    """Safely shut down all orchestrator pool instances."""
    if hasattr(orchestrator_pool, "cleanup_all"):
        await orchestrator_pool.cleanup_all()
    else:
        logger.warning("OrchestratorPool.cleanup_all() not available, skipping cleanup")


async def disconnect_database_clients(
    postgres_client: PostgreSQLClient,
    mongo_client: MongoDBClient,
    redis_client: RedisClient,
) -> None:
    """Disconnect all database clients."""
    await postgres_client.disconnect()
    await mongo_client.disconnect()
    await redis_client.disconnect()
    logger.info("Database connections closed")


def create_lifespan_handler(settings: AppSettings):
    """Create the FastAPI lifespan context manager bound to the given settings.

    Returns:
        An async context manager suitable for FastAPI's lifespan parameter.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Manage application startup and shutdown lifecycle."""
        logger.info("=== Cadence v2 Startup ===")

        app.state.app_settings = settings

        postgres_client, mongo_client, redis_client = await initialize_database_clients(
            settings
        )
        app.state.postgres_client = postgres_client
        app.state.mongo_client = mongo_client
        app.state.redis_client = redis_client

        repositories = create_all_postgresql_repositories(postgres_client)
        app.state.postgres_repo = repositories["global_settings_repository"]
        app.state.system_plugin_repo = repositories["system_plugin_repository"]
        app.state.org_plugin_repo = repositories[
            "organization_plugin_catalog_repository"
        ]
        app.state.instance_repo = repositories["orchestrator_instance_repository"]
        app.state.provider_model_repo = repositories["provider_model_config_repository"]

        redis_cache = create_redis_cache(redis_client)
        app.state.redis_cache = redis_cache

        session_store = SessionStoreRepository(
            redis=redis_client.get_client(),
            default_ttl_seconds=settings.access_token_expire_minutes * 60,
        )
        app.state.session_store = session_store

        conversation_store = MessageRepository(mongo_client)
        app.state.conversation_store = conversation_store

        s3_client = create_s3_client(settings)
        plugin_store = create_plugin_store(settings, s3_client)
        app.state.plugin_store = plugin_store

        services = build_all_application_services(
            repositories, conversation_store, plugin_store, session_store, settings
        )
        app.state.tenant_service = services["tenant_service"]
        app.state.settings_service = services["settings_service"]
        app.state.conversation_service = services["conversation_service"]
        app.state.plugin_service = services["plugin_service"]
        app.state.auth_service = services["auth_service"]

        orchestrator_factory = create_orchestrator_factory(
            settings, repositories["organization_llm_config_repository"], plugin_store
        )

        orchestrator_pool = OrchestratorPool(
            factory=orchestrator_factory,
            db_repositories={
                "orchestrator_instance_repo": repositories[
                    "orchestrator_instance_repository"
                ],
            },
        )
        app.state.orchestrator_pool = orchestrator_pool

        rabbitmq_client = RabbitMQClient(settings.rabbitmq_url)
        try:
            await rabbitmq_client.connect()
            app.state.rabbitmq_client = rabbitmq_client

            event_publisher = OrchestratorEventPublisher(rabbitmq_client)
            app.state.event_publisher = event_publisher

            event_consumer = OrchestratorEventConsumer(
                client=rabbitmq_client,
                pool=orchestrator_pool,
                instance_repo=repositories["orchestrator_instance_repository"],
                plugin_store=plugin_store,
            )
            await event_consumer.start()
            app.state.event_consumer = event_consumer
            logger.info("RabbitMQ event publisher and consumer started")
        except Exception as e:
            logger.warning(f"RabbitMQ not available — events disabled: {e}")
            app.state.rabbitmq_client = None
            app.state.event_publisher = None
            app.state.event_consumer = None

        await load_hot_tier_instances(
            orchestrator_pool,
            repositories["orchestrator_instance_repository"],
            plugin_store,
        )

        orchestrator_service = OrchestratorService(
            pool=orchestrator_pool,
            conversation_service=services["conversation_service"],
        )
        app.state.orchestrator_service = orchestrator_service

        logger.info("=== Cadence v2 Ready ===")

        yield

        logger.info("=== Cadence v2 Shutdown ===")

        running_event_consumer = getattr(app.state, "event_consumer", None)
        if running_event_consumer:
            try:
                await running_event_consumer.stop()
            except Exception as e:
                logger.warning(f"Error stopping event consumer: {e}")

        connected_rabbitmq_client = getattr(app.state, "rabbitmq_client", None)
        if connected_rabbitmq_client:
            try:
                await connected_rabbitmq_client.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting RabbitMQ: {e}")

        await shutdown_orchestrator_pool(orchestrator_pool)

        await disconnect_database_clients(postgres_client, mongo_client, redis_client)

        logger.info("=== Cadence v2 Stopped ===")

    return lifespan
