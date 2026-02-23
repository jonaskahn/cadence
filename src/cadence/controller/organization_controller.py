"""Organization and settings management API endpoints."""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError

from cadence.controller.schemas.tenant_schemas import (
    CreateOrganizationRequest,
    OrchestratorDefaultsRequest,
    OrchestratorDefaultsResponse,
    OrganizationResponse,
    OrgProfileUpdateRequest,
    OrgWithRoleResponse,
    SetTenantSettingRequest,
    TenantSettingResponse,
    TierQuota,
    UpdateOrganizationRequest,
)
from cadence.middleware.authorization_middleware import (
    require_authenticated,
    require_org_admin_access,
    require_org_member,
    require_sys_admin,
)
from cadence.middleware.tenant_context_middleware import TenantContext

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tenants"])


@router.get("/api/orgs", response_model=List[OrgWithRoleResponse])
async def list_accessible_orgs(
    request: Request,
    context: TenantContext = Depends(require_authenticated),
):
    """List organizations visible to the caller.

    sys_admin receives all orgs with role='sys_admin'.
    Regular users receive only the orgs they belong to with their actual role.
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


@router.get("/api/orgs/{org_id}", response_model=OrganizationResponse)
async def get_org_profile(
    org_id: str,
    request: Request,
    context: TenantContext = Depends(require_org_member),
):
    """Get organization profile (any org member)."""
    tenant_service = request.app.state.tenant_service
    try:
        org = await tenant_service.get_org(org_id)
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Organization {org_id} not found",
            )
        return OrganizationResponse(**org)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get org profile: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get organization",
        )


@router.patch("/api/orgs/{org_id}/profile", response_model=OrganizationResponse)
async def update_org_profile(
    org_id: str,
    update_data: OrgProfileUpdateRequest,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Update org basic profile (org_admin). Domain, tier, status and slug are read-only."""
    tenant_service = request.app.state.tenant_service
    try:
        org = await tenant_service.update_org(
            org_id,
            update_data.model_dump(exclude_none=True),
            caller_id=context.user_id,
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
        logger.error(f"Failed to update org profile: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update organization profile",
        )


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
    """Create a new organization (sys_admin only)."""
    tenant_service = request.app.state.tenant_service
    try:
        org = await tenant_service.create_org(
            name=create_request.name,
            caller_id=context.user_id,
            display_name=create_request.display_name,
            domain=create_request.domain,
            tier=create_request.tier,
            description=create_request.description,
            contact_email=create_request.contact_email,
            website=create_request.website,
            logo_url=create_request.logo_url,
            country=create_request.country,
            timezone=create_request.timezone,
        )
        return OrganizationResponse(**org)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization domain already exists",
        )
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
    """List all organizations (sys_admin only)."""
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


@router.get("/api/admin/orgs/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: str,
    request: Request,
    context: TenantContext = Depends(require_sys_admin),
):
    """Get a single organization by ID (sys_admin only)."""
    tenant_service = request.app.state.tenant_service
    try:
        org = await tenant_service.get_org(org_id)
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Organization {org_id} not found",
            )
        return OrganizationResponse(**org)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get organization: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get organization",
        )


@router.get("/api/admin/orgs/{org_id}/quota", response_model=TierQuota)
async def get_organization_quota(
    org_id: str,
    request: Request,
    context: TenantContext = Depends(require_sys_admin),
):
    """Get quota limits for an organization based on its subscription tier (sys_admin only)."""
    settings_service = request.app.state.settings_service
    try:
        quota = await settings_service.get_org_quota(org_id)
        if quota is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quota not found for organization {org_id}",
            )
        return TierQuota(**quota)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get org quota: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get organization quota",
        )


@router.patch("/api/admin/orgs/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: str,
    update_data: UpdateOrganizationRequest,
    request: Request,
    context: TenantContext = Depends(require_sys_admin),
):
    """Update organization (sys_admin only)."""
    tenant_service = request.app.state.tenant_service
    try:
        org = await tenant_service.update_org(
            org_id,
            update_data.model_dump(exclude_none=True),
            caller_id=context.user_id,
        )
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Organization {org_id} not found",
            )
        return OrganizationResponse(**org)
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization domain already exists",
        )
    except Exception as e:
        logger.error(f"Failed to update organization: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update organization",
        )


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
    """Create or update an org setting."""
    tenant_service = request.app.state.tenant_service
    try:
        setting = await tenant_service.set_setting(
            org_id=org_id,
            key=setting_request.key,
            value=setting_request.value,
            caller_id=context.user_id,
            overridable=setting_request.overridable,
        )

        event_publisher = getattr(request.app.state, "event_publisher", None)
        if event_publisher is not None:
            try:
                await event_publisher.publish_org_settings_changed(org_id=org_id)
            except Exception as pub_err:
                logger.warning(
                    f"Failed to publish org settings changed event: {pub_err}"
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
    """List all org settings."""
    tenant_service = request.app.state.tenant_service
    try:
        settings = await tenant_service.list_settings(org_id)
        return [TenantSettingResponse(**setting) for setting in settings]
    except Exception as e:
        logger.error(f"Failed to list tenant settings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list tenant settings",
        )


@router.get(
    "/api/orgs/{org_id}/orchestrator-defaults",
    response_model=OrchestratorDefaultsResponse,
)
async def get_orchestrator_defaults(
    org_id: str,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Org-level orchestrator defaults (stored only in org settings)."""
    settings_service = request.app.state.settings_service
    try:
        keys = [
            "default_llm_config_id",
            "default_model_name",
            "default_max_tokens",
            "default_timeout",
        ]
        orchestrator_defaults: dict = {}
        for key in keys:
            setting = await settings_service.org_settings_repo.get_by_key(org_id, key)
            orchestrator_defaults[key] = setting.value if setting else None
        return OrchestratorDefaultsResponse(**orchestrator_defaults)
    except Exception as e:
        logger.error(f"Failed to get orchestrator defaults: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get orchestrator defaults",
        )


@router.put(
    "/api/orgs/{org_id}/orchestrator-defaults",
    response_model=OrchestratorDefaultsResponse,
)
async def set_orchestrator_defaults(
    org_id: str,
    body: OrchestratorDefaultsRequest,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Save org-level orchestrator defaults. Does not affect running instances."""
    tenant_service = request.app.state.tenant_service
    try:
        for key, value in body.model_dump().items():
            await tenant_service.set_setting(
                org_id=org_id,
                key=key,
                value=value,
                caller_id=context.user_id,
                overridable=True,
            )
        return OrchestratorDefaultsResponse(**body.model_dump())
    except Exception as e:
        logger.error(f"Failed to set orchestrator defaults: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set orchestrator defaults",
        )
