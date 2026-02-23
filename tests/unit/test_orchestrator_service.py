"""Unit tests for OrchestratorService.

Verifies process_chat (sync), process_chat_stream (async generator),
and get_instance_org_id. All orchestrator and conversation interactions
are mocked to isolate the service layer.
"""

from typing import AsyncIterator, List
from unittest.mock import AsyncMock, MagicMock

import pytest
from cadence_sdk.types.sdk_messages import UvAIMessage

from cadence.service.orchestrator_service import OrchestratorService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def conversation_service(
    conversation_store: MagicMock, conversation_repo: MagicMock
) -> MagicMock:
    """Provide a ConversationService mock with pre-wired async methods."""
    from cadence.service.conversation_service import ConversationService

    service = ConversationService(
        message_repo=conversation_store,
        conversation_repo=conversation_repo,
    )
    service.create_conversation = AsyncMock(return_value="conv_test")
    service.get_history = AsyncMock(return_value=[])
    service.save_message = AsyncMock(return_value=None)
    return service


@pytest.fixture
def service(
    orchestrator_pool: MagicMock, conversation_service: MagicMock
) -> OrchestratorService:
    """Provide an OrchestratorService with pool and conversation service mocked."""
    return OrchestratorService(
        pool=orchestrator_pool,
        conversation_service=conversation_service,
    )


async def collect_stream_events(async_gen: AsyncIterator) -> List:
    """Collect all events from an async generator into a list.

    Args:
        async_gen: Async generator yielding stream events.

    Returns:
        List of all yielded events.
    """
    events = []
    async for event in async_gen:
        events.append(event)
    return events


# ---------------------------------------------------------------------------
# process_chat – conversation management
# ---------------------------------------------------------------------------


class TestProcessChatConversationManagement:
    """Tests for OrchestratorService.process_chat — conversation lifecycle."""

    async def test_creates_new_conversation_when_none_provided(
        self, service: OrchestratorService, conversation_service: MagicMock
    ) -> None:
        """process_chat creates a conversation when conversation_id is absent."""
        await service.process_chat(
            org_id="org_test",
            instance_id="inst_test",
            user_id="user_1",
            message="Hello",
        )

        conversation_service.create_conversation.assert_awaited_once_with(
            org_id="org_test",
            user_id="user_1",
            instance_id="inst_test",
        )

    async def test_skips_conversation_creation_when_id_provided(
        self, service: OrchestratorService, conversation_service: MagicMock
    ) -> None:
        """process_chat reuses an existing conversation when conversation_id is provided."""
        await service.process_chat(
            org_id="org_test",
            instance_id="inst_test",
            user_id="user_1",
            message="Hello",
            conversation_id="conv_existing",
        )

        conversation_service.create_conversation.assert_not_awaited()

    async def test_loads_conversation_history_before_processing(
        self, service: OrchestratorService, conversation_service: MagicMock
    ) -> None:
        """process_chat fetches the last 50 messages before invoking the orchestrator."""
        await service.process_chat(
            org_id="org_test",
            instance_id="inst_test",
            user_id="user_1",
            message="Hello",
            conversation_id="conv_existing",
        )

        conversation_service.get_history.assert_awaited_once_with(
            org_id="org_test",
            conversation_id="conv_existing",
            limit=50,
        )


# ---------------------------------------------------------------------------
# process_chat – orchestrator interaction
# ---------------------------------------------------------------------------


class TestProcessChatOrchestratorInteraction:
    """Tests for OrchestratorService.process_chat — orchestrator delegation."""

    async def test_fetches_orchestrator_from_pool(
        self, service: OrchestratorService, orchestrator_pool: MagicMock
    ) -> None:
        """process_chat retrieves the correct orchestrator from the pool."""
        await service.process_chat("org_test", "inst_test", "u1", "Hi")

        orchestrator_pool.get.assert_awaited_once_with("inst_test")

    async def test_calls_orchestrator_ask_with_state(
        self, service: OrchestratorService, mock_orchestrator: MagicMock
    ) -> None:
        """process_chat invokes orchestrator.ask once with the built conversation state."""
        await service.process_chat("org_test", "inst_test", "u1", "Hello")

        mock_orchestrator.ask.assert_awaited_once()

    async def test_saves_new_messages_after_orchestrator_responds(
        self, service: OrchestratorService, conversation_service: MagicMock
    ) -> None:
        """process_chat persists the orchestrator's response messages to history."""
        await service.process_chat("org_test", "inst_test", "u1", "Hello")

        assert conversation_service.save_message.await_count >= 1


# ---------------------------------------------------------------------------
# process_chat – response structure
# ---------------------------------------------------------------------------


