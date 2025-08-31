"""Organization domain model for multi-tenancy support."""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel


class Organization(BaseModel):
    """Organization entity with multi-tenancy and usage controls.

    Captures tenant identity, lifecycle state, configurable settings, and
    aggregate token usage for quota enforcement.
    """

    def __init__(
        self,
        org_id: str,
        name: str,
        created_at: Optional[datetime] = None,
        is_active: bool = True,
        settings: Optional[Dict[str, Any]] = None,
        total_tokens_used: int = 0,
        monthly_token_limit: Optional[int] = None,
        **data: Any,
    ):
        super().__init__(**data)
        if not org_id.strip():
            raise ValueError("org_id cannot be empty")
        if not name.strip():
            raise ValueError("organization name cannot be empty")

        self.org_id = org_id.strip()
        self.name = name.strip()
        self.created_at = created_at or datetime.utcnow()
        self.is_active = is_active
        self.settings = settings or {}
        self.total_tokens_used = total_tokens_used
        self.monthly_token_limit = monthly_token_limit

    def can_create_threads(self) -> bool:
        """Return whether org can create new threads."""
        if not self.is_active:
            return False

        if self.monthly_token_limit and self.total_tokens_used >= self.monthly_token_limit:
            return False

        return True

    def add_token_usage(self, tokens: int) -> None:
        """Increase cumulative token usage."""
        if tokens < 0:
            raise ValueError("Token usage must be non-negative")
        self.total_tokens_used += tokens

    def get_token_usage_percentage(self) -> Optional[float]:
        """Return usage as percentage of monthly limit."""
        if not self.monthly_token_limit:
            return None
        return (self.total_tokens_used / self.monthly_token_limit) * 100

    def is_approaching_limit(self, threshold: float = 80.0) -> bool:
        """Return True if usage is at or above threshold percent."""
        usage_pct = self.get_token_usage_percentage()
        return usage_pct is not None and usage_pct >= threshold

    def reset_monthly_usage(self) -> None:
        """Reset the accumulated token usage to zero."""
        self.total_tokens_used = 0

    def update_setting(self, key: str, value: Any) -> None:
        """Set or update a setting value.

        Args:
            key: Setting name to update.
            value: New value. Should be JSON-serializable if persisted.
        """
        self.settings[key] = value

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Return a setting value or default when missing.

        Args:
            key: Setting name to read.
            default: Value to return when the key is not present.

        Returns:
            The setting value if it exists, otherwise `default`.
        """
        return self.settings.get(key, default)

    def deactivate(self) -> None:
        """Mark the organization as inactive."""
        self.is_active = False

    def activate(self) -> None:
        """Mark the organization as active."""
        self.is_active = True

    def to_dict(self) -> dict:
        """Serialize to a plain dictionary suitable for JSON storage.

        Returns:
            A mapping with primitive values. Timestamps are rendered in ISO
            8601 format.
        """
        return {
            "org_id": self.org_id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "is_active": self.is_active,
            "settings": self.settings,
            "total_tokens_used": self.total_tokens_used,
            "monthly_token_limit": self.monthly_token_limit,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Organization":
        """Deserialize from a dictionary.

        Args:
            data: Mapping with keys org_id, name, created_at (ISO 8601), and
                optional is_active, settings, total_tokens_used,
                monthly_token_limit.

        Returns:
            A new Organization instance.
        """
        return cls(
            org_id=data["org_id"],
            name=data["name"],
            created_at=datetime.fromisoformat(data["created_at"]),
            is_active=data.get("is_active", True),
            settings=data.get("settings", {}),
            total_tokens_used=data.get("total_tokens_used", 0),
            monthly_token_limit=data.get("monthly_token_limit"),
        )

    def __repr__(self) -> str:
        return f"Organization(org_id={self.org_id}, name={self.name}, active={self.is_active})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Organization):
            return False
        return self.org_id == other.org_id

    def __hash__(self) -> int:
        return hash(self.org_id)
