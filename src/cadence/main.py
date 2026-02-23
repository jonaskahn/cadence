"""Cadence v2 FastAPI application.

This module initializes and configures the Cadence v2 multi-tenant
AI agent platform API with middleware, routers, and lifecycle management.
"""

# ruff: noqa: E402  — load_dotenv() must run before any cadence imports that read env

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cadence.middleware import ErrorHandlerMiddleware

env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from cadence.config.app_settings import AppSettings
from cadence.controller import (
    admin_controller,
    auth_controller,
    chat_controller,
    health_controller,
    orchestrator_controller,
    plugin_controller,
    system_plugin_controller,
    tenant_controller,
)
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
from cadence.middleware.rate_limiting_middleware import RateLimitMiddleware
from cadence.middleware.tenant_context_middleware import TenantContextMiddleware
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
from cadence.repository.provider_model_config_repository import (
    ProviderModelConfigRepository,
)
from cadence.repository.organization_plugin_repository import (
    OrganizationPluginRepository,
)
from cadence.repository.organization_repository import OrganizationRepository
from cadence.repository.organization_settings_repository import (
    OrganizationSettingsRepository,
)
from cadence.repository.plugin_store_repository import PluginStoreRepository
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app_settings = AppSettings()

DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60
DEFAULT_RATE_LIMIT_MAX_REQUESTS = 100


async def initialize_database_clients(
    app_settings: AppSettings,
) -> tuple[PostgreSQLClient, MongoDBClient, RedisClient]:
    """Initialize and connect all database clients."""
    postgres_client = PostgreSQLClient(app_settings.postgres_url)
    await postgres_client.connect()

    mongo_client = MongoDBClient(app_settings.mongo_url)
    await mongo_client.connect()

    redis_client = RedisClient(
        app_settings.redis_url,
        app_settings.redis_default_db,
    )
    await redis_client.connect()

    logger.info("Database connections established")
    return postgres_client, mongo_client, redis_client


def create_postgresql_repositories(
    postgres_client: PostgreSQLClient,
) -> dict[str, Any]:
    """Create all PostgreSQL repositories."""
    return {
        "global_settings_repo": GlobalSettingsRepository(postgres_client),
        "org_repo": OrganizationRepository(postgres_client),
        "org_settings_repo": OrganizationSettingsRepository(postgres_client),
        "org_llm_config_repo": OrganizationLLMConfigRepository(postgres_client),
        "provider_model_repo": ProviderModelConfigRepository(postgres_client),
        "org_plugin_repo": OrganizationPluginRepository(postgres_client),
        "system_plugin_repo": SystemPluginRepository(postgres_client),
        "org_catalog_repo": OrgPluginRepository(postgres_client),
        "instance_repo": OrchestratorInstanceRepository(postgres_client),
        "user_repo": UserRepository(postgres_client),
        "membership_repo": UserOrgMembershipRepository(postgres_client),
        "conversation_repo": ConversationRepository(postgres_client),
    }


def create_redis_cache(redis_client: RedisClient) -> RedisCache:
    """Create Redis cache component."""
    underlying_redis = redis_client.get_client()
    return RedisCache(underlying_redis, namespace="cadence")


def create_application_services(
    repositories: dict[str, Any],
    conversation_store: MessageRepository,
    plugin_store: Optional[PluginStoreRepository],
    session_store: SessionStoreRepository,
    app_settings: AppSettings,
) -> dict[str, Any]:
    """Create all application service instances."""
    tenant_service = TenantService(
        org_repo=repositories["org_repo"],
        org_settings_repo=repositories["org_settings_repo"],
        org_llm_config_repo=repositories["org_llm_config_repo"],
        user_repo=repositories["user_repo"],
        membership_repo=repositories["membership_repo"],
        instance_repo=repositories["instance_repo"],
    )

    settings_service = SettingsService(
        global_settings_repo=repositories["global_settings_repo"],
        org_settings_repo=repositories["org_settings_repo"],
        instance_repo=repositories["instance_repo"],
    )

    conversation_service = ConversationService(
        message_repo=conversation_store,
        conversation_repo=repositories["conversation_repo"],
    )

    plugin_service = PluginService(
        system_plugin_repo=repositories["system_plugin_repo"],
        org_plugin_repo=repositories["org_catalog_repo"],
        plugin_store=plugin_store,
    )

    auth_service = AuthService(
        user_repo=repositories["user_repo"],
        membership_repo=repositories["membership_repo"],
        org_repo=repositories["org_repo"],
        session_store=session_store,
        secret_key=app_settings.secret_key,
        algorithm=app_settings.jwt_algorithm,
        token_ttl_seconds=app_settings.access_token_expire_minutes * 60,
    )

    return {
        "tenant_service": tenant_service,
        "settings_service": settings_service,
        "conversation_service": conversation_service,
        "plugin_service": plugin_service,
        "auth_service": auth_service,
    }


