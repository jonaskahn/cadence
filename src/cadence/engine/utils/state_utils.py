"""State manipulation utilities for orchestrators."""

from copy import deepcopy
from typing import Any, Dict

from cadence_sdk.types.sdk_state import UvState


def copy_state(state: UvState) -> UvState:
    """Create deep copy of state."""
    return deepcopy(state)


def merge_states(base: UvState, updates: Dict[str, Any]) -> UvState:
    """Merge updates into base state."""
    result = copy_state(base)
    result.update(updates)
    return result


def sanitize_state(state: UvState) -> UvState:
    """Remove None values and empty collections from state."""
    return {
        k: v
        for k, v in state.items()
        if v is not None and (not isinstance(v, (list, dict)) or v)
    }
