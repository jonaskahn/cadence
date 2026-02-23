"""Unit tests for ConversationService.

Verifies message history retrieval and persistence (MongoDB), conversation
creation and metadata tracking (PostgreSQL), and coordinated deletion
across both stores.
"""

import uuid
from unittest.mock import MagicMock

import pytest
from cadence_sdk.types.sdk_messages import UvAIMessage, UvHumanMessage

from cadence.service.conversation_service import ConversationService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def service(
    conversation_store: MagicMock, conversation_repo: MagicMock
) -> ConversationService:
    """Provide a ConversationService with both persistence backends mocked."""
    return ConversationService(
        message_repo=conversation_store,
        conversation_repo=conversation_repo,
    )


# ---------------------------------------------------------------------------
# get_history
# ---------------------------------------------------------------------------


class TestGetHistory:
    """Tests for ConversationService.get_history."""

    async def test_delegates_to_mongo_store_with_all_args(
        self, service: ConversationService, conversation_store: MagicMock
    ) -> None:
        """get_history passes org_id, conversation_id, and limit to the MongoDB store."""
        await service.get_history("org_test", "conv_test", limit=20)

        conversation_store.get_messages.assert_awaited_once_with(
            org_id="org_test",
            conversation_id="conv_test",
            limit=20,
        )

    async def test_uses_default_limit_of_100(
        self, service: ConversationService, conversation_store: MagicMock
    ) -> None:
        """get_history defaults to a 100-message limit when limit is not specified."""
        await service.get_history("org_test", "conv_test")

        call_kwargs = conversation_store.get_messages.call_args.kwargs
        assert call_kwargs["limit"] == 100

    async def test_returns_messages_from_store(
        self, service: ConversationService, conversation_store: MagicMock
    ) -> None:
        """get_history returns exactly what the MongoDB store provides."""
        expected_messages = [
            UvHumanMessage(content="Hello"),
            UvAIMessage(content="Hi there"),
        ]
        conversation_store.get_messages.return_value = expected_messages

        result = await service.get_history("org_test", "conv_test")

        assert result is expected_messages

    async def test_returns_empty_list_for_new_conversation(
        self, service: ConversationService, conversation_store: MagicMock
    ) -> None:
        """get_history returns an empty list when no messages have been stored yet."""
        conversation_store.get_messages.return_value = []

        result = await service.get_history("org_test", "conv_empty")

        assert result == []


# ---------------------------------------------------------------------------
# save_message
# ---------------------------------------------------------------------------


class TestSaveMessage:
    """Tests for ConversationService.save_message."""

    async def test_delegates_to_mongo_store_with_all_args(
        self, service: ConversationService, conversation_store: MagicMock
    ) -> None:
        """save_message forwards org_id, conversation_id, and message to the MongoDB store."""
        message = UvHumanMessage(content="Test message")

        await service.save_message("org_test", "conv_test", message)

        conversation_store.save_message.assert_awaited_once_with(
            org_id="org_test",
            conversation_id="conv_test",
            message=message,
        )

    async def test_saves_ai_messages_as_well_as_human(
        self, service: ConversationService, conversation_store: MagicMock
    ) -> None:
        """save_message accepts both AI and human message types."""
        ai_message = UvAIMessage(content="AI response")

        await service.save_message("org_test", "conv_test", ai_message)

        conversation_store.save_message.assert_awaited_once()

    async def test_returns_none(self, service: ConversationService) -> None:
        """save_message has no return value (void operation)."""
        result = await service.save_message(
            "org_test", "conv_test", UvHumanMessage(content="Hi")
        )

        assert result is None


# ---------------------------------------------------------------------------
# create_conversation
# ---------------------------------------------------------------------------


