"""HTTP client for Cadence API communication.

Provides clean interfaces for chat, plugin management, and system status
with the Cadence FastAPI backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx


@dataclass
class ChatResult:
    """Result of a chat message exchange."""

    response: str
    thread_id: str
    conversation_id: str
    metadata: Dict[str, Any]


@dataclass
class PluginInfo:
    """Plugin metadata and health status."""

    name: str
    version: str
    description: str
    capabilities: List[str]
    status: str


@dataclass
class SystemStatus:
    """System health and status information."""

    status: str
    available_plugins: List[str]
    healthy_plugins: List[str]
    failed_plugins: List[str]
    total_sessions: int


class CadenceApiClient:
    """HTTP client for communicating with the Cadence FastAPI backend."""

    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self.base_url = base_url.rstrip("/")

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Make HTTP request to backend and return JSON response."""
        with httpx.Client(base_url=self.base_url, timeout=30.0) as client:
            response = client.request(method, endpoint, **kwargs)
            response.raise_for_status()
            return response.json()

    def chat(
        self,
        message: str,
        thread_id: Optional[str] = None,
        user_id: str = "anonymous",
        org_id: str = "public",
        metadata: Optional[Dict[str, Any]] = None,
        tone: Optional[str] = None,
    ) -> ChatResult:
        """Send chat message and return assistant response."""
        payload = {
            "message": message,
            "session_id": thread_id,
            "metadata": metadata or {},
            "tone": tone or "natural",
        }

        data = self._make_request("POST", "/api/v1/chat/chat", json=payload)
        return ChatResult(
            response=data.get("response", ""),
            thread_id=data.get("session_id", thread_id or ""),
            conversation_id=data.get("session_id", ""),
            metadata=data.get("metadata", {}),
        )

    def get_plugins(self) -> List[PluginInfo]:
        """Fetch available plugins with metadata and status."""
        data = self._make_request("GET", "/api/v1/plugins/plugins")
        return [PluginInfo(**plugin) for plugin in data]

    def get_system_status(self) -> SystemStatus:
        """Fetch system status and health information."""
        data = self._make_request("GET", "/api/v1/system/status")
        return SystemStatus(**data)

    def reload_plugins(self) -> Dict[str, Any]:
        """Reload all plugins and return result."""
        return self._make_request("POST", "/api/v1/plugins/plugins/reload")
