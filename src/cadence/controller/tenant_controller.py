"""Tenant management API endpoints.

Permission summary:
  /api/orgs                       any authenticated user (role-aware list)
  /api/admin/orgs/*               sys_admin only
  /api/users                      org_admin or sys_admin (search users by id/email/username)
  /api/admin/users                sys_admin only (create platform user)
  /api/admin/orgs/{id}/users      sys_admin only (create user + add to org)
  /api/orgs/{org_id}/settings     org_admin or sys_admin
  /api/orgs/{org_id}/llm-configs  org_admin only (sys_admin excluded — BYOK isolation)
  /api/orgs/{org_id}/members      org_admin or sys_admin (add existing user to org)
  /api/orgs/{org_id}/users (GET)  org_admin or sys_admin (list members)
  /api/orgs/{org_id}/users (POST) org_admin or sys_admin (add existing user to org)
  /api/orgs/{org_id}/users/*      org_admin or sys_admin (update / remove)
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from cadence.middleware.authorization_middleware import (
    require_any_admin,
    require_authenticated,
    require_org_admin_access,
    require_sys_admin,
)
from cadence.middleware.tenant_context_middleware import TenantContext

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tenants"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class CreateOrganizationRequest(BaseModel):
    """Create organization request."""

    name: str = Field(..., min_length=1, description="Organization name")


class OrganizationResponse(BaseModel):
    """Organization response."""

    org_id: str
    name: str
    status: str
    created_at: str


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


class TenantSettingResponse(BaseModel):
    """Org setting response."""

    key: str
    value: Any
    value_type: str


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


class UpdateMembershipRequest(BaseModel):
    """Update org membership request."""

    is_admin: bool = Field(..., description="New org_admin value")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mask_str(s: Optional[str]) -> Optional[str]:
    """Partially mask a string for soft-deleted user PII."""
    if not s:
        return s
    return s[:2] + "***" if len(s) > 2 else "***"


def _mask_email(email: Optional[str]) -> Optional[str]:
    """Partially mask an email address."""
    if not email:
        return None
    parts = email.split("@")
    return f"{_mask_str(parts[0])}@***"


def _build_llm_response(config: Any) -> LLMConfigResponse:
    """Build LLMConfigResponse from ORM object, masking the API key."""
    return LLMConfigResponse(
        id=str(config.id),
        name=config.name,
        provider=config.provider,
        base_url=config.base_url,
        additional_config=config.additional_config,
        created_at=config.created_at.isoformat(),
    )


def _build_member_response(
    member: Dict[str, Any], mask_deleted: bool
) -> UserMembershipResponse:
    """Build UserMembershipResponse, optionally masking soft-deleted PII."""
    username = member["username"]
    email = member.get("email")
    if mask_deleted and member.get("is_deleted"):
        username = _mask_str(username)
        email = _mask_email(email)
    return UserMembershipResponse(
        user_id=member["user_id"],
        username=username,
        email=email,
        is_sys_admin=member.get("is_sys_admin", False),
        is_admin=member.get("is_admin", False),
        is_deleted=member.get("is_deleted", False),
        created_at=member.get("created_at"),
    )


# ---------------------------------------------------------------------------
# Org listing — accessible by any authenticated user
# ---------------------------------------------------------------------------


@router.get("/api/orgs", response_model=List[OrgWithRoleResponse])
async def list_accessible_orgs(
    request: Request,
    context: TenantContext = Depends(require_authenticated),
):
    """List organizations visible to the caller.

    sys_admin receives all orgs with role='sys_admin'.
    Regular users receive only the orgs they belong to with their actual role.

    Args:
        request: FastAPI request
        context: Any authenticated context

    Returns:
        List of orgs with the caller's role in each

    Raises:
        HTTPException: If retrieval fails
    """
    tenant_service = request.app.state.tenant_service
    try:
        if context.is_sys_admin:
            orgs = await tenant_service.list_orgs()
            return [OrgWithRoleResponse(**org, role="sys_admin") for org in orgs]
        else:
            orgs = await tenant_service.list_orgs_for_user(context.user_id)
            return [OrgWithRoleResponse(**org) for org in orgs]
    except Exception as e:
        logger.error(f"Failed to list accessible orgs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list organizations",
        )


# ---------------------------------------------------------------------------
# Organization management (sys_admin only)
# ---------------------------------------------------------------------------


@router.post(
    "/api/admin/orgs",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_organization(
    create_request: CreateOrganizationRequest,
    request: Request,
    context: TenantContext = Depends(require_sys_admin),
):
    """Create a new organization.

    Args:
        create_request: Organization name
        request: FastAPI request
        context: sys_admin context

    Returns:
        Created organization

    Raises:
        HTTPException: If creation fails
    """
    tenant_service = request.app.state.tenant_service
    try:
        org = await tenant_service.create_org(
            name=create_request.name,
            caller_id=context.user_id,
        )
        return OrganizationResponse(**org)
    except Exception as e:
        logger.error(f"Failed to create organization: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create organization",
        )


@router.get("/api/admin/orgs", response_model=List[OrganizationResponse])
async def list_organizations(
    request: Request,
    context: TenantContext = Depends(require_sys_admin),
):
    """List all organizations (sys_admin only).

    Args:
        request: FastAPI request
        context: sys_admin context

    Returns:
        List of organizations

    Raises:
        HTTPException: If retrieval fails
    """
    tenant_service = request.app.state.tenant_service
    try:
        orgs = await tenant_service.list_orgs()
        return [OrganizationResponse(**org) for org in orgs]
    except Exception as e:
        logger.error(f"Failed to list organizations: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list organizations",
        )


@router.patch("/api/admin/orgs/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: str,
    update_data: Dict[str, Any],
    request: Request,
    context: TenantContext = Depends(require_sys_admin),
):
    """Update organization (sys_admin only).

    Args:
        org_id: Organization identifier
        update_data: Fields to update
        request: FastAPI request
        context: sys_admin context

    Returns:
        Updated organization

    Raises:
        HTTPException: If not found or update fails
    """
    tenant_service = request.app.state.tenant_service
    try:
        org = await tenant_service.update_org(
            org_id, update_data, caller_id=context.user_id
        )
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Organization {org_id} not found",
            )
        return OrganizationResponse(**org)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update organization: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update organization",
        )


# ---------------------------------------------------------------------------
# Tenant settings  (org_admin + sys_admin)
# ---------------------------------------------------------------------------


@router.post(
    "/api/orgs/{org_id}/settings",
    response_model=TenantSettingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def set_tenant_setting(
    org_id: str,
    setting_request: SetTenantSettingRequest,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Create or update an org setting.

    Args:
        org_id: Organization identifier
        setting_request: Key/value to set
        request: FastAPI request
        context: org_admin or sys_admin context

    Returns:
        Setting response

    Raises:
        HTTPException: If operation fails
    """
    tenant_service = request.app.state.tenant_service
    try:
        setting = await tenant_service.set_setting(
            org_id=org_id,
            key=setting_request.key,
            value=setting_request.value,
            caller_id=context.user_id,
        )
        return TenantSettingResponse(**setting)
    except Exception as e:
        logger.error(f"Failed to set tenant setting: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set tenant setting",
        )


