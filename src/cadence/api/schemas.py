"""API request and response schemas.

Defines Pydantic models for request validation, response serialization, and OpenAPI documentation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """User message request for multi-agent processing."""

    message: str = Field(
        ..., description="User message to be processed by the multi-agent system", min_length=1, max_length=10000
    )
    thread_id: Optional[str] = Field(
        default=None, description="Optional session identifier for conversation threading", max_length=255
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional metadata for context or configuration"
    )
    tone: Optional[str] = Field(
        default="natural",
        description="Response tone: natural, explanatory, formal, concise, learning",
        pattern="^(natural|explanatory|formal|concise|learning)$",
    )


class ChatResponse(BaseModel):
    """Agent response with session information."""

    response: str = Field(..., description="Agent's response to the user message")
    thread_id: str = Field(..., description="Session identifier for conversation threading")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional processing metadata (agent, tokens, timing)"
    )


class PluginInfo(BaseModel):
    """Plugin metadata and health status."""

    name: str = Field(..., description="Plugin identifier name")
    version: str = Field(..., description="Plugin version in semantic versioning format")
    description: str = Field(..., description="Human-readable description of plugin functionality")
    capabilities: List[str] = Field(..., description="List of capabilities or features provided by the plugin")
    status: str = Field(..., description="Current plugin health status", pattern="^(healthy|failed)$")


class SystemStatus(BaseModel):
    """System health status and plugin information."""

    status: str = Field(
        ..., description="Overall system health status", pattern="^(operational|healthydegraded|failed)$"
    )
    available_plugins: List[str] = Field(..., description="List of all discovered plugin names")
    healthy_plugins: List[str] = Field(..., description="List of currently healthy plugin names")
    failed_plugins: List[str] = Field(..., description="List of plugin names with failures")
    total_sessions: int = Field(..., description="Number of active conversation sessions", ge=0)
