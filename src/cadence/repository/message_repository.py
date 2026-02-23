"""Conversation storage in MongoDB.

Stores conversation messages in MongoDB for efficient retrieval of
large message histories. Uses organization-specific databases for
tenant isolation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from cadence_sdk import UvMessage

from cadence.constants import DEFAULT_MESSAGES_LIMIT

if TYPE_CHECKING:
    from cadence.infrastructure.persistence.mongodb.client import MongoDBClient


class MessageRepository:
    """MongoDB store for conversation messages.

    Each organization has its own database with a 'messages' collection.
    Messages are stored with conversation_id for easy retrieval.

    Attributes:
        client: MongoDB client for multi-tenant database access
    """

    MESSAGES_COLLECTION = "messages"

    def __init__(self, client: MongoDBClient):
        self.client = client

    def _get_messages_collection(self, org_id: str):
        """Get messages collection for an organization.

        Args:
            org_id: Organization identifier

        Returns:
            Messages collection
        """
        return self.client.get_database(org_id)[self.MESSAGES_COLLECTION]

    async def save_message(
        self,
        org_id: str,
        conversation_id: str,
        message: UvMessage,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Save message to conversation.

        Args:
            org_id: Organization identifier
            conversation_id: Conversation identifier
            message: UvMessage instance to save
            metadata: Optional additional metadata

        Returns:
            MongoDB document ID
        """
        messages_coll = self._get_messages_collection(org_id)

        message_doc = {
            "conversation_id": conversation_id,
            "message": message.to_dict(),
            "created_at": datetime.now(timezone.utc),
        }

        if metadata:
            message_doc["metadata"] = metadata

        result = await messages_coll.insert_one(message_doc)
        return str(result.inserted_id)

    async def get_messages(
        self,
        org_id: str,
        conversation_id: str,
        limit: int = DEFAULT_MESSAGES_LIMIT,
        skip: int = 0,
    ) -> List[UvMessage]:
        """Retrieve messages for conversation.

        Args:
            org_id: Organization identifier
            conversation_id: Conversation identifier
            limit: Maximum number of messages to return
            skip: Number of messages to skip

        Returns:
            List of UvMessage instances in chronological order
        """
        messages_coll = self._get_messages_collection(org_id)

        cursor = (
            messages_coll.find({"conversation_id": conversation_id})
            .sort("created_at", 1)
            .skip(skip)
            .limit(limit)
        )

        messages = []
        async for doc in cursor:
            message_data = doc["message"]
            messages.append(UvMessage.from_dict(message_data))

        return messages

    async def delete_conversation(self, org_id: str, conversation_id: str) -> int:
        """Delete all messages in conversation.

        Args:
            org_id: Organization identifier
            conversation_id: Conversation identifier

        Returns:
            Number of messages deleted
        """
        messages_coll = self._get_messages_collection(org_id)
        result = await messages_coll.delete_many({"conversation_id": conversation_id})
        return result.is_deleted_count

    async def get_message_count(self, org_id: str, conversation_id: str) -> int:
        """Get total message count for conversation.

        Args:
            org_id: Organization identifier
            conversation_id: Conversation identifier

        Returns:
            Number of messages
        """
        messages_coll = self._get_messages_collection(org_id)
        return await messages_coll.count_documents({"conversation_id": conversation_id})

    async def create_indexes(self, org_id: str) -> None:
        """Create database indexes for performance.

        Should be called during application initialization for each organization.

        Args:
            org_id: Organization identifier
        """
        messages_coll = self._get_messages_collection(org_id)
        await messages_coll.create_index([("conversation_id", 1), ("created_at", 1)])
        await messages_coll.create_index("created_at")
