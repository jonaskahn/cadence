"""Org membership management API endpoints."""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status

from cadence.controller.schemas.tenant_schemas import (
    AddOrgMemberRequest,
    UpdateMembershipRequest,
    UserMembershipResponse,
)
from cadence.controller.user_controller import _build_member_response
from cadence.middleware.authorization_middleware import require_org_admin_access
from cadence.middleware.tenant_context_middleware import TenantContext

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tenants"])


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
    """Add an existing user to this organization."""
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
    """List all active members of an organization."""
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
    """Add an existing user to this organization (alias for /members)."""
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
    """Update a user's admin flag within this org."""
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
    """Remove a user from this organization (hard-delete membership)."""
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