def create_s3_client(app_settings: AppSettings) -> Optional[S3Client]:
    """Create S3Client if plugin S3 storage is enabled."""
    if not app_settings.plugin_s3_enabled:
        logger.info("Plugin S3 storage disabled (CADENCE_PLUGIN_S3_ENABLED=false)")
        return None

    client = S3Client(
        endpoint_url=app_settings.s3_endpoint_url,
        access_key_id=app_settings.s3_access_key_id,
        secret_access_key=app_settings.s3_secret_access_key,
        bucket_name=app_settings.s3_bucket_name,
        region=app_settings.s3_region,
    )
    logger.info(
        f"S3 client configured: endpoint={app_settings.s3_endpoint_url or 'AWS'}, "
        f"bucket={app_settings.s3_bucket_name}"
    )
    return client


def create_plugin_store(
    app_settings: AppSettings, s3_client: Optional[S3Client]
) -> PluginStoreRepository:
    """Create PluginStore with optional S3 backend."""
    return PluginStoreRepository(
        tenant_plugins_root=str(app_settings.tenant_plugins_root),
        system_plugins_dir=str(app_settings.system_plugins_dir),
        s3_client=s3_client,
    )


def create_orchestrator_factory(
    app_settings: AppSettings,
    org_llm_config_repo: OrganizationLLMConfigRepository,
    plugin_store: Optional[PluginStoreRepository] = None,
) -> OrchestratorFactory:
    """Create orchestrator factory with LLM configuration."""
    llm_factory = LLMModelFactory(org_llm_config_repo)

    return OrchestratorFactory(
        llm_factory=llm_factory,
        tenant_plugins_root=str(app_settings.tenant_plugins_root),
        system_plugins_dir=str(app_settings.system_plugins_dir),
        plugin_store=plugin_store,
    )


