from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import select

if TYPE_CHECKING:
    from cadence.infrastructure.persistence.postgresql.client import PostgreSQLClient

from cadence.infrastructure.persistence.postgresql.models import Conversation


class ConversationRepository:
    """Repository for conversation metadata operations.

    Attributes:
        client: PostgreSQL client for database access
    """

    def __init__(self, client: PostgreSQLClient):
        self.client = client

    async def create(
        self,
        conversation_id: str | UUID,
        org_id: str | UUID,
        user_id: str | UUID,
        instance_id: Optional[UUID] = None,
    ) -> Conversation:
        """Create new conversation.

        Args:
            conversation_id: Conversation identifier (UUID or string)
            org_id: Organization identifier (UUID or string)
            user_id: User identifier (UUID or string)
            instance_id: Optional orchestrator instance ID

        Returns:
            Created Conversation instance
        """
        if isinstance(conversation_id, str):
            conversation_id = UUID(conversation_id)
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        async with self.client.session() as session:
            conversation = Conversation(
                id=conversation_id,
                org_id=org_id,
                user_id=user_id,
                instance_id=instance_id,
            )
            session.add(conversation)
            await session.flush()
            return conversation

    async def get_by_id(self, conversation_id: str | UUID) -> Optional[Conversation]:
        """Retrieve conversation by ID.

        Args:
            conversation_id: Conversation identifier (UUID or string)

        Returns:
            Conversation instance or None
        """
        if isinstance(conversation_id, str):
            conversation_id = UUID(conversation_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )
            return result.scalar_one_or_none()

    async def list_for_user(
        self, org_id: str | UUID, user_id: str | UUID
    ) -> List[Conversation]:
        """List conversations for user within an organization.

        Args:
            org_id: Organization identifier (UUID or string)
            user_id: User identifier (UUID or string)

        Returns:
            List of Conversation instances
        """
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(Conversation).where(
                    Conversation.org_id == org_id,
                    Conversation.user_id == user_id,
                    Conversation.is_deleted.is_(False),
                )
            )
            return list(result.scalars().all())

    async def update_title(self, conversation_id: str | UUID, title: str) -> None:
        """Update conversation title.

        Args:
            conversation_id: Conversation identifier (UUID or string)
            title: New title
        """
        if isinstance(conversation_id, str):
            conversation_id = UUID(conversation_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )
            conversation = result.scalar_one_or_none()
            if conversation:
                conversation.title = title
                await session.flush()

    async def delete(self, conversation_id: str | UUID) -> bool:
        """Soft-delete a conversation.

        Args:
            conversation_id: Conversation identifier (UUID or string)

        Returns:
            True if found and soft-deleted, False if not found
        """
        if isinstance(conversation_id, str):
            conversation_id = UUID(conversation_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )
            conversation = result.scalar_one_or_none()
            if not conversation:
                return False
            conversation.is_deleted = True
            await session.flush()
            return True
