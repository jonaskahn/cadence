"""Data Transfer Objects for thread management."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ThreadCreateRequest(BaseModel):
    """Request to create a new conversation thread."""

    user_id: str = Field("anonymous", description="User identifier")
    org_id: str = Field("public", description="Organization identifier")
    initial_message: Optional[str] = Field(None, description="Optional initial message")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional thread metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_123",
                "org_id": "org_456",
                "initial_message": "I need help with my project",
                "metadata": {"source": "web_ui", "category": "support"},
            }
        }


class ThreadResponse(BaseModel):
    """Response containing thread information."""

    thread_id: str = Field(..., description="Unique thread identifier")
    user_id: str = Field(..., description="User who owns this thread")
    org_id: str = Field(..., description="Organization this thread belongs to")
    status: str = Field(..., description="Thread status (active/archived)")
    created_at: str = Field(..., description="ISO timestamp of thread creation")
    updated_at: str = Field(..., description="ISO timestamp of last update")
    total_tokens: int = Field(..., ge=0, description="Total tokens used in this thread")
    input_tokens: int = Field(..., ge=0, description="Input tokens used")
    output_tokens: int = Field(..., ge=0, description="Output tokens used")
    message_count: int = Field(..., ge=0, description="Number of conversation turns")
    estimated_cost: Optional[float] = Field(None, description="Estimated cost in USD")

    class Config:
        json_schema_extra = {
            "example": {
                "thread_id": "thread_123",
                "user_id": "user_456",
                "org_id": "org_789",
                "status": "active",
                "created_at": "2024-01-15T10:00:00Z",
                "updated_at": "2024-01-15T10:30:00Z",
                "total_tokens": 1250,
                "input_tokens": 500,
                "output_tokens": 750,
                "message_count": 5,
                "estimated_cost": 0.035,
            }
        }


class ThreadListRequest(BaseModel):
    """Request to list threads with filtering."""

    user_id: Optional[str] = Field(None, description="Filter by user ID")
    org_id: Optional[str] = Field(None, description="Filter by organization ID")
    status: Optional[str] = Field(None, description="Filter by status (active/archived)")
    limit: int = Field(20, ge=1, le=100, description="Number of threads to return")
    offset: int = Field(0, ge=0, description="Number of threads to skip")
    sort_by: str = Field("updated_at", description="Sort field (created_at/updated_at/total_tokens)")
    sort_order: str = Field("desc", description="Sort order (asc/desc)")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_123",
                "org_id": "org_456",
                "status": "active",
                "limit": 10,
                "offset": 0,
                "sort_by": "updated_at",
                "sort_order": "desc",
            }
        }


class ThreadListResponse(BaseModel):
    """Response containing list of threads."""

    threads: List[ThreadResponse] = Field(..., description="List of threads")
    total_count: int = Field(..., ge=0, description="Total number of threads matching filters")
    has_more: bool = Field(..., description="Whether there are more threads available")

    class Config:
        json_schema_extra = {
            "example": {
                "threads": [
                    {
                        "thread_id": "thread_123",
                        "user_id": "user_456",
                        "org_id": "org_789",
                        "status": "active",
                        "created_at": "2024-01-15T10:00:00Z",
                        "updated_at": "2024-01-15T10:30:00Z",
                        "total_tokens": 1250,
                        "input_tokens": 500,
                        "output_tokens": 750,
                        "message_count": 5,
                        "estimated_cost": 0.035,
                    }
                ],
                "total_count": 42,
                "has_more": True,
            }
        }


class ThreadUpdateRequest(BaseModel):
    """Request to update thread properties."""

    status: Optional[str] = Field(None, description="New status (active/archived)")

    class Config:
        json_schema_extra = {"example": {"status": "archived"}}
