"""Thread domain model for conversation management."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional


class ThreadStatus(Enum):
    """Lifecycle states for a thread."""

    ACTIVE = "active"
    ARCHIVED = "archived"


class Thread:
    """Conversation thread with token accounting and lifecycle management.

    Tracks cumulative token usage for cost estimation and enforces business rules
    around message acceptance based on lifecycle state.
    """

    def __init__(
        self,
        thread_id: Optional[str] = None,
        user_id: str = "anonymous",
        org_id: str = "public",
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        total_tokens: int = 0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        message_count: int = 0,
        status: ThreadStatus = ThreadStatus.ACTIVE,
    ):
        self.thread_id = thread_id or str(uuid.uuid4())
        self.user_id = user_id
        self.org_id = org_id
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()
        self.total_tokens = total_tokens
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.message_count = message_count
        self.status = status

    def can_accept_message(self) -> bool:
        """Return whether thread accepts new messages."""
        return self.status == ThreadStatus.ACTIVE

    def add_conversation_tokens(self, user_tokens: int, assistant_tokens: int) -> None:
        """Record tokens for newly added conversation."""
        if not self.can_accept_message():
            raise ValueError(f"Cannot add tokens to {self.status.value} thread")

        self.input_tokens += user_tokens
        self.output_tokens += assistant_tokens
        self.total_tokens = self.input_tokens + self.output_tokens
        self.message_count += 1
        self.updated_at = datetime.utcnow()

    def archive(self) -> None:
        """Transition thread to ARCHIVED state and update timestamp."""
        self.status = ThreadStatus.ARCHIVED
        self.updated_at = datetime.utcnow()

    def reactivate(self) -> None:
        """Transition thread back to ACTIVE state and update timestamp."""
        self.status = ThreadStatus.ACTIVE
        self.updated_at = datetime.utcnow()

    def get_cost_estimate(self, cost_per_1k_input: float = 0.001, cost_per_1k_output: float = 0.003) -> float:
        """Estimate cost for all messages in thread."""
        input_cost = (self.input_tokens / 1000) * cost_per_1k_input
        output_cost = (self.output_tokens / 1000) * cost_per_1k_output
        return input_cost + output_cost

    def to_dict(self) -> dict:
        """Serialize to dictionary with JSON-friendly values."""
        return {
            "thread_id": self.thread_id,
            "user_id": self.user_id,
            "org_id": self.org_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "total_tokens": self.total_tokens,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "message_count": self.message_count,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Thread":
        """Deserialize from a dictionary.

        Args:
            data: Mapping with thread data

        Returns:
            New Thread instance
        """
        return cls(
            thread_id=data["thread_id"],
            user_id=data["user_id"],
            org_id=data["org_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            total_tokens=data["total_tokens"],
            input_tokens=data["input_tokens"],
            output_tokens=data["output_tokens"],
            message_count=data["message_count"],
            status=ThreadStatus(data["status"]),
        )

    def __repr__(self) -> str:
        return f"Thread(thread_id={self.thread_id}, user_id={self.user_id}, status={self.status.value}, tokens={self.total_tokens})"