async def load_hot_tier_instances(
    orchestrator_pool: OrchestratorPool,
    instance_repo: OrchestratorInstanceRepository,
    plugin_store: Optional[PluginStoreRepository],
) -> int:
    """Load only hot-tier instances at startup (direct, not via RabbitMQ).

    Args:
        orchestrator_pool: Pool to load instances into
        instance_repo: Repository for fetching instance configs
        plugin_store: Plugin store for ensuring local plugin files
        settings_service: Settings service for resolving configs

    Returns:
        Number of successfully loaded instances
    """
    hot_instances = await instance_repo.list_by_tier("hot", status="active")
    loaded_count = 0

    for instance in hot_instances:
        instance_id = instance["instance_id"]
        try:
            active_plugins = instance.get("config", {}).get("active_plugins", [])
            if plugin_store is not None:
                for plugin_ref in active_plugins:
                    try:
                        pid = (
                            plugin_ref.split("@")[0]
                            if "@" in plugin_ref
                            else plugin_ref
                        )
                        version = (
                            plugin_ref.split("@")[1] if "@" in plugin_ref else "latest"
                        )
                        await plugin_store.ensure_local(
                            pid=pid, version=version, org_id=instance["org_id"]
                        )
                    except Exception as e:
                        logger.warning(
                            f"Could not ensure local plugin {plugin_ref}: {e}"
                        )

            resolved_config = {**instance["config"], "org_id": instance["org_id"]}

            await orchestrator_pool.create_instance(
                instance_id=instance_id,
                org_id=instance["org_id"],
                framework_type=instance["framework_type"],
                mode=instance["mode"],
                instance_config=instance["config"],
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


async def cleanup_orchestrator_pool(orchestrator_pool: OrchestratorPool) -> None:
    """Safely cleanup orchestrator pool instances."""
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("=== Cadence v2 Startup ===")

    app.state.app_settings = app_settings

    logger.info("Loading infrastructure settings (AppSettings)")

    postgres_client, mongo_client, redis_client = await initialize_database_clients(
        app_settings
    )
    app.state.postgres_client = postgres_client
    app.state.mongo_client = mongo_client
    app.state.redis_client = redis_client

    repositories = create_postgresql_repositories(postgres_client)
    app.state.postgres_repo = repositories["global_settings_repo"]
    app.state.system_plugin_repo = repositories["system_plugin_repo"]
    app.state.org_plugin_repo = repositories["org_catalog_repo"]
    app.state.instance_repo = repositories["instance_repo"]
    app.state.provider_model_repo = repositories["provider_model_repo"]

    redis_cache = create_redis_cache(redis_client)
    app.state.redis_cache = redis_cache

    session_store = SessionStoreRepository(
        redis=redis_client.get_client(),
        default_ttl_seconds=app_settings.access_token_expire_minutes * 60,
    )
    app.state.session_store = session_store

    conversation_store = MessageRepository(mongo_client)
    app.state.conversation_store = conversation_store

    s3_client = create_s3_client(app_settings)
    plugin_store = create_plugin_store(app_settings, s3_client)
    app.state.plugin_store = plugin_store

    services = create_application_services(
        repositories, conversation_store, plugin_store, session_store, app_settings
    )
    app.state.tenant_service = services["tenant_service"]
    app.state.settings_service = services["settings_service"]
    app.state.conversation_service = services["conversation_service"]
    app.state.plugin_service = services["plugin_service"]
    app.state.auth_service = services["auth_service"]

    orchestrator_factory = create_orchestrator_factory(
        app_settings, repositories["org_llm_config_repo"], plugin_store
    )

    orchestrator_pool = OrchestratorPool(
        factory=orchestrator_factory,
        db_repositories={
            "orchestrator_instance_repo": repositories["instance_repo"],
        },
    )
    app.state.orchestrator_pool = orchestrator_pool

    rabbitmq_client = RabbitMQClient(app_settings.rabbitmq_url)
    try:
        await rabbitmq_client.connect()
        app.state.rabbitmq_client = rabbitmq_client

        event_publisher = OrchestratorEventPublisher(rabbitmq_client)
        app.state.event_publisher = event_publisher

        event_consumer = OrchestratorEventConsumer(
            client=rabbitmq_client,
            pool=orchestrator_pool,
            instance_repo=repositories["instance_repo"],
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

    logger.info("Loading hot-tier orchestrator instances from database")
    await load_hot_tier_instances(
        orchestrator_pool,
        repositories["instance_repo"],
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

    event_consumer = getattr(app.state, "event_consumer", None)
    if event_consumer:
        try:
            await event_consumer.stop()
        except Exception as e:
            logger.warning(f"Error stopping event consumer: {e}")

    rabbitmq_client = getattr(app.state, "rabbitmq_client", None)
    if rabbitmq_client:
        try:
            await rabbitmq_client.disconnect()
        except Exception as e:
            logger.warning(f"Error disconnecting RabbitMQ: {e}")

    logger.info("Cleaning up orchestrator pool")
    await cleanup_orchestrator_pool(orchestrator_pool)

    await disconnect_database_clients(postgres_client, mongo_client, redis_client)

    logger.info("=== Cadence v2 Stopped ===")


def create_openapi_schema() -> dict:
    """Generate custom OpenAPI schema with security schemes."""
    if app.openapi_schema:
        return app.openapi_schema

    from fastapi.openapi.utils import get_openapi

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        servers=app.servers,
        tags=app.openapi_tags,
    )

    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT token obtained from authentication endpoint. Format: `Bearer <token>`",
        },
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API key for service-to-service authentication. Format: `X-API-Key: <key>`",
        },
    }

    openapi_schema["security"] = [
        {"BearerAuth": []},
        {"ApiKeyAuth": []},
    ]

    openapi_schema["x-rate-limit"] = {
        "default": "100 requests per minute per tenant",
        "configurable": True,
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


async def get_redis_client_for_rate_limiting():
    """Get Redis client for rate limiting middleware."""
    if not hasattr(app.state, "redis_client"):
        return None
    return app.state.redis_client.get_client()


def configure_cors_middleware(application: FastAPI, allowed_origins: list[str]) -> None:
    """Configure CORS middleware with specified origins."""
    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def configure_rate_limiting_middleware(application: FastAPI) -> None:
    """Configure rate limiting middleware."""
    application.add_middleware(
        RateLimitMiddleware,
        redis_client=get_redis_client_for_rate_limiting,
        window_seconds=DEFAULT_RATE_LIMIT_WINDOW_SECONDS,
        max_requests=DEFAULT_RATE_LIMIT_MAX_REQUESTS,
        enabled=True,
    )


def configure_tenant_context_middleware(
    application: FastAPI, app_settings: AppSettings
) -> None:
    """Configure tenant context middleware.

    The session_store is resolved lazily from app.state during each request
    to avoid a circular dependency at startup time.
    """
    application.add_middleware(
        TenantContextMiddleware,
        jwt_secret=app_settings.secret_key,
        jwt_algorithm=app_settings.jwt_algorithm,
    )


def configure_error_handlers_middleware(
    app: FastAPI, app_settings: AppSettings
) -> None:
    """Set up error handlers for FastAPI application."""
    app.state.debug = app_settings.debug
    app.state.environment = app_settings.environment

    app.add_middleware(ErrorHandlerMiddleware)

    logger.info(
        "Error handling middleware configured",
        extra={"debug": app.state.debug, "environment": app.state.environment},
    )


def register_api_routers(application: FastAPI) -> None:
    """Register all API route controllers."""
    application.include_router(health_controller.router)
    application.include_router(auth_controller.router)
    application.include_router(chat_controller.router)
    application.include_router(orchestrator_controller.router)
    application.include_router(orchestrator_controller.engine_router)
    application.include_router(plugin_controller.router)
    application.include_router(system_plugin_controller.router)
    application.include_router(tenant_controller.router)
    application.include_router(admin_controller.router)


app = FastAPI(
    title="Cadence v2",
    description="""
# Multi-Tenant AI Orchestration Platform

Production-ready framework for deploying AI agent orchestrators at scale.

## Features

* **Multi-Backend Support**: LangGraph, OpenAI Agents SDK, Google ADK
* **Multi-Tenancy**: Complete tenant isolation with BYOK (Bring Your Own Key)
* **Three Orchestration Modes**: Supervisor, Coordinator, Handoff
* **Hot-Reload**: Configuration changes without restart
* **Scalable Architecture**: Hot/Warm/Cold tier pool (1000+ instances)
* **Streaming**: Server-Sent Events (SSE) for real-time responses

## Authentication

### JWT Authentication
```
Authorization: Bearer <jwt_token>
```

### API Key Authentication
```
X-API-Key: <api_key>
```

## Rate Limiting

All API endpoints are rate-limited per tenant. Default: 100 requests/minute.

## Documentation

* Platform Docs: [README](https://github.com/jonaskahn/cadence)
* SDK Docs: [cadence-sdk](https://github.com/jonaskahn/cadence-sdk)
""",
    version="2.0.0",
    lifespan=lifespan,
    contact={
        "name": "Cadence Platform Support",
        "url": "https://github.com/jonaskahn/cadence",
        "email": "support@example.com",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    terms_of_service="https://example.com/terms/",
    openapi_tags=[
        {
            "name": "health",
            "description": "Health check endpoints for monitoring system availability and database connectivity.",
        },
        {
            "name": "completion",
            "description": "Chat endpoints for interacting with AI orchestrators. Supports both streaming (SSE) and synchronous responses.",
        },
        {
            "name": "orchestrators",
            "description": "CRUD operations for managing orchestrator instances. Includes hot-reload configuration updates.",
        },
        {
            "name": "plugins",
            "description": "Plugin management endpoints for discovering, uploading, and configuring plugins.",
        },
        {
            "name": "tenants",
            "description": "Tenant (organization) management including settings, LLM configurations, and user management.",
        },
        {
            "name": "admin",
            "description": "Administrative endpoints for platform-wide settings, health monitoring, and pool statistics. Requires admin privileges.",
        },
    ],
    servers=[
        {
            "url": "http://localhost:8000",
            "description": "Local development server",
        },
        {
            "url": "https://api.example.com",
            "description": "Production server",
        },
        {
            "url": "https://staging-api.example.com",
            "description": "Staging server",
        },
    ],
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.openapi = create_openapi_schema

cors_origins = app_settings.cors_origins if app_settings.cors_origins else ["*"]
configure_cors_middleware(app, cors_origins)
configure_rate_limiting_middleware(app)
configure_tenant_context_middleware(app, app_settings)
configure_error_handlers_middleware(app, app_settings)

register_api_routers(app)

logger.info("Cadence v2 application configured")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "cadence.main:app",
        host=app_settings.api_host,
        port=app_settings.api_port,
        reload=app_settings.debug,
    )