class TestCreateConversation:
    """Tests for ConversationService.create_conversation."""

    async def test_returns_a_valid_uuid_string(
        self, service: ConversationService
    ) -> None:
        """create_conversation returns a string that is a valid UUID."""
        result = await service.create_conversation("org_test", "user_1", uuid.uuid4())

        uuid.UUID(result)

    async def test_generates_unique_id_for_each_call(
        self, service: ConversationService
    ) -> None:
        """create_conversation produces a different ID on every invocation."""
        first_id = await service.create_conversation("org_test", "user_1", uuid.uuid4())
        second_id = await service.create_conversation(
            "org_test", "user_1", uuid.uuid4()
        )

        assert first_id != second_id

    async def test_persists_conversation_in_postgres(
        self, service: ConversationService, conversation_repo: MagicMock
    ) -> None:
        """create_conversation writes metadata to the PostgreSQL repository."""
        instance_id = uuid.uuid4()
        conversation_id = await service.create_conversation(
            "org_test", "user_1", instance_id
        )

        conversation_repo.create.assert_awaited_once_with(
            conversation_id=conversation_id,
            org_id="org_test",
            user_id="user_1",
            instance_id=instance_id,
        )

    async def test_uses_generated_id_in_postgres_create(
        self, service: ConversationService, conversation_repo: MagicMock
    ) -> None:
        """create_conversation passes the same generated ID to PostgreSQL and returns it."""
        returned_id = await service.create_conversation(
            "org_test", "user_1", uuid.uuid4()
        )

        postgres_call_kwargs = conversation_repo.create.call_args.kwargs
        assert postgres_call_kwargs["conversation_id"] == returned_id


# ---------------------------------------------------------------------------
# list_conversations
# ---------------------------------------------------------------------------


class TestListConversations:
    """Tests for ConversationService.list_conversations."""

    async def test_delegates_to_postgres_repo(
        self, service: ConversationService, conversation_repo: MagicMock
    ) -> None:
        """list_conversations passes org_id and user_id to the PostgreSQL repository."""
        await service.list_conversations("org_test", "user_1")

        conversation_repo.list_for_user.assert_awaited_once_with(
            org_id="org_test",
            user_id="user_1",
        )

    async def test_returns_repository_result(
        self, service: ConversationService, conversation_repo: MagicMock
    ) -> None:
        """list_conversations returns exactly what the PostgreSQL repository provides."""
        expected_conversations = [
            {"conversation_id": "c1", "user_id": "user_1"},
            {"conversation_id": "c2", "user_id": "user_1"},
        ]
        conversation_repo.list_for_user.return_value = expected_conversations

        result = await service.list_conversations("org_test", "user_1")

        assert result is expected_conversations

    async def test_returns_empty_list_for_user_with_no_conversations(
        self, service: ConversationService, conversation_repo: MagicMock
    ) -> None:
        """list_conversations returns an empty list for a user who has no conversations."""
        conversation_repo.list_for_user.return_value = []

        result = await service.list_conversations("org_test", "new_user")

        assert result == []


# ---------------------------------------------------------------------------
# delete_conversation
# ---------------------------------------------------------------------------


class TestDeleteConversation:
    """Tests for ConversationService.delete_conversation."""

    async def test_deletes_messages_from_mongodb(
        self, service: ConversationService, conversation_store: MagicMock
    ) -> None:
        """delete_conversation removes all messages from the MongoDB store."""
        await service.delete_conversation("org_test", "conv_test")

        conversation_store.delete_conversation.assert_awaited_once_with(
            org_id="org_test",
            conversation_id="conv_test",
        )

    async def test_deletes_metadata_from_postgresql(
        self, service: ConversationService, conversation_repo: MagicMock
    ) -> None:
        """delete_conversation removes the conversation record from PostgreSQL."""
        await service.delete_conversation("org_test", "conv_test")

        conversation_repo.delete.assert_awaited_once_with("conv_test")

    async def test_deletes_from_both_stores(
        self,
        service: ConversationService,
        conversation_store: MagicMock,
        conversation_repo: MagicMock,
    ) -> None:
        """delete_conversation performs coordinated deletion from MongoDB and PostgreSQL."""
        await service.delete_conversation("org_test", "conv_test")

        conversation_store.delete_conversation.assert_awaited_once()
        conversation_repo.delete.assert_awaited_once()

    async def test_returns_none(self, service: ConversationService) -> None:
        """delete_conversation has no return value (void operation)."""
        result = await service.delete_conversation("org_test", "conv_test")

        assert result is None
