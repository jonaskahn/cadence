"""Authentication service for login, logout, and session management.

Handles credential verification, JWT issuance (jti = ULID), Redis session
creation, and org-membership resolution on login.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from cadence.repository.organization_repository import OrganizationRepository
from cadence.repository.session_store_repository import SessionStoreRepository
from cadence.repository.user_org_membership_repository import (
    UserOrgMembershipRepository,
)
from cadence.repository.user_repository import UserRepository

logger = logging.getLogger(__name__)

PBKDF2_ALGORITHM = "pbkdf2:sha256:260000"


@dataclass
class OrgAccess:
    """Org membership item returned by get_user_orgs.

    Attributes:
        org_id: Organization identifier
        org_name: Organization display name
        role: 'org_admin' or 'user'
    """

    org_id: str
    org_name: str
    role: str


def _verify_pbkdf2_password(plain: str, stored_hash: str) -> bool:
    """Verify a PBKDF2-HMAC-SHA256 password hash (bootstrap-generated format).

    Expected format: pbkdf2:sha256:260000:<hex-salt>:<hex-digest>

    Args:
        plain: Plain-text password
        stored_hash: Stored hash string

    Returns:
        True if password matches
    """
    import hashlib

    parts = stored_hash.split(":")
    if len(parts) != 5 or parts[0] != "pbkdf2":
        return False

    _, algo, iterations_str, salt_hex, digest_hex = parts
    try:
        salt = bytes.fromhex(salt_hex)
        iterations = int(iterations_str)
        expected = bytes.fromhex(digest_hex)
    except (ValueError, TypeError):
        return False

    actual = hashlib.pbkdf2_hmac(algo, plain.encode(), salt, iterations)
    return actual == expected


def _verify_argon2_password(plain: str, stored_hash: str) -> bool:
    """Verify a argon2 password hash (passlib-generated).

    Args:
        plain: Plain-text password
        stored_hash: Stored argon2 hash string

    Returns:
        True if password matches
    """
    from passlib.context import CryptContext

    ctx = CryptContext(schemes=["argon2"], deprecated="auto")
    return ctx.verify(plain, stored_hash)


def _verify_password(plain: str, stored_hash: str) -> bool:
    """Verify a password against any supported hash format.

    Supports both PBKDF2 (bootstrap-generated) and argon2 (passlib) hashes.

    Args:
        plain: Plain-text password
        stored_hash: Stored hash string

    Returns:
        True if password matches
    """
    if stored_hash.startswith("pbkdf2:"):
        return _verify_pbkdf2_password(plain, stored_hash)
    return _verify_argon2_password(plain, stored_hash)


def _hash_password(plain: str) -> str:
    """Hash a plain-text password using argon2.

    Args:
        plain: Plain-text password

    Returns:
        argon2 hash string
    """
    from passlib.context import CryptContext

    ctx = CryptContext(schemes=["argon2"], deprecated="auto")
    return ctx.hash(plain)


def _build_jwt(
    user_id: str,
    jti: str,
    secret_key: str,
    algorithm: str,
    ttl_seconds: int,
) -> str:
    """Build a signed JWT with the given jti (ULID) and no org/role claims.

    Args:
        user_id: Subject (user identifier)
        jti: JWT ID — the ULID used as Redis session key
        secret_key: HMAC signing key
        algorithm: JWT algorithm (e.g. HS256)
        ttl_seconds: Token lifetime in seconds

    Returns:
        Encoded JWT string
    """
    import jwt

    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "jti": jti,
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
    }
    return jwt.encode(payload, secret_key, algorithm=algorithm)


class AuthService:
    """Handles login, logout, token refresh, and org listing.

    Attributes:
        user_repo: User repository for credential lookup
        membership_repo: Membership repository for org resolution
        org_repo: Organization repository for name resolution
        session_store: Redis session store
        secret_key: JWT signing key
        algorithm: JWT algorithm
        token_ttl_seconds: Session and JWT lifetime in seconds
    """

    def __init__(
        self,
        user_repo: UserRepository,
        membership_repo: UserOrgMembershipRepository,
        org_repo: OrganizationRepository,
        session_store: SessionStoreRepository,
        secret_key: str,
        algorithm: str = "HS256",
        token_ttl_seconds: int = 1800,
    ):
        self.user_repo = user_repo
        self.membership_repo = membership_repo
        self.org_repo = org_repo
        self.session_store = session_store
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.token_ttl_seconds = token_ttl_seconds

    async def login(self, username: str, password: str) -> Dict[str, str]:
        """Authenticate a user and issue a JWT with a ULID jti.

        Args:
            username: Username
            password: Plain-text password

        Returns:
            Dict with 'token' key containing the signed JWT

        Raises:
            ValueError: If credentials are invalid
        """
        user = await self.user_repo.get_by_username(username)
        if not user or not user.password_hash:
            raise ValueError("Invalid credentials")

        if not _verify_password(password, user.password_hash):
            raise ValueError("Invalid credentials")

        org_admin, org_user = await self._resolve_memberships(str(user.id))

        session = await self.session_store.create_session(
            user_id=str(user.id),
            is_sys_admin=user.is_sys_admin,
            org_admin=[str(o) for o in org_admin],
            org_user=[str(o) for o in org_user],
            ttl_seconds=self.token_ttl_seconds,
        )

        token = _build_jwt(
            user_id=str(user.id),
            jti=session.jti,
            secret_key=self.secret_key,
            algorithm=self.algorithm,
            ttl_seconds=self.token_ttl_seconds,
        )

        logger.info(f"User logged in: user_id={user.id}")
        return {"token": token}

    async def logout(self, jti: str) -> None:
        """Revoke a session by its JWT jti.

        Args:
            jti: JWT ID (ULID string) extracted from the token
        """
        await self.session_store.delete_session(jti)
        logger.info(f"Session revoked: jti={jti}")

    async def get_user_orgs(self, user_id: str) -> List[OrgAccess]:
        """List all org memberships for a user with org names.

        Args:
            user_id: Authenticated user identifier

        Returns:
            List of OrgAccess entries sorted by org_id
        """
        memberships = await self.membership_repo.list_for_user(user_id)
        result = []
        for m in memberships:
            org = await self.org_repo.get_by_id(str(m.org_id))
            if org and org.status == "active":
                result.append(
                    OrgAccess(
                        org_id=str(m.org_id),
                        org_name=org.name,
                        role="org_admin" if m.is_admin else "user",
                    )
                )
        return sorted(result, key=lambda x: x.org_id)

    async def update_user_password(
        self, user_id: str, current_password: str, new_password: str
    ) -> None:
        """Update a user's password after verifying the current one.

        Args:
            user_id: User identifier
            current_password: Current plain-text password for verification
            new_password: New plain-text password to set

        Raises:
            ValueError: If current password is incorrect or user not found
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.password_hash:
            raise ValueError("Invalid credentials")

        if not _verify_password(current_password, user.password_hash):
            raise ValueError("Current password is incorrect")

        new_hash = _hash_password(new_password)

        from sqlalchemy import select

        from cadence.infrastructure.persistence.postgresql.models import User

        async with self.user_repo.client.session() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            db_user = result.scalar_one_or_none()
            if db_user:
                db_user.password_hash = new_hash
                await session.flush()

        logger.info(f"Password updated for user: {user_id}")

    async def _resolve_memberships(self, user_id: str) -> tuple[List[str], List[str]]:
        """Split org memberships into admin and user lists.

        Args:
            user_id: User identifier

        Returns:
            Tuple of (org_admin_ids, org_user_ids)
        """
        memberships = await self.membership_repo.list_for_user(user_id)
        org_admin = [str(m.org_id) for m in memberships if m.is_admin]
        org_user = [str(m.org_id) for m in memberships if not m.is_admin]
        return org_admin, org_user
