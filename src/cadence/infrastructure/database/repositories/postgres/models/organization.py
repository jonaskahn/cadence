"""SQLAlchemy model for Organization entities."""

from sqlalchemy import JSON, BigInteger, Boolean, Column, Index, String

from .base import Base, TimestampMixin


class OrganizationModel(Base, TimestampMixin):
    """SQLAlchemy model for Organization domain entity."""

    __tablename__ = "organizations"

    org_id = Column(String(255), primary_key=True, comment="Organization identifier")
    name = Column(String(500), nullable=False, comment="Organization name")
    is_active = Column(Boolean, default=True, nullable=False, comment="Organization active status")
    settings = Column(JSON, comment="Organization-specific settings")
    total_tokens_used = Column(BigInteger, default=0, nullable=False, comment="Total tokens consumed")
    monthly_token_limit = Column(BigInteger, nullable=True, comment="Monthly token usage limit")

    __table_args__ = (
        Index("idx_org_active", "is_active"),
        Index("idx_org_tokens", "total_tokens_used"),
    )

    def to_domain_model(self):
        """Convert to domain model."""
        from ....domain.models.organization import Organization

        return Organization(
            org_id=self.org_id,
            name=self.name,
            created_at=self.created_at,
            is_active=self.is_active,
            settings=self.settings or {},
            total_tokens_used=self.total_tokens_used,
            monthly_token_limit=self.monthly_token_limit,
        )

    @classmethod
    def from_domain_model(cls, organization):
        """Create from domain model."""
        return cls(
            org_id=organization.org_id,
            name=organization.name,
            created_at=organization.created_at,
            is_active=organization.is_active,
            settings=organization.settings,
            total_tokens_used=organization.total_tokens_used,
            monthly_token_limit=organization.monthly_token_limit,
        )
