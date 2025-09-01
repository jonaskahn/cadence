"""Thread repository interface and implementations."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from ....domain.models.thread import Thread, ThreadStatus


class ThreadRepository(ABC):
    """Abstract repository interface for Thread entities."""

    @abstractmethod
    async def create_thread(self, user_id: str, org_id: str) -> Thread:
        """Create a new thread."""
        pass

    @abstractmethod
    async def get_thread(self, thread_id: str) -> Optional[Thread]:
        """Get thread by ID."""
        pass

    @abstractmethod
    async def update_thread(self, thread: Thread) -> Thread:
        """Update an existing thread."""
        pass

    @abstractmethod
    async def archive_thread(self, thread_id: str) -> bool:
        """Archive a thread."""
        pass

    @abstractmethod
    async def list_threads(
        self,
        user_id: Optional[str] = None,
        org_id: Optional[str] = None,
        status: Optional[ThreadStatus] = None,
        limit: int = 20,
        offset: int = 0,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> List[Thread]:
        """List threads with filtering and pagination."""
        pass

    @abstractmethod
    async def count_threads(
        self, user_id: Optional[str] = None, org_id: Optional[str] = None, status: Optional[ThreadStatus] = None
    ) -> int:
        """Count threads matching filters."""
        pass

    @abstractmethod
    async def get_thread_stats(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive stats for a thread."""
        pass

    @abstractmethod
    async def update_thread_tokens(self, thread_id: str, user_tokens: int, assistant_tokens: int) -> bool:
        """Update thread token counters atomically."""
        pass


class InMemoryThreadRepository(ThreadRepository):
    """In-memory implementation of ThreadRepository for testing and development."""

    def __init__(self):
        self._threads: Dict[str, Thread] = {}

    async def create_thread(self, user_id: str, org_id: str) -> Thread:
        """Create a new thread."""
        thread = Thread(user_id=user_id, org_id=org_id)
        self._threads[thread.thread_id] = thread
        return thread

    async def get_thread(self, thread_id: str) -> Optional[Thread]:
        """Get thread by ID."""
        return self._threads.get(thread_id)

    async def update_thread(self, thread: Thread) -> Thread:
        """Update an existing thread."""
        if thread.thread_id not in self._threads:
            raise ValueError(f"Thread {thread.thread_id} not found")

        thread.updated_at = datetime.utcnow()
        self._threads[thread.thread_id] = thread
        return thread

    async def archive_thread(self, thread_id: str) -> bool:
        """Archive a thread."""
        thread = self._threads.get(thread_id)
        if not thread:
            return False

        thread.archive()
        return True

    async def list_threads(
        self,
        user_id: Optional[str] = None,
        org_id: Optional[str] = None,
        status: Optional[ThreadStatus] = None,
        limit: int = 20,
        offset: int = 0,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> List[Thread]:
        """List threads with filtering and pagination."""
        filtered_threads = []
        for thread in self._threads.values():
            if user_id and thread.user_id != user_id:
                continue
            if org_id and thread.org_id != org_id:
                continue
            if status and thread.status != status:
                continue
            filtered_threads.append(thread)

        reverse = sort_order.lower() == "desc"
        if sort_by == "created_at":
            filtered_threads.sort(key=lambda t: t.created_at, reverse=reverse)
        elif sort_by == "updated_at":
            filtered_threads.sort(key=lambda t: t.updated_at, reverse=reverse)
        elif sort_by == "total_tokens":
            filtered_threads.sort(key=lambda t: t.total_tokens, reverse=reverse)
        else:
            filtered_threads.sort(key=lambda t: t.updated_at, reverse=reverse)

        return filtered_threads[offset : offset + limit]

    async def count_threads(
        self, user_id: Optional[str] = None, org_id: Optional[str] = None, status: Optional[ThreadStatus] = None
    ) -> int:
        """Count threads matching filters."""
        count = 0
        for thread in self._threads.values():
            if user_id and thread.user_id != user_id:
                continue
            if org_id and thread.org_id != org_id:
                continue
            if status and thread.status != status:
                continue
            count += 1
        return count

    async def get_thread_stats(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive stats for a thread."""
        thread = self._threads.get(thread_id)
        if not thread:
            return None

        return {
            "thread_id": thread.thread_id,
            "total_tokens": thread.total_tokens,
            "input_tokens": thread.input_tokens,
            "output_tokens": thread.output_tokens,
            "message_count": thread.message_count,
            "status": thread.status.value,
            "created_at": thread.created_at.isoformat(),
            "updated_at": thread.updated_at.isoformat(),
            "estimated_cost": thread.get_cost_estimate(),
        }

    async def update_thread_tokens(self, thread_id: str, user_tokens: int, assistant_tokens: int) -> bool:
        """Update thread token counters atomically."""
        thread = self._threads.get(thread_id)
        if not thread:
            return False

        try:
            thread.add_conversation_tokens(user_tokens, assistant_tokens)
            return True
        except ValueError:
            return False

    def clear_all(self) -> None:
        """Clear all threads (for testing)."""
        self._threads.clear()

    def get_all_threads(self) -> List[Thread]:
        """Get all threads (for testing)."""
        return list(self._threads.values())