@router.get(
    "/api/orgs/{org_id}/settings",
    response_model=List[TenantSettingResponse],
)
async def list_tenant_settings(
    org_id: str,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """List all org settings.

    Args:
        org_id: Organization identifier
        request: FastAPI request
        context: org_admin or sys_admin context

    Returns:
        List of settings

    Raises:
        HTTPException: If retrieval fails
    """
    tenant_service = request.app.state.tenant_service
    try:
        settings = await tenant_service.list_settings(org_id)
        return [TenantSettingResponse(**s) for s in settings]
    except Exception as e:
        logger.error(f"Failed to list tenant settings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list tenant settings",
        )


# ---------------------------------------------------------------------------
# LLM configuration — org_admin ONLY (sys_admin excluded for BYOK isolation)
# ---------------------------------------------------------------------------


@router.post(
    "/api/orgs/{org_id}/llm-configs",
    response_model=LLMConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_llm_config(
    org_id: str,
    config_request: AddLLMConfigRequest,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Add LLM configuration (BYOK).

    Accessible by org_admin only — sys_admin cannot read org API keys.

    Args:
        org_id: Organization identifier
        config_request: LLM config details
        request: FastAPI request
        context: org_admin context

    Returns:
        LLM config response (API key masked)

    Raises:
        HTTPException: 500 on failure
    """
    tenant_service = request.app.state.tenant_service
    try:
        config = await tenant_service.add_llm_config(
            org_id=org_id,
            name=config_request.name,
            provider=config_request.provider,
            api_key=config_request.api_key,
            base_url=config_request.base_url,
            additional_config=config_request.additional_config,
            caller_id=context.user_id,
        )
        return _build_llm_response(config)
    except IntegrityError as e:
        err = str(e)
        if "foreign key" in err.lower() or "fk" in err.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="LLM config already exists"
        )
    except Exception as e:
        logger.error(f"Failed to add LLM config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add LLM configuration",
        )


@router.get(
    "/api/orgs/{org_id}/llm-configs",
    response_model=List[LLMConfigResponse],
)
async def list_llm_configs(
    org_id: str,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """List LLM configurations (API key masked).

    Args:
        org_id: Organization identifier
        request: FastAPI request
        context: org_admin context

    Returns:
        List of LLM configs
    """
    tenant_service = request.app.state.tenant_service
    try:
        configs = await tenant_service.list_llm_configs(org_id)
        return [_build_llm_response(c) for c in configs]
    except Exception as e:
        logger.error(f"Failed to list LLM configs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list LLM configurations",
        )


@router.get(
    "/api/providers/{provider}/models",
    response_model=List[ProviderModelResponse],
    tags=["tenants"],
)
async def list_provider_models(
    provider: str,
    request: Request,
    context: TenantContext = Depends(require_authenticated),
):
    """List known models for a given LLM provider.

    Returns the platform model catalog for the specified provider.
    Users may also type a custom model name not present in this list.

    Args:
        provider: Provider identifier (openai, anthropic, google, groq, azure)
        request: FastAPI request
        context: Any authenticated context

    Returns:
        List of model entries with model_id, display_name, and aliases
    """
    provider_model_repo = request.app.state.provider_model_repo
    try:
        models = await provider_model_repo.get_by_provider(provider)
        return [
            ProviderModelResponse(
                model_id=m.model_id,
                display_name=m.display_name,
                aliases=m.aliases or [],
            )
            for m in models
        ]
    except Exception as e:
        logger.error(
            f"Failed to list models for provider {provider}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list provider models",
        )


@router.delete(
    "/api/orgs/{org_id}/llm-configs/{config_name}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_llm_config(
    org_id: str,
    config_name: str,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Soft-delete an LLM configuration.

    Returns 409 if the config is still referenced by active orchestrators.

    Args:
        org_id: Organization identifier
        config_name: Config name to delete
        request: FastAPI request
        context: org_admin context

    Raises:
        HTTPException: 404 if not found, 409 if in use
    """
    tenant_service = request.app.state.tenant_service
    try:
        deleted = await tenant_service.delete_llm_config(
            org_id=org_id,
            name=config_name,
            caller_id=context.user_id,
        )
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"LLM config '{config_name}' not found",
            )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete LLM config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete LLM configuration",
        )


# ---------------------------------------------------------------------------
# User management — sys_admin only
# ---------------------------------------------------------------------------


@router.get(
    "/api/users",
    response_model=List[UserMembershipResponse],
)
async def search_users(
    request: Request,
    context: TenantContext = Depends(require_any_admin),
    user_id: Optional[str] = None,
    email: Optional[str] = None,
    username: Optional[str] = None,
):
    """Search platform users by user_id, email, or username (exact match).

    Accessible by org_admin and sys_admin. At least one query param is required.

    Args:
        request: FastAPI request
        context: org_admin or sys_admin context
        user_id: Exact user ID to look up
        email: Exact email address to look up
        username: Exact username to look up

    Returns:
        List of matching users (0 or 1 results for exact match)

    Raises:
        HTTPException: 400 if no search param provided
    """
    if not any([user_id, email, username]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least one of: user_id, email, username",
        )
    tenant_service = request.app.state.tenant_service
    try:
        user_dict = await tenant_service.search_user(
            user_id=user_id,
            email=email,
            username=username,
            requester_is_sys_admin=context.is_sys_admin,
        )
        if not user_dict:
            return []
        return [_build_member_response(user_dict, mask_deleted=False)]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to search users: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search users",
        )


