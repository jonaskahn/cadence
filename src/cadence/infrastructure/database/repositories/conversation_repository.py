"""Conversation repository interface and implementations."""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ....domain.models.conversation import Conversation


class ConversationRepository(ABC):
    """Abstract repository interface for Conversation entities.

    Implements the optimized storage strategy:
    - Stores only user input + final AI response (not intermediate LangGraph steps)
    - Maintains conversation continuity for LangGraph context
    """

    @abstractmethod
    async def save(self, conversation: Conversation) -> Conversation:
        """Save a conversation  atomically with thread token updates."""
        pass

    @abstractmethod
    async def get(self, id: str) -> Optional[Conversation]:
        """Get a conversation by ID."""
        pass

    @abstractmethod
    async def get_conversation_history(
        self, thread_id: str, limit: int = 50, before_id: Optional[str] = None
    ) -> List[Conversation]:
        """Get conversation history for a thread, ordered by creation time."""
        pass

    @abstractmethod
    async def get_thread_conversations_count(self, thread_id: str) -> int:
        """Get total number of  in a thread."""
        pass

    @abstractmethod
    async def get_recent_conversations(
        self, user_id: Optional[str] = None, org_id: Optional[str] = None, limit: int = 10, hours_back: int = 24
    ) -> List[Conversation]:
        """Get recent conversation across threads."""
        pass

    @abstractmethod
    async def search_conversations(
        self, query: str, thread_id: Optional[str] = None, user_id: Optional[str] = None, limit: int = 20
    ) -> List[Conversation]:
        """Search conversation by content."""
        pass

    @abstractmethod
    async def get_conversation_statistics(
        self,
        thread_id: Optional[str] = None,
        user_id: Optional[str] = None,
        org_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get conversation statistics."""
        pass

    @abstractmethod
    async def delete_old_conversations(self, older_than_days: int) -> int:
        """Delete conversation older than specified days."""
        pass


class InMemoryConversationRepository(ConversationRepository):
    """In-memory implementation of ConversationRepository for testing and development."""

    def __init__(self, thread_repository=None):
        self._conversations: Dict[str, Conversation] = {}
        self._thread_repository = thread_repository

    async def save(self, conversation: Conversation) -> Conversation:
        """Save a conversation atomically with thread token updates."""
        self._conversations[conversation.id] = conversation

        if self._thread_repository:
            await self._thread_repository.update_thread_tokens(
                conversation.thread_id, conversation.user_tokens, conversation.assistant_tokens
            )

        return conversation

    async def get(self, id: str) -> Optional[Conversation]:
        """Get a conversation by ID."""
        return self._conversations.get(id)

    async def get_conversation_history(
        self, thread_id: str, limit: int = 50, before_id: Optional[str] = None
    ) -> List[Conversation]:
        """Get conversation history for a thread, ordered by creation time."""
        thread_conversations = [conv for conv in self._conversations.values() if conv.thread_id == thread_id]

        thread_conversations.sort(key=lambda c: c.created_at)

        if before_id:
            before_conversation = self._conversations.get(before_id)
            if before_conversation:
                thread_conversations = [
                    conv for conv in thread_conversations if conv.created_at < before_conversation.created_at
                ]

        return thread_conversations[-limit:] if len(thread_conversations) > limit else thread_conversations

    async def get_thread_conversations_count(self, thread_id: str) -> int:
        """Get total number of conversations in a thread."""
        return sum(1 for conv in self._conversations.values() if conv.thread_id == thread_id)

    async def get_recent_conversations(
        self, user_id: Optional[str] = None, org_id: Optional[str] = None, limit: int = 10, hours_back: int = 24
    ) -> List[Conversation]:
        """Get recent conversations across threads."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)

        filtered_conversations = []
        for conv in self._conversations.values():
            if conv.created_at < cutoff_time:
                continue

            filtered_conversations.append(conv)

        filtered_conversations.sort(key=lambda c: c.created_at, reverse=True)

        return filtered_conversations[:limit]

    async def search_conversations(
        self, query: str, thread_id: Optional[str] = None, user_id: Optional[str] = None, limit: int = 20
    ) -> List[Conversation]:
        """Search conversations by content."""
        query_lower = query.lower()
        matching_conversations = []

        for conv in self._conversations.values():
            if thread_id and conv.thread_id != thread_id:
                continue

            if query_lower in conv.user_message.lower() or query_lower in conv.assistant_message.lower():
                matching_conversations.append(conv)

        matching_conversations.sort(key=lambda c: c.created_at, reverse=True)

        return matching_conversations[:limit]

    async def get_conversation_statistics(
        self,
        thread_id: Optional[str] = None,
        user_id: Optional[str] = None,
        org_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get conversation statistics."""
        filtered_conversations = []

        for conv in self._conversations.values():
            if thread_id and conv.thread_id != thread_id:
                continue
            if start_date and conv.created_at < start_date:
                continue
            if end_date and conv.created_at > end_date:
                continue
            filtered_conversations.append(conv)

        if not filtered_conversations:
            return {
                "total_conversations": 0,
                "total_tokens": 0,
                "average_tokens_per_conversation": 0.0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "estimated_cost": 0.0,
                "unique_threads": 0,
            }

        total_tokens = sum(conv.total_tokens for conv in filtered_conversations)
        total_input_tokens = sum(conv.user_tokens for conv in filtered_conversations)
        total_output_tokens = sum(conv.assistant_tokens for conv in filtered_conversations)
        unique_threads = len(set(conv.thread_id for conv in filtered_conversations))

        return {
            "total_conversations": len(filtered_conversations),
            "total_tokens": total_tokens,
            "average_tokens_per_conversation": total_tokens / len(filtered_conversations),
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "estimated_cost": sum(conv.get_cost_estimate() for conv in filtered_conversations),
            "unique_threads": unique_threads,
        }

    async def delete_old_conversations(self, older_than_days: int) -> int:
        """Delete conversations older than specified days."""
        cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)

        old_conversation_ids = [
            conv_id for conv_id, conv in self._conversations.items() if conv.created_at < cutoff_date
        ]

        for conv_id in old_conversation_ids:
            del self._conversations[conv_id]

        return len(old_conversation_ids)

    def clear_all(self) -> None:
        """Clear all turns (for testing)."""
        self._conversations.clear()

    def get_all_conversations(self) -> List[Conversation]:
        """Get all conversations (for testing)."""
        return list(self._conversations.values())

    def get_storage_efficiency_estimate(self) -> Dict[str, Any]:
        """Estimate storage efficiency compared to full message storage.

        This demonstrates the significant storage reduction achieved by storing
        only user input + final AI response instead of intermediate steps.
        """
        if not self._conversations:
            return {"efficiency_percentage": 0.0, "estimated_savings": 0.0}

        current_storage = 0
        for conv in self._conversations.values():
            current_storage += len(conv.user_message) + len(conv.assistant_message) + 100

        estimated_full_storage = current_storage * 4

        efficiency_percentage = ((estimated_full_storage - current_storage) / estimated_full_storage) * 100

        return {
            "current_storage_bytes": current_storage,
            "estimated_full_storage_bytes": estimated_full_storage,
            "efficiency_percentage": efficiency_percentage,
            "estimated_savings_bytes": estimated_full_storage - current_storage,
        }
