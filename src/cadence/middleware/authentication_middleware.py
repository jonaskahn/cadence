"""Authentication middleware for JWT and API key validation.

This module provides authentication middleware supporting both JWT tokens
and API keys for request authentication.
"""

import logging
from typing import Optional

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class JWTAuth:
    """JWT authentication validator.

    Supports both internal JWT (HMAC) and third-party JWT (RSA).

    Attributes:
        internal_secret: Internal JWT secret key
        internal_algorithm: Internal JWT algorithm (HS256)
        third_party_secret: Third-party JWT public key
        third_party_algorithm: Third-party JWT algorithm (RS256)
    """

    def __init__(
        self,
        internal_secret: str,
        internal_algorithm: str = "HS256",
        third_party_secret: Optional[str] = None,
        third_party_algorithm: str = "RS256",
    ):
        """Initialize JWT authentication.

        Args:
            internal_secret: Internal JWT secret
            internal_algorithm: Internal algorithm (default: HS256)
            third_party_secret: Third-party public key (optional)
            third_party_algorithm: Third-party algorithm (default: RS256)
        """
        self.internal_secret = internal_secret
        self.internal_algorithm = internal_algorithm
        self.third_party_secret = third_party_secret
        self.third_party_algorithm = third_party_algorithm

    def validate(self, token: str) -> dict:
        """Validate JWT token.

        Tries internal secret first, then third-party if configured.

        Args:
            token: JWT token string

        Returns:
            Decoded JWT payload

        Raises:
            HTTPException: If token is invalid
        """
        import jwt

        try:
            return jwt.decode(
                token,
                self.internal_secret,
                algorithms=[self.internal_algorithm],
            )
        except jwt.InvalidTokenError:
            if self.third_party_secret:
                try:
                    return jwt.decode(
                        token,
                        self.third_party_secret,
                        algorithms=[self.third_party_algorithm],
                    )
                except jwt.InvalidTokenError as e:
                    logger.warning(f"JWT validation failed: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid authentication token",
                    )
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication token",
                )


class APIKeyAuth:
    """API key authentication validator.

    Validates API keys from X-API-Key header against database.

    Attributes:
        api_key_repo: Repository for API key validation
    """

    def __init__(self, api_key_repo):
        """Initialize API key authentication.

        Args:
            api_key_repo: API key repository
        """
        self.api_key_repo = api_key_repo

    async def validate(self, api_key: str) -> dict:
        """Validate API key.

        Args:
            api_key: API key string

        Returns:
            API key metadata (org_id, user_id, etc.)

        Raises:
            HTTPException: If API key is invalid
        """
        key_data = await self.api_key_repo.validate(api_key)

        if not key_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )

        return key_data


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware for enforcing authentication on protected routes.

    Checks for JWT or API key and validates before allowing access.

    Attributes:
        jwt_auth: JWT authentication validator
        api_key_auth: API key authentication validator
        public_paths: List of paths that don't require authentication
    """

    def __init__(
        self,
        app,
        jwt_auth: JWTAuth,
        api_key_auth: Optional[APIKeyAuth] = None,
        public_paths: Optional[list] = None,
    ):
        """Initialize authentication middleware.

        Args:
            app: FastAPI application
            jwt_auth: JWT authentication validator
            api_key_auth: Optional API key validator
            public_paths: Paths that don't require auth (default: /health, /docs)
        """
        super().__init__(app)
        self.jwt_auth = jwt_auth
        self.api_key_auth = api_key_auth
        self.public_paths = public_paths or [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]

    async def dispatch(self, request: Request, call_next):
        """Process request and validate authentication.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response from downstream handlers

        Raises:
            HTTPException: If authentication fails
        """
        if self._is_public_path(request.url.path):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        api_key_header = request.headers.get("X-API-Key")

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            self.jwt_auth.validate(token)

        elif api_key_header and self.api_key_auth:
            await self.api_key_auth.validate(api_key_header)

        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required (Bearer token or X-API-Key)",
            )

        response = await call_next(request)
        return response

    def _is_public_path(self, path: str) -> bool:
        """Check if path is public.

        Args:
            path: Request path

        Returns:
            True if public path
        """
        if path == "/":
            return True
        return any(path.startswith(public) for public in self.public_paths)
