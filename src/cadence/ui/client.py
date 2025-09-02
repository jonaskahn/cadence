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
    source: str = "unknown"


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

    def __init__(self, api_base_url: str = "http://localhost:8000") -> None:
        self.base_url = api_base_url.rstrip("/")

    def _make_request(self, http_method: str, api_endpoint: str, **kwargs) -> Any:
        """Make HTTP request to backend and return JSON response."""
        with httpx.Client(base_url=self.base_url, timeout=30.0) as http_client:
            api_response = http_client.request(http_method, api_endpoint, **kwargs)
            api_response.raise_for_status()
            return api_response.json()

    def _request_allow_error_json(self, http_method: str, api_endpoint: str, **kwargs) -> Any:
        """Make HTTP request and return JSON even on 4xx/5xx if server provided it.

        Falls back to a generic error payload if JSON parsing fails.
        """
        with httpx.Client(base_url=self.base_url, timeout=30.0) as http_client:
            api_response = http_client.request(http_method, api_endpoint, **kwargs)
            try:
                data = api_response.json()
            except Exception:
                data = {
                    "success": False,
                    "message": f"HTTP {api_response.status_code} {api_response.reason_phrase}",
                }
            return data

    def chat(
        self,
        user_message: str,
        thread_id: Optional[str] = None,
        user_id: str = "anonymous",
        org_id: str = "public",
        metadata: Optional[Dict[str, Any]] = None,
        tone: Optional[str] = None,
    ) -> ChatResult:
        """Send chat message and return assistant response."""
        chat_payload = {
            "message": user_message,
            "thread_id": thread_id,
            "metadata": metadata or {},
            "tone": tone or "natural",
        }

        response_data = self._make_request("POST", "/api/v1/chat/chat", json=chat_payload)
        return ChatResult(
            response=response_data.get("response", ""),
            thread_id=response_data.get("thread_id", thread_id or ""),
            conversation_id=response_data.get("conversation_id", ""),
            metadata=response_data.get("metadata", {}),
        )

    def get_plugins(self) -> List[PluginInfo]:
        """Fetch available plugins with metadata and status."""
        plugins_data = self._make_request("GET", "/api/v1/plugins/plugins")
        return [PluginInfo(**plugin_data) for plugin_data in plugins_data]

    def get_system_status(self) -> SystemStatus:
        """Fetch system status and health information."""
        status_data = self._make_request("GET", "/api/v1/system/status")
        return SystemStatus(**status_data)

    def reload_plugins(self) -> Dict[str, Any]:
        """Reload all plugins and return result."""
        return self._make_request("POST", "/api/v1/plugins/plugins/reload")

    def upload_plugin(self, file_path: str, force_overwrite: bool = False) -> Dict[str, Any]:
        """Upload a plugin file."""
        with open(file_path, "rb") as f:
            files = {"file": (file_path.split("/")[-1], f, "application/zip")}
            data = {"force_overwrite": force_overwrite}
            return self._request_allow_error_json("POST", "/api/v1/plugins/plugins/upload", files=files, data=data)
