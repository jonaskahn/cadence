"""User management API endpoints."""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError

from cadence.controller.schemas.tenant_schemas import (
    CreateUserRequest,
    UpdateUserRequest,
    UserMembershipResponse,
)
from cadence.middleware.authorization_middleware import (
    require_any_admin,
    require_sys_admin,
)
from cadence.middleware.tenant_context_middleware import TenantContext

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tenants"])


def _mask_sensitive_string(value: Optional[str]) -> Optional[str]:
    """Partially mask a string value to protect soft-deleted user PII."""
    if not value:
        return value
    return value[:2] + "***" if len(value) > 2 else "***"


def _mask_email(email: Optional[str]) -> Optional[str]:
    """Partially mask an email address."""
    if not email:
        return None
    email_parts = email.split("@")
    return f"{_mask_sensitive_string(email_parts[0])}@***"


def _build_member_response(member: dict, mask_deleted: bool) -> UserMembershipResponse:
    """Build UserMembershipResponse, optionally masking soft-deleted PII."""
    username = member["username"]
    email = member.get("email")
    if mask_deleted and member.get("is_deleted"):
        username = _mask_sensitive_string(username)
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
    """Search platform users by user_id, email, or username (exact match)."""
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
    """Create a new platform user (sys_admin only)."""
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
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists",
        )
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
    """List all platform users (sys_admin only)."""
    tenant_service = request.app.state.tenant_service
    try:
        users = await tenant_service.list_all_users()
        return [_build_member_response(user, mask_deleted=False) for user in users]
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
    """Update a platform user's username, email, or sys_admin flag (sys_admin only)."""
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
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists",
        )
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
    """Soft-delete a platform user and remove all org memberships (sys_admin only)."""
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
