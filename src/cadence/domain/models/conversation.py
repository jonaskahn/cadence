"""Conversation domain model for optimized conversation storage."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field


class Conversation(BaseModel):
    """User-assistant exchange with token and metadata tracking.

    Represents one conversation turn with optimized storage for context reconstruction.
    """

    id: Optional[str | int] = Field(default_factory=lambda: str(uuid.uuid4()), description="Conversation ID")
    thread_id: str | int = Field(description="Thread ID")
    user_message: str = Field(description="User input message")
    assistant_message: Optional[str] = Field(description="Assistant response message")
    user_tokens: Optional[int] = Field(default=0, description="User tokens")
    assistant_tokens: Optional[int] = Field(default=0, description="Assistant tokens")
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Created_at")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Metadata")

    @property
    def total_tokens(self) -> int:
        """Return total tokens for this exchange."""
        return self.user_tokens + self.assistant_tokens

    def add_metadata(self, key: str, value: Any) -> None:
        """Add or update metadata entry."""
        self.metadata[key] = value

    def get_processing_time(self) -> Optional[float]:
        """Return processing time in seconds, if available."""
        return self.metadata.get("processing_time")

    def get_tools_used(self) -> list:
        """Return tools used during processing."""
        return self.metadata.get("tools_used", [])

    def get_agent_hops(self) -> int:
        """Return number of agent-to-agent hops."""
        return self.metadata.get("agent_hops", 0)

    def get_cost_estimate(self, cost_per_1k_input: float = 0.001, cost_per_1k_output: float = 0.003) -> float:
        """Estimate token cost for this exchange."""
        input_cost = (self.user_tokens / 1000) * cost_per_1k_input
        output_cost = (self.assistant_tokens / 1000) * cost_per_1k_output
        return input_cost + output_cost

    def to_langgraph_messages(self) -> list:
        """Convert to LangGraph message sequence."""
        return [HumanMessage(content=self.user_message), AIMessage(content=self.assistant_message)]

    def to_dict(self) -> dict:
        """Serialize to plain dictionary."""
        return {
            "conversation_id": self.id,
            "thread_id": self.thread_id,
            "user_message": self.user_message,
            "assistant_message": self.assistant_message,
            "user_tokens": self.user_tokens,
            "assistant_tokens": self.assistant_tokens,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Conversation":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            thread_id=data["thread_id"],
            user_message=data["user_message"],
            assistant_message=data["assistant_message"],
            user_tokens=data["user_tokens"],
            assistant_tokens=data["assistant_tokens"],
            created_at=datetime.fromisoformat(data["created_at"]),
            metadata=data.get("metadata", {}),
        )

    def __repr__(self) -> str:
        return f"Conversation(id={self.id}, thread_id={self.thread_id}, tokens={self.total_tokens})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Conversation):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
