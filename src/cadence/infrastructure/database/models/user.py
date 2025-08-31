"""SQLAlchemy model for User entities."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String, UniqueConstraint

from .base import Base, TimestampMixin


class UserModel(Base, TimestampMixin):
    """SQLAlchemy model for User domain entity."""

    __tablename__ = "users"

    id = Column(String(255), primary_key=True)
    user_id = Column(String(255), nullable=False, comment="User identifier")
    org_id = Column(
        String(255),
        ForeignKey("organizations.org_id", ondelete="CASCADE"),
        nullable=False,
        comment="Organization identifier",
    )
    display_name = Column(String(255), comment="User display name")
    last_active = Column(DateTime, nullable=True, comment="Last activity timestamp")
    is_active = Column(Boolean, default=True, nullable=False, comment="User active status")

    __table_args__ = (
        UniqueConstraint("user_id", "org_id", name="uq_user_org"),
        Index("idx_user_org_active", "org_id", "is_active"),
        Index("idx_user_last_active", "last_active"),
        Index("idx_user_lookup", "user_id", "org_id"),
    )

    def to_domain_model(self):
        """Convert to domain model."""
        from ....domain.models.user import User

        return User(
            user_id=self.user_id,
            org_id=self.org_id,
            display_name=self.display_name,
            created_at=self.created_at,
            last_active=self.last_active,
            is_active=self.is_active,
        )

    @classmethod
    def from_domain_model(cls, user):
        """Create from domain model."""
        return cls(
            id=f"{user.org_id}:{user.user_id}",
            user_id=user.user_id,
            org_id=user.org_id,
            display_name=user.display_name,
            created_at=user.created_at,
            last_active=user.last_active,
            is_active=user.is_active,
        )
