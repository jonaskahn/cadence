"""Data transfer objects for chat-related API contracts."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Chat request DTO for user message processing."""

    message: str = Field(..., min_length=1, max_length=10000, description="User message content")
    thread_id: Optional[str] = Field(None, description="Thread ID for conversation continuity")
    user_id: str = Field("anonymous", description="User identifier")
    org_id: str = Field("public", description="Organization identifier")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional request metadata")
    tone: Optional[str] = Field(
        default="natural",
        description="Response tone: natural, explanatory, formal, concise, learning",
        pattern="^(natural|explanatory|formal|concise|learning)$",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Hello, how can you help me?",
                "thread_id": "thread_123",
                "user_id": "user_456",
                "org_id": "org_789",
                "metadata": {"source": "web_ui", "priority": "normal"},
                "tone": "natural",
            }
        }


class TokenUsage(BaseModel):
    """Token usage information for cost tracking."""

    input_tokens: int = Field(..., ge=0, description="Input tokens used")
    output_tokens: int = Field(..., ge=0, description="Output tokens used")
    total_tokens: int = Field(..., ge=0, description="Total tokens used")

    def __init__(self, **data):
        super().__init__(**data)
        if self.total_tokens != self.input_tokens + self.output_tokens:
            self.total_tokens = self.input_tokens + self.output_tokens


class ChatResponse(BaseModel):
    """Chat response DTO with assistant response and metadata."""

    response: str = Field(..., description="Assistant response content")
    thread_id: str = Field(..., description="Thread ID for this conversation")
    conversation_id: str = Field(..., description="Unique identifier for this conversation")
    token_usage: TokenUsage = Field(..., description="Token usage information")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Response metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "response": "I can help you with various tasks. What would you like to know?",
                "thread_id": "thread_123",
                "conversation_id": "conv_456",
                "token_usage": {"input_tokens": 25, "output_tokens": 42, "total_tokens": 67},
                "metadata": {
                    "agent_hops": 2,
                    "tools_used": ["search", "calculator"],
                    "processing_time": 1.23,
                    "model_used": "gpt-4",
                },
            }
        }


class ConversationResponse(BaseModel):
    """Response DTO for individual conversation retrieval."""

    conversation_id: str = Field(..., description="Unique conversation identifier")
    thread_id: str = Field(..., description="Thread this conversation belongs to")
    user_message: str = Field(..., description="User message")
    assistant_message: str = Field(..., description="Assistant response")
    token_usage: TokenUsage = Field(..., description="Token usage for this conversation")
    created_at: str = Field(..., description="ISO timestamp of conversation creation")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Conversation metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "conversation_id": "conv_456",
                "thread_id": "thread_123",
                "user_message": "What is 2+2?",
                "assistant_message": "2+2 equals 4.",
                "token_usage": {"input_tokens": 8, "output_tokens": 12, "total_tokens": 20},
                "created_at": "2024-01-15T10:30:00Z",
                "metadata": {"tools_used": ["calculator"], "processing_time": 0.5},
            }
        }
