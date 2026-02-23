"""Role-based access control dependencies for FastAPI endpoints.

All dependencies read from request.state.session (a TokenSession set by
TenantContextMiddleware). For org-scoped endpoints the org_id path parameter
is resolved automatically by FastAPI's dependency injection.
"""

from fastapi import HTTPException, Path, Request, status

from cadence.middleware.tenant_context_middleware import TenantContext, require_session


def _build_context(
    session, org_id: str = "", is_org_admin: bool = False
) -> TenantContext:
    return TenantContext(
        user_id=session.user_id,
        org_id=org_id,
        is_sys_admin=session.is_sys_admin,
        is_org_admin=is_org_admin,
    )


async def require_authenticated(request: Request) -> TenantContext:
    """Require any authenticated session (no role enforcement).

    Args:
        request: FastAPI request

    Returns:
        TenantContext with no org binding

    Raises:
        HTTPException: 401 if no valid session
    """
    session = require_session(request)
    return _build_context(session)


async def require_sys_admin(request: Request) -> TenantContext:
    """Require platform-wide sys_admin flag.

    Args:
        request: FastAPI request

    Returns:
        TenantContext

    Raises:
        HTTPException: 401 if not authenticated, 403 if not sys_admin
    """
    session = require_session(request)
    if not session.is_sys_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin access required",
        )
    return _build_context(session)


async def require_org_member(
    request: Request,
    org_id: str = Path(...),
) -> TenantContext:
    """Require the caller to be a member (any role) of the org in the path.

    sys_admin bypasses the membership check.

    Args:
        request: FastAPI request
        org_id: Organization identifier from URL path

    Returns:
        TenantContext bound to the requested org

    Raises:
        HTTPException: 401 if not authenticated, 403 if not a member
    """
    session = require_session(request)
    if not session.is_sys_admin and not session.is_member_of(org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )
    is_org_admin = session.is_sys_admin or session.is_admin_of(org_id)
    return _build_context(session, org_id=org_id, is_org_admin=is_org_admin)


async def require_org_admin_access(
    request: Request,
    org_id: str = Path(...),
) -> TenantContext:
    """Require org_admin rights or sys_admin for the org in the path.

    Args:
        request: FastAPI request
        org_id: Organization identifier from URL path

    Returns:
        TenantContext bound to the requested org

    Raises:
        HTTPException: 401 if not authenticated, 403 if not org_admin/sys_admin
    """
    session = require_session(request)
    has_access = session.is_sys_admin or session.is_admin_of(org_id)
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization admin access required",
        )
    is_org_admin = session.is_admin_of(org_id)
    return _build_context(session, org_id=org_id, is_org_admin=is_org_admin)


async def require_any_admin(request: Request) -> TenantContext:
    """Require sys_admin or org_admin of at least one organization.

    Used for platform-scoped endpoints that have no org_id in the path.

    Args:
        request: FastAPI request

    Returns:
        TenantContext with no org binding

    Raises:
        HTTPException: 401 if not authenticated, 403 if not any kind of admin
    """
    session = require_session(request)
    if not session.is_sys_admin and not session.org_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return _build_context(session)
