"""Service container with dependency injection.

Manages service lifecycle and dependency injection for the Cadence framework,
providing centralized access to infrastructure and application services.
"""

import logging
from typing import Optional

from cadence_sdk.base.loggable import Loggable
from fastapi import HTTPException

from ...config.settings import Settings
from ...infrastructure.database.factory import DatabaseFactory
from ...infrastructure.database.repositories import (
    ConversationRepository,
    InMemoryConversationRepository,
    InMemoryThreadRepository,
    ThreadRepository,
)
from ...infrastructure.llm.factory import LLMModelFactory
from ...infrastructure.plugins.sdk_manager import SDKPluginManager
from ..orchestrator.coordinator import MultiAgentOrchestrator
from .conversation_service import ConversationService
from .orchestrator_service import OrchestratorService

logger = logging.getLogger(__name__)

try:
    from langgraph.checkpoint.redis import RedisSaver
except Exception:
    RedisSaver = None


class ServiceContainer(Loggable):
    """Service container with layered architecture and dependency injection.

    Manages complete service hierarchy including infrastructure, application,
    and domain layers with proper dependency injection.
    """

    def __init__(self) -> None:
        super().__init__()

        self.settings: Optional[Settings] = None
        self.llm_factory: Optional[LLMModelFactory] = None
        self.plugin_manager: Optional[SDKPluginManager] = None
        self.thread_repository: Optional[ThreadRepository] = None
        self.conversation_repository: Optional[ConversationRepository] = None

        self.orchestrator: Optional[MultiAgentOrchestrator] = None
        self.orchestrator_service: Optional[OrchestratorService] = None
        self.conversation_service: Optional[ConversationService] = None

    async def initialize(
        self,
        settings: Settings,
        thread_repository: Optional[ThreadRepository] = None,
        conversation_repository: Optional[ConversationRepository] = None,
    ) -> None:
        """Initialize all services with dependency injection."""
        self.logger.info("Initializing enhanced service container...")
        self.settings = settings

        self._initialize_infrastructure(settings)
        await self._initialize_repositories(thread_repository, conversation_repository)

        self._initialize_orchestration(settings)
        self._initialize_services()

        self.logger.info("Enhanced service container initialized successfully")
        self.logger.debug(f"Available plugins: {self.plugin_manager.get_available_plugins()}")
        self.logger.debug(
            f"Repository types: Thread={type(self.thread_repository).__name__}, Conversation={type(self.conversation_repository).__name__}"
        )

    def _initialize_infrastructure(self, settings: Settings) -> None:
        """Initialize infrastructure components."""
        provider = settings.default_llm_provider
        if not settings.validate_llm_provider(provider):
            raise ValueError(
                f"Missing or invalid credentials for provider '{provider}'. "
                "Check API key and provider-specific settings."
            )

        self.llm_factory = LLMModelFactory(settings)

        self.plugin_manager = SDKPluginManager(settings.plugins_dir, self.llm_factory)
        self.plugin_manager.discover_and_load_plugins()
        self.plugin_manager.perform_health_checks()

        self.logger.debug(f"Infrastructure initialized with {len(self.plugin_manager.get_available_plugins())} plugins")

    async def _initialize_repositories(
        self, thread_repository: Optional[ThreadRepository], conversation_repository: Optional[ConversationRepository]
    ) -> None:
        """Initialize repositories with dependency injection (backend-aware)."""
        if thread_repository and conversation_repository:
            self.thread_repository = thread_repository
            self.conversation_repository = conversation_repository
            self.logger.debug(
                f"Using provided repositories: {type(thread_repository).__name__}, {type(conversation_repository).__name__}"
            )
            return

        """Build repositories based on configured backend (memory/redis/postgresql)."""
        try:
            factory = DatabaseFactory(self.settings)
            await factory.initialize()
            thread_repo, conv_repo = await factory.create_repositories()
            self.thread_repository = thread_repo
            self.conversation_repository = conv_repo
            self.logger.debug(
                f"Using configured repositories: Thread={type(thread_repo).__name__}, Conversation={type(conv_repo).__name__}"
            )
        except Exception as e:
            self.logger.error(f"Failed to initialize configured repositories, falling back to memory: {e}")
            self._create_memory_repositories()

    def _create_memory_repositories(self):
        """Create in-memory repositories as fallback."""
        self.thread_repository = InMemoryThreadRepository()
        self.conversation_repository = InMemoryConversationRepository(self.thread_repository)
        self.logger.info("Using in-memory repositories (fallback)")

    def _initialize_orchestration(self, settings: Settings) -> None:
        """Initialize LangGraph orchestration with optional checkpointing."""
        checkpointer = self._get_checkpointer(settings)
        self.orchestrator = MultiAgentOrchestrator(
            plugin_manager=self.plugin_manager,
            llm_factory=self.llm_factory,
            settings=settings,
            checkpointer=checkpointer,
        )
        self.logger.info("LangGraph orchestrator initialized")

    def _get_checkpointer(self, settings: Settings):
        """Return langgraph checkpointer based on settings."""
        checkpointer = None
        enable_checkpoints = getattr(settings, "enable_checkpoints", False)
        redis_url = getattr(settings, "redis_url", None)
        if enable_checkpoints and redis_url and RedisSaver is not None:
            try:
                ttl_configuration = None
                checkpoint_ttl_minutes = getattr(settings, "checkpoint_ttl_minutes", 0)
                if checkpoint_ttl_minutes > 0:
                    ttl_configuration = {
                        "default_ttl": checkpoint_ttl_minutes,
                        "refresh_on_read": getattr(settings, "checkpoint_refresh_on_read", True),
                    }
                checkpointer = RedisSaver.from_conn_string(redis_url, ttl=ttl_configuration)
                checkpointer.setup()
                self.logger.info("Initialized Redis checkpointer")
            except Exception as e:
                self.logger.error(f"Failed to initialize Redis checkpointer: {e}")
        return checkpointer

    def _initialize_services(self) -> None:
        """Initialize application services with dependency injection."""
        self.orchestrator_service = OrchestratorService(self.orchestrator)

        self.conversation_service = ConversationService(
            thread_repository=self.thread_repository,
            conversation_repository=self.conversation_repository,
            orchestrator=self.orchestrator,
        )

        self.logger.info("Application services initialized")

    def get_conversation_service(self) -> ConversationService:
        """Get ConversationService instance."""
        if not self.conversation_service:
            raise HTTPException(status_code=503, detail="ConversationService not initialized")
        return self.conversation_service

    def get_orchestrator_service(self) -> OrchestratorService:
        """Get OrchestratorService instance."""
        if not self.orchestrator_service:
            raise HTTPException(status_code=503, detail="OrchestratorService not initialized")
        return self.orchestrator_service

    def get_thread_repository(self) -> ThreadRepository:
        """Get ThreadRepository instance."""
        if not self.thread_repository:
            raise HTTPException(status_code=503, detail="ThreadRepository not initialized")
        return self.thread_repository

    def get_conversation_repository(self) -> ConversationRepository:
        """Get ConversationRepository instance."""
        if not self.conversation_repository:
            raise HTTPException(status_code=503, detail="ConversationRepository not initialized")
        return self.conversation_repository

    def get_orchestrator(self) -> MultiAgentOrchestrator:
        """Get MultiAgentOrchestrator instance (legacy compatibility)."""
        if not self.orchestrator:
            raise HTTPException(status_code=503, detail="Orchestrator not initialized")
        return self.orchestrator

    def get_plugin_manager(self) -> SDKPluginManager:
        """Get SDKPluginManager instance (legacy compatibility)."""
        if not self.plugin_manager:
            raise HTTPException(status_code=503, detail="Plugin manager not initialized")
        return self.plugin_manager

    async def health_check(self) -> dict:
        """Comprehensive health check of all services."""
        health_info = {"status": "healthy", "services": {}, "repositories": {}, "orchestrator": {}, "plugins": {}}

        try:
            if self.orchestrator_service:
                orchestrator_health = await self.orchestrator_service.health_check()
                health_info["orchestrator"] = orchestrator_health
                if orchestrator_health["status"] != "healthy":
                    health_info["status"] = "degraded"

            if self.plugin_manager:
                health_info["plugins"] = {
                    "available": self.plugin_manager.get_available_plugins(),
                    "healthy": list(self.plugin_manager.healthy_plugins),
                    "failed": list(self.plugin_manager.failed_plugins),
                }
                if self.plugin_manager.failed_plugins:
                    health_info["status"] = "degraded"

            if self.thread_repository:
                health_info["repositories"]["thread"] = {
                    "type": type(self.thread_repository).__name__,
                    "status": "healthy",
                }

            if self.conversation_repository:
                health_info["repositories"]["conversation"] = {
                    "type": type(self.conversation_repository).__name__,
                    "status": "healthy",
                }

                if hasattr(self.conversation_repository, "get_storage_efficiency_estimate"):
                    storage_efficiency = self.conversation_repository.get_storage_efficiency_estimate()
                    health_info["repositories"]["conversation"]["storage_efficiency"] = storage_efficiency

            health_info["services"] = {
                "conversation_service": "healthy" if self.conversation_service else "not_initialized",
                "orchestrator_service": "healthy" if self.orchestrator_service else "not_initialized",
            }

        except Exception as e:
            self.logger.error(f"Health check error: {e}")
            health_info["status"] = "unhealthy"
            health_info["error"] = str(e)

        return health_info

    def get_service_info(self) -> dict:
        """Get detailed service information."""
        return {
            "service_container": "EnhancedServiceContainer",
            "architecture": "layered",
            "storage_strategy": "optimized_conversations",
            "storage_reduction": "significant",
            "components": {
                "infrastructure": {
                    "llm_factory": type(self.llm_factory).__name__ if self.llm_factory else None,
                    "plugin_manager": type(self.plugin_manager).__name__ if self.plugin_manager else None,
                    "thread_repository": type(self.thread_repository).__name__ if self.thread_repository else None,
                    "conversation_repository": (
                        type(self.conversation_repository).__name__ if self.conversation_repository else None
                    ),
                },
                "orchestration": {
                    "orchestrator": type(self.orchestrator).__name__ if self.orchestrator else None,
                    "checkpointer_enabled": self.orchestrator.checkpointer is not None if self.orchestrator else False,
                },
                "services": {
                    "conversation_service": (
                        type(self.conversation_service).__name__ if self.conversation_service else None
                    ),
                    "orchestrator_service": (
                        type(self.orchestrator_service).__name__ if self.orchestrator_service else None
                    ),
                },
            },
        }

    async def cleanup(self) -> None:
        """Clean up resources and connections."""
        try:
            self.logger.info("Cleaning up service container...")

            if hasattr(self.thread_repository, "cleanup"):
                await self.thread_repository.cleanup()

            if hasattr(self.conversation_repository, "cleanup"):
                await self.conversation_repository.cleanup()

            if hasattr(self.plugin_manager, "cleanup"):
                await self.plugin_manager.cleanup()

            if hasattr(self.orchestrator, "cleanup"):
                await self.orchestrator.cleanup()

            self.logger.info("Service container cleanup completed")

        except Exception as e:
            self.logger.error(f"Error during service container cleanup: {e}")


global_service_container = ServiceContainer()


async def initialize_container(
    settings: Settings,
    thread_repository: Optional[ThreadRepository] = None,
    conversation_repository: Optional[ConversationRepository] = None,
) -> None:
    """Initialize API with enhanced service container.

    Args:
        settings: Application settings
        thread_repository: Optional custom thread repository
        conversation_repository: Optional custom conversation repository
    """
    await global_service_container.initialize(
        settings=settings, thread_repository=thread_repository, conversation_repository=conversation_repository
    )
    global_service_container.logger.info("Enhanced API initialized successfully")
