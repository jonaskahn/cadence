"""Unit tests for cadence.engine.utils.message_utils.

Covers:
- filter_tool_messages: removes UvToolMessage, keeps others
- get_last_human_message: returns last human msg or None
- count_tokens_estimate: character-based token estimation
- compact_tool_messages: truncates oversized tool messages
- compact_messages_by_mode: mode dispatch (none / tool / aggressive)
- compact_messages: max_messages window, keep_system flag
- build_message_summary: counts by role
"""

from cadence.engine.utils.message_utils import (
    build_message_summary,
    compact_messages,
    compact_messages_by_mode,
    compact_tool_messages,
    count_tokens_estimate,
    filter_tool_messages,
    get_last_human_message,
)
from cadence_sdk.types.sdk_messages import (
    UvAIMessage,
    UvHumanMessage,
    UvSystemMessage,
    UvToolMessage,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tool_msg(content: str, tool_call_id: str = "tc1") -> UvToolMessage:
    return UvToolMessage(content=content, tool_call_id=tool_call_id, tool_name="search")


def _human(content: str) -> UvHumanMessage:
    return UvHumanMessage(content=content)


def _ai(content: str) -> UvAIMessage:
    return UvAIMessage(content=content)


def _system(content: str) -> UvSystemMessage:
    return UvSystemMessage(content=content)


# ---------------------------------------------------------------------------
# filter_tool_messages
# ---------------------------------------------------------------------------


class TestFilterToolMessages:
    def test_removes_tool_messages(self):
        msgs = [_human("hi"), _tool_msg("result"), _ai("ok")]
        result = filter_tool_messages(msgs)
        assert len(result) == 2
        assert not any(isinstance(m, UvToolMessage) for m in result)

    def test_returns_all_when_no_tool_messages(self):
        msgs = [_human("hi"), _ai("hello")]
        assert filter_tool_messages(msgs) == msgs

    def test_empty_list_returns_empty(self):
        assert filter_tool_messages([]) == []

    def test_only_tool_messages_returns_empty(self):
        msgs = [_tool_msg("a"), _tool_msg("b")]
        assert filter_tool_messages(msgs) == []


# ---------------------------------------------------------------------------
# get_last_human_message
# ---------------------------------------------------------------------------


class TestGetLastHumanMessage:
    def test_returns_last_human(self):
        first = _human("first")
        last = _human("last")
        msgs = [first, _ai("middle"), last]
        assert get_last_human_message(msgs) is last

    def test_returns_none_when_no_human(self):
        msgs = [_ai("response"), _tool_msg("data")]
        assert get_last_human_message(msgs) is None

    def test_empty_list_returns_none(self):
        assert get_last_human_message([]) is None

    def test_single_human_message(self):
        msg = _human("only one")
        assert get_last_human_message([msg]) is msg


# ---------------------------------------------------------------------------
# count_tokens_estimate
# ---------------------------------------------------------------------------


class TestCountTokensEstimate:
    def test_four_chars_is_one_token(self):
        msgs = [_human("abcd")]  # 4 chars → 1 token
        assert count_tokens_estimate(msgs) == 1

    def test_zero_for_empty_list(self):
        assert count_tokens_estimate([]) == 0

    def test_sums_all_messages(self):
        msgs = [_human("aaaa"), _ai("bbbb")]  # 4 + 4 = 8 chars → 2 tokens
        assert count_tokens_estimate(msgs) == 2

    def test_integer_division(self):
        msgs = [_human("abc")]  # 3 chars → 0 tokens (floor division)
        assert count_tokens_estimate(msgs) == 0


# ---------------------------------------------------------------------------
# compact_tool_messages
# ---------------------------------------------------------------------------


class TestCompactToolMessages:
    def test_short_tool_message_unchanged(self):
        msg = _tool_msg("short", "tc1")
        result = compact_tool_messages([msg], max_chars=100)
        assert result[0].content == "short"

    def test_long_tool_message_truncated(self):
        long_content = "x" * 200
        msg = _tool_msg(long_content, "tc1")
        result = compact_tool_messages([msg], max_chars=50)
        assert len(result) == 1
        assert "truncated" in result[0].content
        assert result[0].content.startswith("x" * 50)

    def test_non_tool_messages_pass_through(self):
        human = _human("hello")
        result = compact_tool_messages([human], max_chars=5)
        assert result[0] is human

    def test_truncated_message_preserves_tool_call_id(self):
        msg = _tool_msg("y" * 500, "call_abc")
        result = compact_tool_messages([msg], max_chars=10)
        assert result[0].tool_call_id == "call_abc"

    def test_preserves_order(self):
        msgs = [_human("q"), _tool_msg("x" * 200, "tc1"), _ai("a")]
        result = compact_tool_messages(msgs, max_chars=10)
        assert isinstance(result[0], UvHumanMessage)
        assert isinstance(result[1], UvToolMessage)
        assert isinstance(result[2], UvAIMessage)


# ---------------------------------------------------------------------------
# compact_messages_by_mode
# ---------------------------------------------------------------------------


class TestCompactMessagesByMode:
    def test_none_mode_returns_unchanged(self):
        msgs = [_human("hi"), _tool_msg("x" * 500)]
        result = compact_messages_by_mode(msgs, mode="none", max_tool_chars=10)
        assert result is msgs

    def test_tool_mode_compacts_tool_messages(self):
        msgs = [_tool_msg("z" * 200)]
        result = compact_messages_by_mode(msgs, mode="tool", max_tool_chars=10)
        assert "truncated" in result[0].content

    def test_aggressive_mode_compacts_tool_messages(self):
        msgs = [_tool_msg("z" * 200)]
        result = compact_messages_by_mode(msgs, mode="aggressive", max_tool_chars=10)
        assert "truncated" in result[0].content

    def test_unknown_mode_returns_unchanged(self):
        msgs = [_human("hi")]
        result = compact_messages_by_mode(msgs, mode="unknown")
        assert result is msgs


# ---------------------------------------------------------------------------
# compact_messages
# ---------------------------------------------------------------------------


class TestCompactMessages:
    def test_no_limit_returns_all(self):
        msgs = [_human("a"), _human("b"), _human("c")]
        assert compact_messages(msgs, max_messages=None) is msgs

    def test_within_limit_returns_all(self):
        msgs = [_human("a"), _human("b")]
        result = compact_messages(msgs, max_messages=5)
        assert result is msgs

    def test_truncates_to_max_messages(self):
        msgs = [_human(str(i)) for i in range(10)]
        result = compact_messages(msgs, max_messages=3, keep_system=False)
        assert len(result) == 3
        assert result[-1].content == "9"

    def test_keep_system_preserves_system_messages(self):
        sys_msg = _system("You are helpful")
        humans = [_human(str(i)) for i in range(5)]
        msgs = [sys_msg] + humans
        result = compact_messages(msgs, max_messages=3, keep_system=True)
        assert sys_msg in result

    def test_keep_system_false_trims_everything(self):
        sys_msg = _system("sys")
        humans = [_human(str(i)) for i in range(5)]
        msgs = [sys_msg] + humans
        result = compact_messages(msgs, max_messages=2, keep_system=False)
        assert len(result) == 2
        assert sys_msg not in result

    def test_keep_system_with_too_many_system_messages(self):
        """When system messages alone fill the budget, only they are returned."""
        sys_msgs = [_system(f"sys{i}") for i in range(5)]
        result = compact_messages(sys_msgs, max_messages=2, keep_system=True)
        assert all(isinstance(m, UvSystemMessage) for m in result)


# ---------------------------------------------------------------------------
# build_message_summary
# ---------------------------------------------------------------------------


class TestBuildMessageSummary:
    def test_counts_all_roles(self):
        msgs = [
            _human("q1"),
            _human("q2"),
            _ai("a1"),
            _system("s1"),
            _tool_msg("t1"),
            _tool_msg("t2"),
            _tool_msg("t3"),
        ]
        summary = build_message_summary(msgs)
        assert "2 human" in summary
        assert "1 AI" in summary
        assert "1 system" in summary
        assert "3 tool" in summary

    def test_empty_list_all_zeros(self):
        summary = build_message_summary([])
        assert "0 human" in summary
        assert "0 AI" in summary

    def test_only_human_messages(self):
        msgs = [_human("a"), _human("b")]
        summary = build_message_summary(msgs)
        assert "2 human" in summary
        assert "0 AI" in summary
