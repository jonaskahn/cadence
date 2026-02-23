"""Authentication API endpoints.

Provides login, logout, and current-user org listing.

Endpoints:
  POST   /api/auth/login    — issue JWT (no auth required)
  DELETE /api/auth/logout   — revoke current session (auth required)
  GET    /api/me/orgs       — list orgs the caller belongs to (auth required)
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from cadence.middleware.authorization_middleware import require_authenticated
from cadence.middleware.tenant_context_middleware import TenantContext

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    """Login credentials.

    Attributes:
        username: Account username
        password: Plain-text password
    """

    username: str = Field(..., min_length=1, description="Username")
    password: str = Field(..., min_length=1, description="Password")


class LoginResponse(BaseModel):
    """Successful login response.

    Attributes:
        token: Signed JWT; use as 'Authorization: Bearer <token>'
    """

    token: str


class OrgAccessResponse(BaseModel):
    """Org membership entry.

    Attributes:
        org_id: Organization identifier
        org_name: Organization display name
        role: 'org_admin' or 'user'
    """

    org_id: str
    org_name: str
    role: str


@router.post(
    "/api/auth/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
)
async def login(login_request: LoginRequest, request: Request):
    """Authenticate and receive a JWT.

    The JWT carries only sub (user_id) and jti (ULID session key).
    Org membership and role data live in Redis and are resolved per request.

    Args:
        login_request: Username and password
        request: FastAPI request

    Returns:
        LoginResponse with signed JWT

    Raises:
        HTTPException: 401 if credentials are invalid
    """
    auth_service = request.app.state.auth_service
    try:
        result = await auth_service.login(
            username=login_request.username,
            password=login_request.password,
        )
        return LoginResponse(token=result["token"])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    except Exception as e:
        logger.error(f"Login failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed",
        )


@router.delete(
    "/api/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_authenticated)],
)
async def logout(request: Request):
    """Revoke the current session token.

    Args:
        request: FastAPI request

    Raises:
        HTTPException: If revocation fails
    """
    auth_service = request.app.state.auth_service
    try:
        jti = getattr(request.state, "token_jti", None)
        if jti:
            await auth_service.logout(jti)
    except Exception as e:
        logger.error(f"Logout failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed",
        )


class UpdateProfileRequest(BaseModel):
    """Self-service profile update.

    Attributes:
        display_name: Optional new display name
        email: Optional new email address
        current_password: Required when new_password is provided
        new_password: New password to set (requires current_password)
    """

    display_name: Optional[str] = None
    email: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = Field(default=None, min_length=8)


@router.patch("/api/me/profile", status_code=status.HTTP_204_NO_CONTENT)
async def update_my_profile(
    update_request: UpdateProfileRequest,
    request: Request,
    context: TenantContext = Depends(require_authenticated),
):
    """Update the authenticated user's display_name, email, and/or password.

    Args:
        update_request: Fields to update
        request: FastAPI request
        context: Authenticated context

    Raises:
        HTTPException: 422 if new_password provided without current_password
        HTTPException: 409 if email is already taken
        HTTPException: 401 if current_password is wrong
    """
    if update_request.new_password and not update_request.current_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="current_password is required when setting a new password",
        )

    auth_service = request.app.state.auth_service
    user_repo = auth_service.user_repo

    try:
        if update_request.display_name is not None or update_request.email is not None:
            if update_request.email is not None:
                existing = await user_repo.get_by_email(update_request.email)
                if existing and str(existing.id) != context.user_id:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Email is already in use",
                    )
            await user_repo.update(
                context.user_id,
                display_name=update_request.display_name,
                email=update_request.email,
                caller_id=context.user_id,
            )

        if update_request.new_password:
            await auth_service.update_user_password(
                user_id=context.user_id,
                current_password=update_request.current_password,
                new_password=update_request.new_password,
            )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to update profile: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile",
        )


class AboutMeResponse(BaseModel):
    """Current user identity response.

    Attributes:
        user_id: Authenticated user identifier
        is_sys_admin: Whether the user has platform-wide admin privileges
        username: Login username
        email: Email address
        display_name: Human-friendly display name
    """

    user_id: str
    is_sys_admin: bool
    username: Optional[str] = None
    email: Optional[str] = None
    display_name: Optional[str] = None


@router.get("/api/me", response_model=AboutMeResponse)
async def get_me(
    request: Request,
    context: TenantContext = Depends(require_authenticated),
):
    """Get current user identity and admin status.

    Args:
        request: FastAPI request
        context: Authenticated tenant context

    Returns:
        Current user id, sys_admin flag, username, email, and display_name
    """
    auth_service = request.app.state.auth_service
    user = await auth_service.user_repo.get_by_id(context.user_id)
    return AboutMeResponse(
        user_id=context.user_id,
        is_sys_admin=context.is_sys_admin,
        username=user.username if user else None,
        email=user.email if user else None,
        display_name=user.display_name if user else None,
    )


@router.get(
    "/api/me/orgs",
    response_model=list[OrgAccessResponse],
)
async def list_my_orgs(
    request: Request,
    context: TenantContext = Depends(require_authenticated),
):
    """List all organizations the authenticated user belongs to.

    Use the returned org_id as the path parameter for subsequent API calls.

    Args:
        request: FastAPI request
        context: Authenticated tenant context

    Returns:
        List of org memberships with role

    Raises:
        HTTPException: If retrieval fails
    """
    auth_service = request.app.state.auth_service
    try:
        orgs = await auth_service.get_user_orgs(context.user_id)
        return [
            OrgAccessResponse(
                org_id=org_access.org_id,
                org_name=org_access.org_name,
                role=org_access.role,
            )
            for org_access in orgs
        ]
    except Exception as e:
        logger.error(f"Failed to list user orgs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve organizations",
        )
