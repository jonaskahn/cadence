"""Infrastructure layer for Cadence framework.

Provides external service integrations, data persistence, and plugin management
for the multi-agent AI system with multi-backend support.
"""

from cadence.infrastructure.database import DatabaseFactory
from cadence.infrastructure.llm import LLMModelFactory
from cadence.infrastructure.plugins import SDKPluginManager

__all__ = ["DatabaseFactory", "LLMModelFactory", "SDKPluginManager"]
