"""SQLAlchemy model for Conversation entities."""

from sqlalchemy import JSON, Column, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin


class ConversationModel(Base, TimestampMixin):
    """SQLAlchemy model for Conversation.

    This model stores only user input + final AI response (not intermediate LangGraph steps)
    achieving significant storage cost reduction while preserving conversation context.
    """

    __tablename__ = "conversations"

    id = Column(String(255), primary_key=True, comment="Conversation identifier")
    thread_id = Column(
        String(255),
        ForeignKey("threads.thread_id", ondelete="CASCADE"),
        nullable=False,
        comment="Thread this conversation belongs to",
    )

    user_message = Column(Text, nullable=False, comment="User message content")
    assistant_message = Column(Text, nullable=False, comment="Final AI response content")

    user_tokens = Column(Integer, nullable=False, comment="Tokens used for user message")
    assistant_tokens = Column(Integer, nullable=False, comment="Tokens used for assistant response")

    conversation_metadata = Column(JSON, comment="Conversation metadata (tools used, processing time, etc.)")

    __table_args__ = (
        Index("idx_conversation_thread_created", "thread_id", "created_at"),
        Index("idx_conversation_created", "created_at"),
        Index("idx_conversation_tokens", "user_tokens", "assistant_tokens"),
        # Full-text search indexes for content search (PostgreSQL specific)
        # These will be created conditionally based on database type
    )

    thread = relationship("ThreadModel", back_populates="conversations")

    def to_domain_model(self):
        """Convert to domain model."""
        from ....domain.models.conversation import Conversation

        return Conversation(
            conversation_id=self.conversation_id,
            thread_id=self.thread_id,
            user_message=self.user_message,
            assistant_message=self.assistant_message,
            user_tokens=self.user_tokens,
            assistant_tokens=self.assistant_tokens,
            created_at=self.created_at,
            metadata=self.conversation_metadata or {},
        )

    @classmethod
    def from_domain_model(cls, conversation):
        """Create from domain model."""
        return cls(
            conversation_id=conversation.conversation_id,
            thread_id=conversation.thread_id,
            user_message=conversation.user_message,
            assistant_message=conversation.assistant_message,
            user_tokens=conversation.user_tokens,
            assistant_tokens=conversation.assistant_tokens,
            created_at=conversation.created_at,
            conversation_metadata=conversation.metadata,
        )

    @property
    def total_tokens(self) -> int:
        """Calculate total tokens for this conversation."""
        return self.user_tokens + self.assistant_tokens

    def get_storage_size_estimate(self) -> int:
        """Estimate storage size in bytes for this conversation."""
        return (
            len(self.user_message.encode("utf-8"))
            + len(self.assistant_message.encode("utf-8"))
            + len(str(self.conversation_metadata).encode("utf-8"))
            + 100
        )
