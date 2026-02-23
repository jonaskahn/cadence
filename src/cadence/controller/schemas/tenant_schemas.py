"""Pydantic schemas for tenant management API."""

import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class TierQuota(BaseModel):
    """Quota limits for a subscription tier."""

    max_orchestrators: int
    max_members: int
    max_messages_per_month: int
    max_messages_per_day: int
    rate_limit_rpm: int
    rate_limit_burst: int
    max_llm_configs: int
    description: str = ""


class TierDefinitionResponse(BaseModel):
    """Single tier definition returned by GET /api/admin/tiers."""

    key: str  # e.g. "tier.free"
    tier_name: str  # e.g. "free"
    quota: TierQuota


class CreateOrganizationRequest(BaseModel):
    """Create organization request."""

    name: str = Field(..., min_length=1, description="Organization name")
    display_name: Optional[str] = None
    domain: str = Field(
        ..., min_length=1, description="Organization domain (unique, required)"
    )
    tier: Optional[str] = None
    description: Optional[str] = None
    contact_email: Optional[str] = None
    website: Optional[str] = None
    logo_url: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = None

    @field_validator("contact_email")
    @classmethod
    def validate_contact_email_format(cls, v: Optional[str]) -> Optional[str]:
        if v and not _EMAIL_RE.match(v):
            raise ValueError("Invalid email address")
        return v


class OrgProfileUpdateRequest(BaseModel):
    """Partial update for org profile (org_admin) — excludes domain, tier, status, name."""

    display_name: Optional[str] = None
    description: Optional[str] = None
    contact_email: Optional[str] = None
    website: Optional[str] = None
    logo_url: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = None

    @field_validator("contact_email")
    @classmethod
    def validate_contact_email_format(cls, v: Optional[str]) -> Optional[str]:
        if v and not _EMAIL_RE.match(v):
            raise ValueError("Invalid email address")
        return v


class UpdateOrganizationRequest(BaseModel):
    """Partial update for an organization (sys_admin only)."""

    name: Optional[str] = None
    display_name: Optional[str] = None
    domain: Optional[str] = Field(
        None, min_length=1, description="Organization domain (unique)"
    )
    tier: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    contact_email: Optional[str] = None
    website: Optional[str] = None
    logo_url: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = None

    @field_validator("contact_email")
    @classmethod
    def validate_contact_email_format(cls, v: Optional[str]) -> Optional[str]:
        if v and not _EMAIL_RE.match(v):
            raise ValueError("Invalid email address")
        return v


class OrganizationResponse(BaseModel):
    """Organization response."""

    org_id: str
    name: str
    status: str
    created_at: str
    display_name: Optional[str] = None
    domain: Optional[str] = None
    tier: str = "free"
    description: Optional[str] = None
    contact_email: Optional[str] = None
    website: Optional[str] = None
    logo_url: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = None


class OrgWithRoleResponse(BaseModel):
    """Organization response with the caller's role in that org."""

    org_id: str
    name: str
    status: str
    created_at: str
    role: str  # "sys_admin" | "org_admin" | "member"


class SetTenantSettingRequest(BaseModel):
    """Set org setting request."""

    key: str = Field(..., min_length=1, description="Setting key")
    value: Any = Field(..., description="Setting value")
    overridable: bool = False


class TenantSettingResponse(BaseModel):
    """Org setting response."""

    key: str
    value: Any
    value_type: str
    overridable: bool


class AddLLMConfigRequest(BaseModel):
    """Add LLM config request."""

    name: str = Field(..., min_length=1, description="Config name (unique per org)")
    provider: str = Field(
        ..., description="Provider (openai/anthropic/google/groq/azure)"
    )
    api_key: str = Field(..., min_length=1, description="API key")
    base_url: Optional[str] = Field(None, description="Custom base URL")
    additional_config: Optional[Dict[str, Any]] = Field(
        None, description="Provider-specific extra settings (e.g. Azure api_version)"
    )


class UpdateLLMConfigRequest(BaseModel):
    """Update LLM config request (provider is immutable)."""

    name: Optional[str] = Field(None, min_length=1, description="New config name")
    api_key: Optional[str] = Field(
        None, description="New API key; omit to keep existing"
    )
    base_url: Optional[str] = Field(None, description="Custom base URL; null to clear")
    additional_config: Optional[Dict[str, Any]] = Field(
        None, description="Provider-specific extra settings; null to clear"
    )


class ProviderModelResponse(BaseModel):
    """Single model entry from the provider model catalog."""

    model_id: str
    display_name: str
    aliases: List[str]


class LLMConfigResponse(BaseModel):
    """LLM config response (API key masked)."""

    id: str
    name: str
    provider: str
    base_url: Optional[str]
    additional_config: Optional[Dict[str, Any]]
    created_at: str


class CreateUserRequest(BaseModel):
    """Create user request (sys_admin only — creates a platform-level user)."""

    username: str = Field(..., min_length=1, description="Username")
    email: Optional[str] = Field(None, description="Email address")
    password: Optional[str] = Field(None, description="Initial password")

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: Optional[str]) -> Optional[str]:
        if v and not _EMAIL_RE.match(v):
            raise ValueError("Invalid email address")
        return v


class AddOrgMemberRequest(BaseModel):
    """Add existing user to an org (org_admin or sys_admin)."""

    user_id: str = Field(..., min_length=1, description="Existing user identifier")
    is_admin: bool = Field(False, description="Grant admin rights in this org")


class UserMembershipResponse(BaseModel):
    """User with membership response."""

    user_id: str
    username: str
    email: Optional[str]
    is_sys_admin: bool
    is_admin: bool
    created_at: Optional[str]
    is_deleted: bool


class UpdateUserRequest(BaseModel):
    """Update platform user request (sys_admin only)."""

    username: Optional[str] = Field(None, min_length=1, description="New username")
    email: Optional[str] = Field(None, description="New email address")
    is_sys_admin: Optional[bool] = Field(None, description="Grant or revoke sys_admin")

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: Optional[str]) -> Optional[str]:
        if v and not _EMAIL_RE.match(v):
            raise ValueError("Invalid email address")
        return v


class UpdateMembershipRequest(BaseModel):
    """Update org membership request."""

    is_admin: bool = Field(..., description="New org_admin value")


class FrameworkSupportedProvidersResponse(BaseModel):
    """Providers supported by a given orchestration framework."""

    framework_type: str
    supported_providers: Optional[List[str]]  # None = all providers supported
    supports_all: bool
    supported_modes: List[str]


class OrchestratorDefaultsRequest(BaseModel):
    """Request to set org-level orchestrator defaults."""

    default_llm_config_id: Optional[int] = None
    default_model_name: Optional[str] = None
    default_max_tokens: Optional[int] = None
    default_timeout: Optional[int] = None


class OrchestratorDefaultsResponse(BaseModel):
    """Effective orchestrator defaults for an org (global base merged with org overrides)."""

    default_llm_config_id: Optional[int] = None
    default_model_name: Optional[str] = None
    default_max_tokens: Optional[int] = None
    default_timeout: Optional[int] = None
