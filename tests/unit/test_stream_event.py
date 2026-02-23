"""Unit tests for cadence.infrastructure.streaming.stream_event.

Covers:
- StreamEventType constants
- StreamEvent construction and attribute storage
- to_sse: SSE format (event + data lines)
- to_dict: dictionary representation with all fields
- agent_start, message, metadata factory methods
"""

import json

from cadence.infrastructure.streaming.stream_event import StreamEvent, StreamEventType

# ---------------------------------------------------------------------------
# StreamEventType constants
# ---------------------------------------------------------------------------


class TestStreamEventTypeConstants:
    def test_agent_constant(self):
        assert StreamEventType.AGENT == "agent"

    def test_message_constant(self):
        assert StreamEventType.MESSAGE == "message"

    def test_metadata_constant(self):
        assert StreamEventType.METADATA == "metadata"


# ---------------------------------------------------------------------------
# StreamEvent construction
# ---------------------------------------------------------------------------


class TestStreamEventConstruction:
    def test_stores_event_type(self):
        event = StreamEvent("agent", {"key": "value"})
        assert event.event_type == "agent"

    def test_stores_data(self):
        data = {"content": "hello", "role": "assistant"}
        event = StreamEvent("message", data)
        assert event.data == data

    def test_timestamp_defaults_to_current_time(self):
        import time

        before = time.time()
        event = StreamEvent("agent", {})
        after = time.time()
        assert before <= event.timestamp <= after

    def test_custom_timestamp_stored(self):
        event = StreamEvent("agent", {}, timestamp=12345.0)
        assert event.timestamp == 12345.0


# ---------------------------------------------------------------------------
# to_sse
# ---------------------------------------------------------------------------


class TestToSse:
    def test_starts_with_event_line(self):
        event = StreamEvent("agent", {"progress": 10})
        sse = event.to_sse()
        assert sse.startswith("event: agent\n")

    def test_contains_data_line_with_json(self):
        event = StreamEvent("message", {"content": "hi"})
        sse = event.to_sse()
        assert "data: " in sse
        # Extract the JSON part from the data line
        data_line = [line for line in sse.split("\n") if line.startswith("data:")][0]
        payload = json.loads(data_line[len("data: ") :])
        assert payload["content"] == "hi"

    def test_ends_with_double_newline(self):
        event = StreamEvent("agent", {})
        assert event.to_sse().endswith("\n\n")

    def test_format_is_event_data_blank(self):
        event = StreamEvent("metadata", {"k": "v"})
        sse = event.to_sse()
        lines = sse.split("\n")
        assert lines[0].startswith("event:")
        assert lines[1].startswith("data:")


# ---------------------------------------------------------------------------
# to_dict
# ---------------------------------------------------------------------------


class TestToDict:
    def test_contains_event_type(self):
        event = StreamEvent("agent", {})
        d = event.to_dict()
        assert d["event_type"] == "agent"

    def test_contains_data(self):
        data = {"foo": "bar"}
        event = StreamEvent("message", data)
        d = event.to_dict()
        assert d["data"] == data

    def test_contains_timestamp(self):
        event = StreamEvent("agent", {}, timestamp=9999.0)
        d = event.to_dict()
        assert d["timestamp"] == 9999.0


# ---------------------------------------------------------------------------
# Factory methods
# ---------------------------------------------------------------------------


class TestAgentStart:
    def test_event_type_is_agent(self):
        event = StreamEvent.agent_start({"progress": 5})
        assert event.event_type == StreamEventType.AGENT

    def test_data_is_passed_through(self):
        data = {"progress": 20, "key": "msg.planner"}
        event = StreamEvent.agent_start(data)
        assert event.data == data

    def test_none_data_accepted(self):
        event = StreamEvent.agent_start(None)
        assert event.event_type == StreamEventType.AGENT


class TestMessageFactory:
    def test_event_type_is_message(self):
        event = StreamEvent.message("hello")
        assert event.event_type == StreamEventType.MESSAGE

    def test_content_stored_in_data(self):
        event = StreamEvent.message("world")
        assert event.data["content"] == "world"

    def test_default_role_is_assistant(self):
        event = StreamEvent.message("hi")
        assert event.data["role"] == "assistant"

    def test_custom_role_stored(self):
        event = StreamEvent.message("hi", role="user")
        assert event.data["role"] == "user"

    def test_extra_kwargs_included(self):
        event = StreamEvent.message("hi", session_id="abc")
        assert event.data["session_id"] == "abc"


class TestMetadataFactory:
    def test_event_type_is_metadata(self):
        event = StreamEvent.metadata({"version": "1.0"})
        assert event.event_type == StreamEventType.METADATA

    def test_metadata_dict_stored_as_data(self):
        meta = {"org_id": "org_1", "latency_ms": 120}
        event = StreamEvent.metadata(meta)
        assert event.data == meta
