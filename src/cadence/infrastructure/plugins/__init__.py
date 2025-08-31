"""Plugin infrastructure for Cadence framework.

Provides SDK-based agent discovery and management with dynamic loading,
health monitoring, and LangGraph integration for the multi-agent system.
"""

from .sdk_manager import SDKPluginBundle, SDKPluginManager

__all__ = [
    "SDKPluginManager",
    "SDKPluginBundle",
]
