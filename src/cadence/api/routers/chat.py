"""Chat Conversation API Endpoints.

This router provides the primary message processing endpoint for the multi-agent conversation system.
It handles user message requests, orchestrates agent responses, and manages conversation threading
for continuous dialogue sessions.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ...core.services import ConversationService
from ...domain.dtos.chat_dtos import ChatRequest, ChatResponse
from ..services import global_service_container

chat_api_router = APIRouter()


def get_conversation_service() -> ConversationService:
    """Dependency injection function to retrieve the conversation service from the global container."""
    return global_service_container.get_conversation_service()


@chat_api_router.post("/chat", response_model=ChatResponse)
async def process_chat_message(
    chat_request: ChatRequest,
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> ChatResponse:
    """Process user message through the multi-agent orchestrator system.

    Receives a user message, routes it through the appropriate agents based on content,
    and returns the coordinated response while maintaining conversation context.
    """
    return await conversation_service.process_message(chat_request)


router = chat_api_router
