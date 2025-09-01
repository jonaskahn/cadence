"""User domain model for user management."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class User(BaseModel):
    """User entity with identity, lifecycle, and activity tracking."""

    def __init__(
        self,
        user_id: str,
        org_id: str = "public",
        display_name: Optional[str] = None,
        created_at: Optional[datetime] = None,
        last_active: Optional[datetime] = None,
        is_active: bool = True,
        **data: Any,
    ):
        super().__init__(**data)
        if not user_id.strip():
            raise ValueError("user_id cannot be empty")
        if not org_id.strip():
            raise ValueError("org_id cannot be empty")

        self.user_id = user_id.strip()
        self.org_id = org_id.strip()
        self.display_name = display_name or user_id
        self.created_at = created_at or datetime.utcnow()
        self.last_active = last_active
        self.is_active = is_active

    def update_last_active(self) -> None:
        """Set last_active to current UTC timestamp."""
        self.last_active = datetime.utcnow()

    def deactivate(self) -> None:
        """Mark user account as inactive."""
        self.is_active = False

    def activate(self) -> None:
        """Mark user account as active."""
        self.is_active = True

    def can_create_threads(self) -> bool:
        """Return True if user is allowed to create threads."""
        return self.is_active

    def to_dict(self) -> dict:
        """Serialize to dictionary with JSON-friendly values."""
        return {
            "user_id": self.user_id,
            "org_id": self.org_id,
            "display_name": self.display_name,
            "created_at": self.created_at.isoformat(),
            "last_active": self.last_active.isoformat() if self.last_active else None,
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        """Deserialize from dictionary."""
        return cls(
            user_id=data["user_id"],
            org_id=data["org_id"],
            display_name=data.get("display_name"),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_active=datetime.fromisoformat(data["last_active"]) if data.get("last_active") else None,
            is_active=data.get("is_active", True),
        )

    def __repr__(self) -> str:
        return f"User(user_id={self.user_id}, org_id={self.org_id}, active={self.is_active})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, User):
            return False
        return self.user_id == other.user_id and self.org_id == other.org_id

    def __hash__(self) -> int:
        return hash((self.user_id, self.org_id))
