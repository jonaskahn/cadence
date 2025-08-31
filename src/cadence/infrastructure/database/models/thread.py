"""SQLAlchemy model for Thread entities."""

from sqlalchemy import BigInteger, Column, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from ....domain.models.thread import ThreadStatus
from .base import Base, TimestampMixin


class ThreadModel(Base, TimestampMixin):
    """SQLAlchemy model for Thread domain entity with optimized conversation storage."""

    __tablename__ = "threads"

    thread_id = Column(String(255), primary_key=True, comment="Thread identifier")
    user_id = Column(String(255), nullable=False, comment="User identifier")
    org_id = Column(
        String(255),
        ForeignKey("organizations.org_id", ondelete="CASCADE"),
        nullable=False,
        comment="Organization identifier",
    )

    total_tokens = Column(BigInteger, default=0, nullable=False, comment="Total tokens used in thread")
    input_tokens = Column(BigInteger, default=0, nullable=False, comment="Input tokens used")
    output_tokens = Column(BigInteger, default=0, nullable=False, comment="Output tokens used")
    message_count = Column(Integer, default=0, nullable=False, comment="Number of conversation turns")

    status = Column(Enum(ThreadStatus), default=ThreadStatus.ACTIVE, nullable=False, comment="Thread status")

    __table_args__ = (
        Index("idx_thread_user_org", "user_id", "org_id"),
        Index("idx_thread_updated", "updated_at"),
        Index("idx_thread_status", "status"),
        Index("idx_thread_tokens", "total_tokens"),
        Index("idx_thread_user_status", "user_id", "status", "updated_at"),
        Index("idx_thread_org_analytics", "org_id", "created_at", "total_tokens"),
    )

    conversations = relationship(
        "ConversationModel",
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="ConversationModel.created_at",
    )

    def to_domain_model(self):
        """Convert to domain model."""
        from ....domain.models.thread import Thread

        return Thread(
            thread_id=self.thread_id,
            user_id=self.user_id,
            org_id=self.org_id,
            created_at=self.created_at,
            updated_at=self.updated_at,
            total_tokens=self.total_tokens,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            message_count=self.message_count,
            status=self.status,
        )

    @classmethod
    def from_domain_model(cls, thread):
        """Create from domain model."""
        return cls(
            thread_id=thread.thread_id,
            user_id=thread.user_id,
            org_id=thread.org_id,
            created_at=thread.created_at,
            updated_at=thread.updated_at,
            total_tokens=thread.total_tokens,
            input_tokens=thread.input_tokens,
            output_tokens=thread.output_tokens,
            message_count=thread.message_count,
            status=thread.status,
        )

    def update_from_domain_model(self, thread):
        """Update existing model from domain model."""
        self.updated_at = thread.updated_at
        self.total_tokens = thread.total_tokens
        self.input_tokens = thread.input_tokens
        self.output_tokens = thread.output_tokens
        self.message_count = thread.message_count
        self.status = thread.status
