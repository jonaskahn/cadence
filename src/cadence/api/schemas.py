"""API Data Models and Validation Schemas.

This module defines all Pydantic models used for API request validation, response serialization,
and OpenAPI documentation generation. Each schema represents a specific data contract
for the Cadence multi-agent conversation system.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request model for initiating or continuing a conversation with the multi-agent system.

    Contains the user's message, optional conversation threading, metadata for context,
    and response tone preferences for personalized interactions.
    """

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
    """Response model containing the agent's reply and conversation session information.

    Provides the processed response from the multi-agent system along with
    session tracking details for maintaining conversation context.
    """

    response: str = Field(..., description="Agent's response to the user message")
    thread_id: str = Field(..., description="Session identifier for conversation threading")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional processing metadata (agent, tokens, timing)"
    )


class PluginInfo(BaseModel):
    """Plugin metadata and operational status information.

    Represents a discovered plugin with its capabilities, version information,
    and current health status for system monitoring and management.
    """

    name: str = Field(..., description="Plugin identifier name")
    version: str = Field(..., description="Plugin version in semantic versioning format")
    description: str = Field(..., description="Human-readable description of plugin functionality")
    capabilities: List[str] = Field(..., description="List of capabilities or features provided by the plugin")
    status: str = Field(..., description="Current plugin health status", pattern="^(healthy|failed)$")
    source: str = Field(
        default="unknown",
        description="Where the plugin was loaded from: environment|directory|storage|unknown",
        pattern="^(environment|directory|storage|unknown)$",
    )


class SystemStatus(BaseModel):
    """Comprehensive system health and operational status.

    Provides an overview of the entire Cadence system including plugin health,
    available services, and system metrics for monitoring and diagnostics.
    """

    status: str = Field(
        ..., description="Overall system health status", pattern="^(operational|healthydegraded|failed)$"
    )
    available_plugins: List[str] = Field(..., description="List of all discovered plugin names")
    healthy_plugins: List[str] = Field(..., description="List of currently healthy plugin names")
    failed_plugins: List[str] = Field(..., description="List of plugin names with failures")
    total_sessions: int = Field(..., description="Number of active conversation sessions", ge=0)