@router.post(
    "/api/admin/users",
    response_model=UserMembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    create_request: CreateUserRequest,
    request: Request,
    context: TenantContext = Depends(require_sys_admin),
):
    """Create a new platform user (not assigned to any org).

    Only sys_admin can create user accounts. Use the membership endpoints
    to assign the user to organizations afterward.

    Args:
        create_request: Username, email, and optional password
        request: FastAPI request
        context: sys_admin context

    Returns:
        Created user

    Raises:
        HTTPException: If creation fails
    """
    tenant_service = request.app.state.tenant_service
    try:
        user = await tenant_service.create_user(
            username=create_request.username,
            email=create_request.email,
            password=create_request.password,
            is_sys_admin=False,
            caller_id=context.user_id,
        )
        return _build_member_response(user, mask_deleted=False)
    except Exception as e:
        logger.error(f"Failed to create user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user",
        )


@router.get(
    "/api/admin/users",
    response_model=List[UserMembershipResponse],
)
async def list_all_users(
    request: Request,
    context: TenantContext = Depends(require_sys_admin),
):
    """List all platform users (sys_admin only).

    Args:
        request: FastAPI request
        context: sys_admin context

    Returns:
        List of all non-deleted users
    """
    tenant_service = request.app.state.tenant_service
    try:
        users = await tenant_service.list_all_users()
        return [_build_member_response(u, mask_deleted=False) for u in users]
    except Exception as e:
        logger.error(f"Failed to list users: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list users",
        )


