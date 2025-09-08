"""API Service Layer Initialization."""

from __future__ import annotations

from typing import Optional

from ..config.settings import Settings
from ..core.services.service_container import global_service_container, initialize_container
from ..infrastructure.database.repositories import ConversationRepository, ThreadRepository


async def initialize_api(
    application_settings: Settings,
    thread_repository: Optional[ThreadRepository] = None,
    conversation_repository: Optional[ConversationRepository] = None,
) -> None:
    """Initialize the global service container with application configuration."""
    await initialize_container(application_settings, thread_repository, conversation_repository)


__all__ = ["initialize_api", "global_service_container"]
