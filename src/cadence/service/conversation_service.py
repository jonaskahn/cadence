"""Conversation service for managing conversation history.

This module provides conversation management using MongoDB for messages
and PostgreSQL for conversation metadata.
"""

import logging
from typing import Any, Dict, List
from uuid import UUID, uuid4

from cadence_sdk.types.sdk_messages import UvMessage

from cadence.constants import DEFAULT_MESSAGES_LIMIT
from cadence.repository.conversation_repository import ConversationRepository
from cadence.repository.message_repository import MessageRepository

logger = logging.getLogger(__name__)


class ConversationService:
    """Service for managing conversations and message history.

    Attributes:
        message_repo: MongoDB conversation store
        conversation_repo: PostgreSQL conversation repository
    """

    def __init__(
        self,
        message_repo: MessageRepository,
        conversation_repo: ConversationRepository,
    ):
        """Initialize conversation service.

        Args:
            message_repo: MongoDB message store
            conversation_repo: PostgreSQL conversation repository
        """
        self.message_repo = message_repo
        self.conversation_repo = conversation_repo

    async def get_history(
        self,
        org_id: str,
        conversation_id: str,
        limit: int = DEFAULT_MESSAGES_LIMIT,
    ) -> List[UvMessage]:
        """Get conversation message history.

        Args:
            org_id: Organization ID
            conversation_id: Conversation ID
            limit: Maximum messages to retrieve

        Returns:
            List of messages in chronological order
        """
        logger.debug(
            f"Loading conversation history: {conversation_id} (limit: {limit})"
        )

        messages = await self.message_repo.get_messages(
            org_id=org_id,
            conversation_id=conversation_id,
            limit=limit,
        )

        return messages

    async def save_message(
        self,
        org_id: str,
        conversation_id: str,
        message: UvMessage,
    ) -> None:
        """Save message to conversation history.

        Args:
            org_id: Organization ID
            conversation_id: Conversation ID
            message: Message to save
        """
        logger.debug(f"Saving message to conversation: {conversation_id}")

        await self.message_repo.save_message(
            org_id=org_id,
            conversation_id=conversation_id,
            message=message,
        )

    async def create_conversation(
        self,
        org_id: str,
        user_id: str,
        instance_id: str | UUID,
    ) -> str:
        """Create new conversation.

        Args:
            org_id: Organization ID
            user_id: User ID
            instance_id: Orchestrator instance ID

        Returns:
            Created conversation ID
        """
        conversation_id = str(uuid4())

        logger.info(f"Creating conversation: {conversation_id}")

        if isinstance(instance_id, str):
            instance_id = UUID(instance_id)

        await self.conversation_repo.create(
            conversation_id=conversation_id,
            org_id=org_id,
            user_id=user_id,
            instance_id=instance_id,
        )

        return conversation_id

    async def list_conversations(
        self,
        org_id: str,
        user_id: str,
    ) -> List[Dict[str, Any]]:
        """List user's conversations.

        Args:
            org_id: Organization ID
            user_id: User ID

        Returns:
            List of conversation metadata
        """
        logger.debug(f"Listing conversations for user: {user_id}")

        conversations = await self.conversation_repo.list_for_user(
            org_id=org_id,
            user_id=user_id,
        )

        return conversations

    async def delete_conversation(
        self,
        org_id: str,
        conversation_id: str,
    ) -> None:
        """Delete conversation and all messages.

        Args:
            org_id: Organization ID
            conversation_id: Conversation ID
        """
        logger.info(f"Deleting conversation: {conversation_id}")

        await self.message_repo.delete_conversation(
            org_id=org_id,
            conversation_id=conversation_id,
        )

        await self.conversation_repo.delete(conversation_id)
