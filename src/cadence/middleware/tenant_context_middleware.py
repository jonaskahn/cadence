"""Multi-tenant context middleware for request isolation.

Extracts the JWT from the Authorization header, validates the signature,
then resolves the session from Redis using the JWT's jti (ULID).

The resolved session is attached to request.state for downstream dependencies.
No org/role data is stored in the JWT; all of that lives in Redis.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


@dataclass
class TenantContext:
    """Request-scoped identity and access context.

    Attributes:
        user_id: Authenticated user identifier
        org_id: Organization identifier for this request (empty for sys_admin endpoints)
        is_sys_admin: Platform-wide admin flag
        is_org_admin: Admin of the requested org (derived from session)
    """

    user_id: str
    org_id: str
    is_sys_admin: bool
    is_org_admin: bool


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Middleware that validates JWT signature and loads the Redis session.

    Sets request.state.session (TokenSession or None) and
    request.state.token_jti (str or None) for downstream dependencies.

    The SessionStore is resolved lazily from app.state at request time so
    middleware can be registered before the lifespan starts.

    Attributes:
        jwt_secret: Secret key for JWT signature verification
        jwt_algorithm: JWT algorithm (default HS256)
    """

    def __init__(self, app, jwt_secret: str, jwt_algorithm: str = "HS256"):
        """Initialize the middleware.

        Args:
            app: FastAPI application
            jwt_secret: JWT signing secret
            jwt_algorithm: JWT algorithm
        """
        super().__init__(app)
        self.jwt_secret = jwt_secret
        self.jwt_algorithm = jwt_algorithm

    async def dispatch(self, request: Request, call_next):
        """Validate JWT and attach session to request.state.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response from downstream handlers
        """
        request.state.session = None
        request.state.token_jti = None

        bearer = self._extract_bearer(request)
        if bearer:
            jti = self._decode_jwt_jti(bearer)
            if jti:
                session_store = getattr(request.app.state, "session_store", None)
                if session_store:
                    session = await session_store.get_session(jti)
                    if session:
                        request.state.session = session
                        request.state.token_jti = jti

        return await call_next(request)

    def _extract_bearer(self, request: Request) -> Optional[str]:
        """Extract the Bearer token from the Authorization header.

        Args:
            request: Incoming request

        Returns:
            Token string or None
        """
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:]
        return None

    def _decode_jwt_jti(self, token: str) -> Optional[str]:
        """Decode JWT and extract the jti claim.

        Args:
            token: JWT string

        Returns:
            jti string or None if invalid
        """
        try:
            import jwt

            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=[self.jwt_algorithm],
            )
            return payload.get("jti")
        except Exception as e:
            logger.debug(f"JWT decode failed: {e}")
            return None


def get_session(request: Request):
    """Get the TokenSession attached to this request, if any.

    Args:
        request: FastAPI request

    Returns:
        TokenSession or None
    """
    return getattr(request.state, "session", None)


def require_session(request: Request):
    """Get the TokenSession or raise 401.

    Args:
        request: FastAPI request

    Returns:
        TokenSession

    Raises:
        HTTPException: 401 if no valid session
    """
    session = get_session(request)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return session
