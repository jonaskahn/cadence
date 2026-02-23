"""Chat API endpoints with SSE streaming support.

This module provides chat endpoints for interacting with orchestrator instances
with support for both streaming (SSE) and synchronous responses.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from cadence.middleware.authorization_middleware import require_org_member
from cadence.middleware.tenant_context_middleware import TenantContext
from cadence.service.orchestrator_service import OrchestratorService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/orgs/{org_id}/completion", tags=["completion"])


class ChatRequest(BaseModel):
    """Chat request payload.

    Attributes:
        instance_id: Orchestrator instance ID
        message: User message text
        conversation_id: Optional conversation ID
    """

    instance_id: str = Field(
        ...,
        description="Orchestrator instance identifier",
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="User message",
    )
    conversation_id: Optional[str] = Field(
        None,
        description="Conversation ID for maintaining context",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "instance_id": "550e8400-e29b-41d4-a716-446655440000",
                "message": "What is the weather in San Francisco?",
                "conversation_id": "conv_abc123xyz",
            }
        }


class ChatResponse(BaseModel):
    """Chat response payload for synchronous endpoint.

    Attributes:
        session_id: Conversation session ID
        response: AI response text
        agent_hops: Number of agent hops executed
        current_agent: Last agent that processed the request
    """

    session_id: str = Field(..., description="Conversation session ID")
    response: str = Field(..., description="AI assistant response")
    agent_hops: int = Field(..., description="Number of agent routing hops")
    current_agent: str = Field(..., description="Last agent that processed the request")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "conv_abc123xyz",
                "response": "The weather in San Francisco is sunny with a temperature of 72°F.",
                "agent_hops": 3,
                "current_agent": "weather_plugin",
            }
        }


@router.post(
    "/stream",
    response_class=StreamingResponse,
    summary="Chat with AI (Streaming)",
    description="""
Send a message to an AI orchestrator and receive a streaming response via Server-Sent Events (SSE).

**Event Types:**
- `agent_start`: Agent begins processing
- `agent_end`: Agent completes processing
- `tool_start`: Tool invocation begins
- `tool_end`: Tool invocation completes
- `message`: AI assistant message chunk
- `error`: Error occurred
- `metadata`: Additional metadata

**Example SSE Response:**
```
event: agent_start
data: {"agent": "supervisor", "timestamp": 1708234567.123}

event: tool_start
data: {"tool": "weather_plugin.get_weather", "args": {"location": "San Francisco"}}

event: tool_end
data: {"tool": "weather_plugin.get_weather", "result": "Sunny, 72°F"}

event: message
data: {"content": "The weather in San Francisco is sunny with a temperature of 72°F."}

event: agent_end
data: {"agent": "supervisor", "timestamp": 1708234568.456}
```
""",
    responses={
        200: {
            "description": "SSE stream of chat events",
            "content": {
                "text/event-stream": {
                    "example": 'event: message\ndata: {"content": "Hello!"}\n\n'
                }
            },
        },
        403: {"description": "Access denied to this orchestrator instance"},
        404: {"description": "Orchestrator instance not found"},
        500: {"description": "Internal server error"},
    },
)
async def chat_stream(
    chat_request: ChatRequest,
    request: Request,
    context: TenantContext = Depends(require_org_member),
):
    """Stream chat response using Server-Sent Events.

    Args:
        chat_request: Chat request with instance_id and message
        request: FastAPI request
        context: Tenant context from JWT

    Returns:
        StreamingResponse with SSE events

    Raises:
        HTTPException: If instance not found or not accessible
    """
    orchestrator_service: OrchestratorService = request.app.state.orchestrator_service

    try:
        await _validate_instance_access(
            orchestrator_service,
            chat_request.instance_id,
            context.org_id,
        )

        async def event_generator():
            """Generate SSE events from orchestrator stream."""
            try:
                async for stream_event in orchestrator_service.process_chat_stream(
                    org_id=context.org_id,
                    instance_id=chat_request.instance_id,
                    user_id=context.user_id,
                    message=chat_request.message,
                    conversation_id=chat_request.conversation_id,
                ):
                    yield stream_event.to_sse()
                    yield "\n\n"

            except Exception as e:
                logger.error(f"Stream error: {e}", exc_info=True)
                error_event = {
                    "event": "error",
                    "data": {"error": str(e)},
                }
                yield f"data: {error_event}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat stream failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process chat request",
        )


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Chat with AI (Synchronous)",
    description="""
Send a message to an AI orchestrator and wait for the complete response.

Use this endpoint when you need the full response at once rather than streaming.
For real-time streaming responses, use the streaming endpoint instead.

**Note:** This endpoint will wait until the orchestrator completes processing
before returning. For long-running requests, consider using the streaming endpoint.
""",
    responses={
        200: {
            "description": "Complete chat response",
            "content": {
                "application/json": {
                    "example": {
                        "session_id": "conv_abc123xyz",
                        "response": "The weather in San Francisco is sunny with a temperature of 72°F.",
                        "agent_hops": 3,
                        "current_agent": "weather_plugin",
                    }
                }
            },
        },
        403: {"description": "Access denied to this orchestrator instance"},
        404: {"description": "Orchestrator instance not found"},
        500: {"description": "Internal server error"},
    },
)
async def chat_sync(
    chat_request: ChatRequest,
    request: Request,
    context: TenantContext = Depends(require_org_member),
):
    """Process chat request and return complete response.

    Args:
        chat_request: Chat request with instance_id and message
        request: FastAPI request
        context: Tenant context from JWT

    Returns:
        ChatResponse with complete AI response

    Raises:
        HTTPException: If instance not found or processing fails
    """
    orchestrator_service: OrchestratorService = request.app.state.orchestrator_service

    try:
        await _validate_instance_access(
            orchestrator_service,
            chat_request.instance_id,
            context.org_id,
        )

        result = await orchestrator_service.process_chat(
            org_id=context.org_id,
            instance_id=chat_request.instance_id,
            user_id=context.user_id,
            message=chat_request.message,
            conversation_id=chat_request.conversation_id,
        )

        return ChatResponse(
            session_id=result.get("conversation_id", ""),
            response=result.get("response", ""),
            agent_hops=result.get("metadata", {}).get("agent_hops", 0),
            current_agent=result.get("metadata", {}).get("current_agent", ""),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat sync failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process chat request",
        )


async def _validate_instance_access(
    orchestrator_service: OrchestratorService,
    instance_id: str,
    org_id: str,
) -> None:
    """Validate tenant has access to orchestrator instance.

    Args:
        orchestrator_service: Orchestrator service
        instance_id: Instance ID to validate
        org_id: Organization ID from tenant context

    Raises:
        HTTPException: If instance not found or not accessible
    """
    instance_org_id = await orchestrator_service.get_instance_org_id(instance_id)

    if not instance_org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Instance {instance_id} not found",
        )

    if instance_org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this instance",
        )
