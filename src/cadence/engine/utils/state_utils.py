"""State manipulation utilities for orchestrators.

This module provides utilities for copying, merging, and sanitizing orchestrator state.
"""

from copy import deepcopy
from typing import Any, Dict

from cadence_sdk.types.sdk_state import UvState


def copy_state(state: UvState) -> UvState:
    """Create deep copy of state.

    Args:
        state: State to copy

    Returns:
        Deep copied state
    """
    return deepcopy(state)


def merge_states(base: UvState, updates: Dict[str, Any]) -> UvState:
    """Merge updates into base state.

    Args:
        base: Base state dictionary
        updates: Updates to apply

    Returns:
        Merged state
    """
    result = copy_state(base)
    result.update(updates)
    return result


def sanitize_state(state: UvState) -> UvState:
    """Remove None values and empty collections from state.

    Args:
        state: State to sanitize

    Returns:
        Sanitized state
    """
    return {
        k: v
        for k, v in state.items()
        if v is not None and (not isinstance(v, (list, dict)) or v)
    }


def extract_metadata(state: UvState) -> Dict[str, Any]:
    """Extract metadata from state.

    Args:
        state: State to extract from

    Returns:
        Metadata dictionary
    """
    return state.get("metadata", {})


def update_metadata(state: UvState, updates: Dict[str, Any]) -> UvState:
    """Update metadata in state.

    Args:
        state: State to update
        updates: Metadata updates

    Returns:
        Updated state
    """
    result = copy_state(state)
    metadata = result.get("metadata", {})
    metadata.update(updates)
    result["metadata"] = metadata
    return result