class TestProcessChatResponseStructure:
    """Tests for OrchestratorService.process_chat — return value shape."""

    async def test_returns_dict_with_all_required_keys(
        self, service: OrchestratorService
    ) -> None:
        """process_chat returns a dict containing conversation_id, response, messages, and metadata."""
        result = await service.process_chat("org_test", "inst_test", "u1", "Hello")

        assert "conversation_id" in result
        assert "response" in result
        assert "messages" in result
        assert "metadata" in result

    async def test_response_contains_ai_message_content(
        self, service: OrchestratorService, mock_orchestrator: MagicMock
    ) -> None:
        """process_chat extracts the last AI message content as the response text."""
        mock_orchestrator.ask.return_value = {
            "messages": [UvAIMessage(content="AI reply here")],
            "agent_hops": 2,
            "current_agent": "agent_x",
        }

        result = await service.process_chat("org_test", "inst_test", "u1", "Hello")

        assert result["response"] == "AI reply here"

    async def test_metadata_includes_agent_hops_count(
        self, service: OrchestratorService, mock_orchestrator: MagicMock
    ) -> None:
        """process_chat includes agent_hops from the orchestrator result in metadata."""
        mock_orchestrator.ask.return_value = {
            "messages": [UvAIMessage(content="reply")],
            "agent_hops": 3,
            "current_agent": "coordinator",
        }

        result = await service.process_chat("org_test", "inst_test", "u1", "Hi")

        assert result["metadata"]["agent_hops"] == 3

    async def test_metadata_includes_current_agent_name(
        self, service: OrchestratorService, mock_orchestrator: MagicMock
    ) -> None:
        """process_chat includes current_agent from the orchestrator result in metadata."""
        mock_orchestrator.ask.return_value = {
            "messages": [UvAIMessage(content="reply")],
            "agent_hops": 1,
            "current_agent": "coordinator",
        }

        result = await service.process_chat("org_test", "inst_test", "u1", "Hi")

        assert result["metadata"]["current_agent"] == "coordinator"

    async def test_returns_empty_response_when_no_ai_messages_produced(
        self, service: OrchestratorService, mock_orchestrator: MagicMock
    ) -> None:
        """process_chat returns empty string response when orchestrator produces no AI messages."""
        mock_orchestrator.ask.return_value = {
            "messages": [],
            "agent_hops": 0,
            "current_agent": "",
        }

        result = await service.process_chat("org_test", "inst_test", "u1", "Hi")

        assert result["response"] == ""


# ---------------------------------------------------------------------------
# process_chat_stream
# ---------------------------------------------------------------------------


class TestProcessChatStream:
    """Tests for OrchestratorService.process_chat_stream."""

    async def test_creates_conversation_when_none_provided(
        self, service: OrchestratorService, conversation_service: MagicMock
    ) -> None:
        """process_chat_stream creates a new conversation when none is provided."""
        from cadence.infrastructure.streaming.stream_event import StreamEvent

        async def single_message_stream(state):
            yield StreamEvent.message("Hello")

        service.pool.get.return_value.astream = single_message_stream

        await collect_stream_events(
            service.process_chat_stream("org_test", "inst_test", "u1", "Hi")
        )

        conversation_service.create_conversation.assert_awaited_once()

    async def test_yields_events_from_orchestrator_stream(
        self, service: OrchestratorService, mock_orchestrator: MagicMock
    ) -> None:
        """process_chat_stream yields all events produced by the orchestrator."""
        from cadence.infrastructure.streaming.stream_event import StreamEvent

        async def two_message_stream(state):
            yield StreamEvent.message("chunk1")
            yield StreamEvent.message("chunk2")

        mock_orchestrator.astream = two_message_stream

        events = await collect_stream_events(
            service.process_chat_stream("org_test", "inst_test", "u1", "Hi")
        )

        assert len(events) >= 3  # two chunks + final metadata

    async def test_emits_metadata_event_as_final_event(
        self, service: OrchestratorService, mock_orchestrator: MagicMock
    ) -> None:
        """process_chat_stream appends a metadata event with saved=True at the end."""
        from cadence.infrastructure.streaming.stream_event import StreamEvent

        async def single_token_stream(state):
            yield StreamEvent.message("token")

        mock_orchestrator.astream = single_token_stream

        events = await collect_stream_events(
            service.process_chat_stream("org_test", "inst_test", "u1", "Hi")
        )

        last_event = events[-1]
        assert last_event.event_type == "metadata"
        assert last_event.data.get("saved") is True

    async def test_saves_user_message_to_history_after_streaming(
        self,
        service: OrchestratorService,
        mock_orchestrator: MagicMock,
        conversation_service: MagicMock,
    ) -> None:
        """process_chat_stream persists the user message once streaming completes."""
        from cadence.infrastructure.streaming.stream_event import StreamEvent

        async def minimal_stream(state):
            yield StreamEvent.message("hi")

        mock_orchestrator.astream = minimal_stream

        await collect_stream_events(
            service.process_chat_stream("org_test", "inst_test", "u1", "Hello")
        )

        conversation_service.save_message.assert_awaited_once()


# ---------------------------------------------------------------------------
# get_instance_org_id
# ---------------------------------------------------------------------------


class TestGetInstanceOrgId:
    """Tests for OrchestratorService.get_instance_org_id."""

    async def test_returns_org_id_from_orchestrator_attribute(
        self, service: OrchestratorService, mock_orchestrator: MagicMock
    ) -> None:
        """get_instance_org_id extracts org_id from the orchestrator when present."""
        mock_orchestrator.org_id = "org_from_orch"

        result = await service.get_instance_org_id("inst_test")

        assert result == "org_from_orch"

    async def test_returns_none_when_orchestrator_lacks_org_id(
        self, service: OrchestratorService, mock_orchestrator: MagicMock
    ) -> None:
        """get_instance_org_id returns None when the orchestrator has no org_id attribute."""
        if hasattr(mock_orchestrator, "org_id"):
            delattr(mock_orchestrator, "org_id")

        result = await service.get_instance_org_id("inst_test")

        assert result is None

    async def test_returns_none_when_pool_raises(
        self, service: OrchestratorService, orchestrator_pool: MagicMock
    ) -> None:
        """get_instance_org_id returns None when the pool cannot find the instance."""
        orchestrator_pool.get.side_effect = ValueError("not found")

        result = await service.get_instance_org_id("missing_inst")

        assert result is None