@router.patch(
    "/api/admin/users/{user_id}",
    response_model=UserMembershipResponse,
)
async def update_user(
    user_id: str,
    update_request: UpdateUserRequest,
    request: Request,
    context: TenantContext = Depends(require_sys_admin),
):
    """Update a platform user's username, email, or sys_admin flag (sys_admin only).

    Args:
        user_id: User identifier
        update_request: Fields to update
        request: FastAPI request
        context: sys_admin context

    Returns:
        Updated user

    Raises:
        HTTPException: 404 if not found
    """
    tenant_service = request.app.state.tenant_service
    try:
        user = await tenant_service.update_user(
            user_id=user_id,
            username=update_request.username,
            email=update_request.email,
            is_sys_admin=update_request.is_sys_admin,
            caller_id=context.user_id,
        )
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        return _build_member_response(user, mask_deleted=False)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user",
        )


@router.delete("/api/admin/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    request: Request,
    context: TenantContext = Depends(require_sys_admin),
):
    """Soft-delete a platform user and remove all org memberships (sys_admin only).

    Args:
        user_id: User identifier
        request: FastAPI request
        context: sys_admin context

    Raises:
        HTTPException: 400 if attempting to delete self, 404 if not found
    """
    if user_id == context.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )
    tenant_service = request.app.state.tenant_service
    try:
        deleted = await tenant_service.delete_user(user_id, caller_id=context.user_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user",
        )


# ---------------------------------------------------------------------------
# Org membership management (org_admin + sys_admin)
# ---------------------------------------------------------------------------


