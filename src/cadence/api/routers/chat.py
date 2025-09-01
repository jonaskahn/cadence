"""Chat conversation endpoints.

Provides message processing endpoint for multi-agent conversation system.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ...core.services import ConversationService
from ...domain.dtos.chat_dtos import ChatRequest, ChatResponse
from ..services import global_service_container

chat_api_router = APIRouter()


def get_conversation_service() -> ConversationService:
    """Retrieve conversation service from global container."""
    return global_service_container.get_conversation_service()


@chat_api_router.post("/chat", response_model=ChatResponse)
async def process_chat_message(
    chat_request: ChatRequest,
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> ChatResponse:
    """Process user message through multi-agent orchestrator."""
    return await conversation_service.process_message(chat_request)


router = chat_api_router
