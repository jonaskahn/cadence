from enum import Enum
from typing import FrozenSet, Optional


class Framework(str, Enum):
    """Target orchestration framework for model creation."""

    LANGGRAPH = "langgraph"
    OPENAI_AGENTS = "openai_agents"
    GOOGLE_ADK = "google_adk"


FRAMEWORK_SUPPORTED_PROVIDERS: dict[str, Optional[FrozenSet[str]]] = {
    Framework.LANGGRAPH: frozenset(
        {
            "openai",
            "azure",
            "gemini",
            "claude",
            "anthropic",
            "tensorzero",
            "litellm",
            "groq",
        }
    ),
    Framework.GOOGLE_ADK: frozenset({"litellm", "claude", "anthropic"}),
    Framework.OPENAI_AGENTS: frozenset({"openai", "litellm"}),
}

FRAMEWORK_SUPPORTED_MODES: dict[str, FrozenSet[str]] = {
    Framework.LANGGRAPH: frozenset({"supervisor"}),
    Framework.GOOGLE_ADK: frozenset({"supervisor"}),
    Framework.OPENAI_AGENTS: frozenset(),
}
