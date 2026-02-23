"""Plugin routing and description utilities.

This module provides utilities for building plugin descriptions and routing prompts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

from cadence_sdk.base.metadata import PluginMetadata

if TYPE_CHECKING:
    from cadence.infrastructure.plugins import SDKPluginBundle


def build_plugin_description(metadata: PluginMetadata, tools: List[Any]) -> str:
    """Build human-readable plugin description.

    Args:
        metadata: Plugin metadata
        tools: List of plugin tools

    Returns:
        Formatted description string
    """
    tool_names = ", ".join(tool.name for tool in tools)
    capabilities = (
        ", ".join(metadata.capabilities) if metadata.capabilities else "general"
    )

    description = f"{metadata.name} (v{metadata.version}): {metadata.description}\n"
    description += f"Capabilities: {capabilities}\n"
    description += f"Tools: {tool_names}"

    return description


def build_routing_prompt(plugin_descriptions: List[str]) -> str:
    """Build routing prompt for coordinator mode.

    Args:
        plugin_descriptions: List of plugin description strings

    Returns:
        Routing prompt text
    """
    prompt = "You are a coordinator agent. Route user requests to appropriate specialized agents.\n\n"
    prompt += "Available agents:\n\n"

    for i, desc in enumerate(plugin_descriptions, 1):
        prompt += f"{i}. {desc}\n\n"

    prompt += "Choose the most appropriate agent based on the user's request. "
    prompt += "You can route to different agents as needed to complete the task."

    return prompt


def extract_plugin_capabilities(metadata: PluginMetadata) -> List[str]:
    """Extract normalized capability tags from metadata.

    Args:
        metadata: Plugin metadata

    Returns:
        List of normalized capability strings
    """
    if not metadata.capabilities:
        return ["general"]

    return [cap.lower().strip() for cap in metadata.capabilities]


def match_capability(query: str, capabilities: List[str]) -> float:
    """Calculate capability match score for query.

    Simple keyword-based matching.

    Args:
        query: User query string
        capabilities: List of capability tags

    Returns:
        Match score (0.0 to 1.0)
    """
    query_lower = query.lower()
    matches = sum(1 for cap in capabilities if cap in query_lower)

    if matches == 0:
        return 0.0

    return min(1.0, matches / len(capabilities))


def build_all_plugins_description(bundles: Dict[str, SDKPluginBundle]) -> str:
    """Build combined plugin+tool description for supervisor prompt.

    Args:
        bundles: Dict mapping pid to SDKPluginBundle

    Returns:
        Formatted plugin descriptions for supervisor system prompt
    """
    parts = []
    for pid, bundle in bundles.items():
        meta = bundle.metadata
        capabilities = ", ".join(meta.capabilities) if meta.capabilities else "general"
        tool_names = ", ".join(t.name for t in bundle.orchestrator_tools)
        parts.append(
            f"Plugin: {meta.name} (pid={pid})\n"
            f"Description: {meta.description}\n"
            f"Capabilities: {capabilities}\n"
            f"Tools: {tool_names}"
        )
    return "\n\n".join(parts)


def build_tool_descriptions(bundles: Dict[str, SDKPluginBundle]) -> str:
    """Build tool-level descriptions for supervisor prompt.

    Args:
        bundles: Dict mapping pid to SDKPluginBundle

    Returns:
        Formatted per-tool descriptions
    """
    parts = []
    for bundle in bundles.values():
        for tool in bundle.orchestrator_tools:
            desc = getattr(tool, "description", "")
            parts.append(f"- {tool.name}: {desc}")
    return "\n".join(parts)


def select_plugin_by_capability(
    query: str,
    plugins_metadata: Dict[str, PluginMetadata],
) -> str:
    """Select best plugin for query based on capabilities.

    Args:
        query: User query string
        plugins_metadata: Dict mapping plugin name to metadata

    Returns:
        Best matching plugin name
    """
    best_score = 0.0
    best_plugin = next(iter(plugins_metadata.keys()))

    for name, metadata in plugins_metadata.items():
        capabilities = extract_plugin_capabilities(metadata)
        score = match_capability(query, capabilities)

        if score > best_score:
            best_score = score
            best_plugin = name

    return best_plugin
