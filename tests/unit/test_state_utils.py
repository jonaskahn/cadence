"""Unit tests for cadence.engine.utils.state_utils.

Covers:
- copy_state: produces an independent deep copy
- merge_states: merges updates into a copy without mutating original
- sanitize_state: removes None values and empty collections
"""

from cadence.engine.utils.state_utils import copy_state, merge_states, sanitize_state

# ---------------------------------------------------------------------------
# copy_state
# ---------------------------------------------------------------------------


class TestCopyState:
    def test_returns_equal_dict(self):
        state = {"messages": ["hello"], "hops": 3}
        copied = copy_state(state)
        assert copied == state

    def test_is_not_same_object(self):
        state = {"key": "value"}
        copied = copy_state(state)
        assert copied is not state

    def test_nested_objects_are_deep_copied(self):
        state = {"messages": ["a", "b"]}
        copied = copy_state(state)
        copied["messages"].append("c")
        assert "c" not in state["messages"]

    def test_empty_state_copies_correctly(self):
        assert copy_state({}) == {}


# ---------------------------------------------------------------------------
# merge_states
# ---------------------------------------------------------------------------


class TestMergeStates:
    def test_applies_updates_to_copy(self):
        base = {"hops": 0, "current_agent": ""}
        result = merge_states(base, {"hops": 5})
        assert result["hops"] == 5

    def test_does_not_mutate_original(self):
        base = {"hops": 0}
        merge_states(base, {"hops": 99})
        assert base["hops"] == 0

    def test_adds_new_keys(self):
        base = {"hops": 1}
        result = merge_states(base, {"new_key": "new_val"})
        assert result["new_key"] == "new_val"
        assert "new_key" not in base

    def test_empty_updates_returns_copy_of_base(self):
        base = {"a": 1}
        result = merge_states(base, {})
        assert result == base
        assert result is not base

    def test_update_overwrites_existing_key(self):
        base = {"status": "idle"}
        result = merge_states(base, {"status": "running"})
        assert result["status"] == "running"


# ---------------------------------------------------------------------------
# sanitize_state
# ---------------------------------------------------------------------------


class TestSanitizeState:
    def test_removes_none_values(self):
        state = {"a": 1, "b": None, "c": "ok"}
        result = sanitize_state(state)
        assert "b" not in result
        assert result["a"] == 1
        assert result["c"] == "ok"

    def test_removes_empty_list(self):
        state = {"items": [], "count": 0}
        result = sanitize_state(state)
        assert "items" not in result

    def test_removes_empty_dict(self):
        state = {"config": {}, "name": "test"}
        result = sanitize_state(state)
        assert "config" not in result
        assert result["name"] == "test"

    def test_keeps_non_empty_list(self):
        state = {"items": ["x"]}
        result = sanitize_state(state)
        assert result["items"] == ["x"]

    def test_keeps_non_empty_dict(self):
        state = {"config": {"key": "val"}}
        result = sanitize_state(state)
        assert result["config"] == {"key": "val"}

    def test_keeps_zero_integer(self):
        """Zero is falsy but not None or empty collection — should be kept."""
        state = {"count": 0}
        result = sanitize_state(state)
        assert "count" in result

    def test_keeps_false_boolean(self):
        """False is falsy but not None or empty collection — should be kept."""
        state = {"enabled": False}
        result = sanitize_state(state)
        assert "enabled" in result

    def test_empty_state_returns_empty(self):
        assert sanitize_state({}) == {}

    def test_all_none_returns_empty(self):
        state = {"a": None, "b": None}
        assert sanitize_state(state) == {}