@router.post(
    "/api/orgs/{org_id}/members",
    response_model=UserMembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_member_to_org(
    org_id: str,
    add_request: AddOrgMemberRequest,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Add an existing user to this organization.

    org_admin can add any existing user. They cannot grant sys_admin.

    Args:
        org_id: Organization identifier
        add_request: Existing user_id and desired is_admin flag
        request: FastAPI request
        context: org_admin or sys_admin context

    Returns:
        User with new membership

    Raises:
        HTTPException: 404 if user not found, 409 if already a member
    """
    tenant_service = request.app.state.tenant_service
    try:
        user_dict = await tenant_service.add_existing_user_to_org(
            org_id=org_id,
            user_id=add_request.user_id,
            is_admin=add_request.is_admin,
            caller_id=context.user_id,
        )
        return _build_member_response(user_dict, mask_deleted=False)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add member to org: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add member to organization",
        )


@router.get(
    "/api/orgs/{org_id}/users",
    response_model=List[UserMembershipResponse],
)
async def list_org_users(
    org_id: str,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """List all active members of an organization.

    Args:
        org_id: Organization identifier
        request: FastAPI request
        context: org_admin or sys_admin context

    Returns:
        List of active user memberships

    Raises:
        HTTPException: If retrieval fails
    """
    tenant_service = request.app.state.tenant_service
    try:
        members = await tenant_service.list_org_members(org_id)
        return [_build_member_response(m, mask_deleted=False) for m in members]
    except Exception as e:
        logger.error(f"Failed to list users: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list users",
        )


@router.post(
    "/api/orgs/{org_id}/users",
    response_model=UserMembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_user_to_org(
    org_id: str,
    add_request: AddOrgMemberRequest,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Add an existing user to this organization.

    Alias for POST /api/orgs/{org_id}/members. org_admin can add any existing
    user. They cannot grant sys_admin.

    Args:
        org_id: Organization identifier
        add_request: Existing user_id and desired is_admin flag
        request: FastAPI request
        context: org_admin or sys_admin context

    Returns:
        User with new membership

    Raises:
        HTTPException: 404 if user not found, 409 if already a member
    """
    tenant_service = request.app.state.tenant_service
    try:
        user_dict = await tenant_service.add_existing_user_to_org(
            org_id=org_id,
            user_id=add_request.user_id,
            is_admin=add_request.is_admin,
            caller_id=context.user_id,
        )
        return _build_member_response(user_dict, mask_deleted=False)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add user to org: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add user to organization",
        )


@router.patch(
    "/api/orgs/{org_id}/users/{user_id}/membership",
    response_model=UserMembershipResponse,
)
async def update_user_membership(
    org_id: str,
    user_id: str,
    membership_request: UpdateMembershipRequest,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Update a user's admin flag within this org.

    Args:
        org_id: Organization identifier
        user_id: User identifier
        membership_request: New is_admin value
        request: FastAPI request
        context: org_admin or sys_admin context

    Returns:
        Updated membership response

    Raises:
        HTTPException: 404 if membership not found
    """
    tenant_service = request.app.state.tenant_service
    try:
        membership = await tenant_service.update_org_membership(
            user_id=user_id,
            org_id=org_id,
            is_admin=membership_request.is_admin,
            caller_id=context.user_id,
        )
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Membership for user {user_id} in org {org_id} not found",
            )
        member = await tenant_service.get_org_member(org_id, user_id)
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found",
            )
        return _build_member_response(member, mask_deleted=False)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update membership: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update membership",
        )


@router.delete(
    "/api/orgs/{org_id}/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_user_from_org(
    org_id: str,
    user_id: str,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Remove a user from this organization (hard-delete membership).

    Args:
        org_id: Organization identifier
        user_id: User identifier
        request: FastAPI request
        context: org_admin or sys_admin context

    Raises:
        HTTPException: 404 if not found
    """
    tenant_service = request.app.state.tenant_service
    try:
        removed = await tenant_service.remove_user_from_org(
            user_id=user_id,
            org_id=org_id,
        )
        if not removed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} is not a member of org {org_id}",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove user from org: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove user from organization",
        )
