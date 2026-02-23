"""SQLAlchemy async models for Cadence PostgreSQL database.

Defines all database tables for the Cadence multi-tenant platform:
- Global settings (Tier 2)
- Organizations and organization-specific settings (Tier 3)
- LLM configurations with encrypted API keys (BYOK)
- Orchestrator instances (Tier 4)
- Users, org memberships, and conversations

All timestamps use UTC. All primary keys use UUID (except auto-increment surrogate
keys on join/settings tables). All tables include audit columns (created_by,
updated_by) and soft-delete columns (deleted, deleted_at, deleted_by).
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import declarative_base, relationship

BaseModel = declarative_base()


def utc_now() -> datetime:
    """Get current UTC timestamp."""
    return datetime.now(timezone.utc)


class GlobalSettings(BaseModel):
    """Global configuration settings (Tier 2)."""

    __tablename__ = "global_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(255), nullable=False, unique=True)
    value = Column(JSONB, nullable=False)
    value_type = Column(String(50), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)


class Organization(BaseModel):
    """Tenant organization."""

    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)

    settings = relationship(
        "OrganizationSettings",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    llm_configs = relationship(
        "OrganizationLLMConfig",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    plugins = relationship(
        "OrganizationPlugin",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    instances = relationship(
        "OrchestratorInstance",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    memberships = relationship(
        "UserOrgMembership",
        back_populates="organization",
        cascade="all, delete-orphan",
    )


class OrganizationSettings(BaseModel):
    """Organization-specific settings (Tier 3)."""

    __tablename__ = "organization_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    key = Column(String(255), nullable=False)
    value = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)

    organization = relationship("Organization", back_populates="settings")

    __table_args__ = (
        UniqueConstraint("org_id", "key", name="uq_org_setting_key"),
        Index("idx_org_settings_org_id", "org_id"),
    )


class OrganizationLLMConfig(BaseModel):
    """Organization LLM API configuration (BYOK - Bring Your Own Key).

    Stores API keys for LLM providers. Organizations provide their own keys;
    the platform provides no defaults. api_key is stored as-is (encrypt at
    service level if needed). additional_config holds provider-specific extras
    (e.g. Azure deployment_id, api_version).

    A config cannot be soft-deleted while referenced by an active orchestrator.
    Soft-deleted configs are invisible to the LLM factory.
    Name is unique per org among non-deleted rows (allows reuse after soft-delete).

    Attributes:
        id: Primary key
        org_id: Organization identifier
        name: Configuration name — unique per org among non-deleted rows
        provider: LLM provider (openai, anthropic, google, azure, etc.)
        api_key: API key (store encrypted at service level)
        base_url: Optional custom base URL for provider
        additional_config: Provider-specific extra configuration (JSONB)
        created_at / updated_at: Timestamps
        created_by / updated_by: Audit user IDs
        is_deleted : Soft-delete fields
    """

    __tablename__ = "organization_llm_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(255), nullable=False)
    provider = Column(String(50), nullable=False)
    api_key = Column(Text, nullable=False)
    base_url = Column(String(512), nullable=True)
    additional_config = Column(JSONB, nullable=True, default=dict)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=True
    )
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)

    organization = relationship("Organization", back_populates="llm_configs")

    __table_args__ = (
        Index(
            "uq_org_llm_config_name_active",
            "org_id",
            "name",
            unique=True,
            postgresql_where=text("is_deleted = FALSE"),
        ),
        Index(
            "uq_org_llm_config_provider_key_active",
            "org_id",
            "provider",
            "api_key",
            unique=True,
            postgresql_where=text("is_deleted = FALSE"),
        ),
        Index("idx_org_llm_configs_org_id", "org_id"),
    )


class OrganizationPlugin(BaseModel):
    """Organization plugin activation."""

    __tablename__ = "organization_plugins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    plugin_pid = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="active")
    config = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=True
    )
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)

    organization = relationship("Organization", back_populates="plugins")

    __table_args__ = (
        UniqueConstraint("org_id", "plugin_pid", name="uq_org_plugin_pid"),
        Index("idx_org_plugins_org_id", "org_id"),
    )


class OrchestratorInstance(BaseModel):
    """Orchestrator instance configuration (Tier 4).

    Soft-delete is managed via the status column ('deleted') for backward
    compatibility with pool eviction logic, plus the standard deleted flag
    for cross-table consistency.
    """

    __tablename__ = "orchestrator_instances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(255), nullable=False)
    framework_type = Column(String(50), nullable=False)
    mode = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False, default="active")
    config = Column(JSONB, nullable=False, default=dict)
    tier = Column(String(20), nullable=False, default="cold")
    plugin_settings = Column(JSONB, nullable=True, default=dict)
    config_hash = Column(String(64), nullable=True)
    last_accessed_at = Column(DateTime(timezone=True), default=utc_now)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)

    organization = relationship("Organization", back_populates="instances")
    conversations = relationship("Conversation", back_populates="instance")

    __table_args__ = (
        Index("idx_orchestrator_instances_org_id", "org_id"),
        Index("idx_orchestrator_instances_status", "org_id", "status"),
        Index("idx_orchestrator_instances_last_accessed", "last_accessed_at"),
        Index("idx_orchestrator_instances_tier", "tier"),
    )


class User(BaseModel):
    """User account.

    Users are platform-level entities not bound to a single organization.
    Org membership and admin rights are tracked in UserOrgMembership.
    is_sys_admin grants platform-wide administration regardless of org.

    Attributes:
        id: Primary key (UUID)
        username: Globally unique username (among non-deleted rows)
        email: Optional email address
        password_hash: Hashed password (argon2 via passlib)
        is_sys_admin: Platform-wide admin flag
    """

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    username = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    password_hash = Column(Text, nullable=True)
    is_sys_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=True
    )
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)

    memberships = relationship(
        "UserOrgMembership", back_populates="user", cascade="all, delete-orphan"
    )
    conversations = relationship("Conversation", back_populates="user")

    __table_args__ = (
        Index(
            "uq_user_username_active",
            "username",
            unique=True,
            postgresql_where=text("is_deleted = FALSE"),
        ),
    )


class UserOrgMembership(BaseModel):
    """Membership of a user in an organization.

    Tracks which organizations a user belongs to and whether they have
    admin rights within that organization. Membership rows are hard-deleted
    (no soft-delete) — removal is permanent and instant.

    Attributes:
        id: Primary key
        user_id: User identifier
        org_id: Organization identifier
        is_admin: Whether the user is an admin of this organization
    """

    __tablename__ = "user_org_memberships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=True
    )
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)

    user = relationship("User", back_populates="memberships")
    organization = relationship("Organization", back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("user_id", "org_id", name="uq_user_org_membership"),
        Index("idx_user_org_mem_user_id", "user_id"),
        Index("idx_user_org_mem_org_id", "org_id"),
    )


class SystemPlugin(BaseModel):
    """System-wide plugin catalog (available to all tenants)."""

    __tablename__ = "system_plugins"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    pid = Column(String(255), nullable=False)
    version = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    tag = Column(String(100), nullable=True)
    is_latest = Column(Boolean, nullable=False, default=False)
    s3_path = Column(String(512), nullable=True)
    default_settings = Column(JSONB, nullable=True, default=dict)
    capabilities = Column(JSONB, nullable=True, default=list)
    agent_type = Column(String(50), nullable=False, default="specialized")
    stateless = Column(Boolean, nullable=False, default=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=True
    )
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint("pid", "version", name="uq_system_plugin_pid_version"),
        Index("idx_system_plugins_pid", "pid"),
        Index(
            "uq_system_plugin_latest",
            "pid",
            unique=True,
            postgresql_where=text("is_latest = TRUE"),
        ),
    )


class OrgPlugin(BaseModel):
    """Organization-specific plugin catalog."""

    __tablename__ = "org_plugins"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    pid = Column(String(255), nullable=False)
    version = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    tag = Column(String(100), nullable=True)
    is_latest = Column(Boolean, nullable=False, default=False)
    s3_path = Column(String(512), nullable=True)
    default_settings = Column(JSONB, nullable=True, default=dict)
    capabilities = Column(JSONB, nullable=True, default=list)
    agent_type = Column(String(50), nullable=False, default="specialized")
    stateless = Column(Boolean, nullable=False, default=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=True
    )
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "org_id", "pid", "version", name="uq_org_plugin_org_pid_version"
        ),
        Index("idx_org_plugins_catalog_org_id", "org_id"),
        Index(
            "uq_org_plugin_latest",
            "org_id",
            "pid",
            unique=True,
            postgresql_where=text("is_latest = TRUE"),
        ),
    )


class ProviderModelConfig(BaseModel):
    """Platform-level catalog of known models per LLM provider.

    Seeded by migrations. Used to power the model-selection list in the UI
    when an org admin configures an LLM. Users may still type a model name
    that isn't in this table (free-text override).

    Attributes:
        id: Primary key
        provider: Provider identifier (openai, anthropic, google, groq, azure, openai_compatible)
        model_id: The model identifier sent to the provider API (e.g. "gpt-4o")
        display_name: Human-readable label (e.g. "GPT-4o")
        aliases: JSON list of alternative identifiers (e.g. ["4o"])
        is_active: Whether this entry is visible in the selection list
    """

    __tablename__ = "provider_model_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(50), nullable=False)
    model_id = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=False)
    aliases = Column(JSONB, nullable=False, default=list)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=True
    )

    __table_args__ = (
        Index(
            "uq_provider_model_id_active",
            "provider",
            "model_id",
            unique=True,
            postgresql_where=text("is_active = TRUE"),
        ),
        Index("idx_provider_model_configs_provider", "provider"),
    )


class Conversation(BaseModel):
    """Conversation metadata."""

    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    title = Column(String(500), nullable=True)
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    instance_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orchestrator_instances.id", ondelete="SET NULL"),
    )
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=True
    )
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="conversations")
    instance = relationship("OrchestratorInstance", back_populates="conversations")

    __table_args__ = (
        Index("idx_conversations_user_id", "user_id"),
        Index("idx_conversations_instance_id", "instance_id"),
        Index("idx_conversations_org_id", "org_id"),
    )
