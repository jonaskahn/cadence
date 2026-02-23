"""Redis-backed session store for ULID-keyed JWT sessions.

Stores session data (org memberships, sys_admin flag) in Redis keyed by the
JWT's jti (a ULID). Provides instant revocation: deleting the Redis key
invalidates the token regardless of JWT expiry.

Redis key layout:
  session:{jti}          → JSON session payload, TTL
  user_sessions:{user_id} → Redis Set of active jti values (for bulk revocation)
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from ulid import ULID

from cadence.constants import DEFAULT_SESSION_TTL_SECONDS

logger = logging.getLogger(__name__)

SESSION_KEY_PREFIX = "session"
USER_SESSIONS_KEY_PREFIX = "user_sessions"


def _session_key(jti: str) -> str:
    return f"{SESSION_KEY_PREFIX}:{jti}"


def _user_sessions_key(user_id: str) -> str:
    return f"{USER_SESSIONS_KEY_PREFIX}:{user_id}"


@dataclass
class TokenSession:
    """In-memory representation of a Redis session entry.

    Attributes:
        jti: JWT ID — the ULID used as Redis key and JWT jti claim
        user_id: Authenticated user identifier
        is_sys_admin: Platform-wide admin flag
        org_admin: Organization IDs where user has admin rights
        org_user: Organization IDs where user is a regular member
        created_at: Session creation time (ISO format)
        expires_at: Session expiry time (ISO format)
    """

    jti: str
    user_id: str
    is_sys_admin: bool
    org_admin: List[str] = field(default_factory=list)
    org_user: List[str] = field(default_factory=list)
    created_at: str = ""
    expires_at: str = ""

    def is_member_of(self, org_id: str) -> bool:
        """Check whether the session has any access to the given org."""
        return org_id in self.org_admin or org_id in self.org_user

    def is_admin_of(self, org_id: str) -> bool:
        """Check whether the session has admin access to the given org."""
        return org_id in self.org_admin


class SessionStoreRepository:
    """CRUD operations for Redis-backed JWT sessions.

    Attributes:
        redis: Redis async client
        default_ttl_seconds: Default session lifetime in seconds
    """

    def __init__(self, redis, default_ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS):
        """Initialize the session store.

        Args:
            redis: Connected redis.asyncio.Redis client
            default_ttl_seconds: Session TTL (default 30 minutes)
        """
        self.redis = redis
        self.default_ttl_seconds = default_ttl_seconds

    @staticmethod
    def generate_jti() -> str:
        """Generate a new ULID string for use as JWT jti.

        Returns:
            ULID string
        """
        return str(ULID())

    async def create_session(
        self,
        user_id: str,
        is_sys_admin: bool,
        org_admin: List[str],
        org_user: List[str],
        ttl_seconds: Optional[int] = None,
    ) -> TokenSession:
        """Create and persist a new session in Redis.

        Args:
            user_id: Authenticated user identifier
            is_sys_admin: Platform-wide admin flag
            org_admin: Org IDs where user has admin rights
            org_user: Org IDs where user is a regular member
            ttl_seconds: Session lifetime (defaults to store default)

        Returns:
            Created TokenSession with generated jti
        """
        ttl = ttl_seconds or self.default_ttl_seconds
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl)

        jti = self.generate_jti()
        session = TokenSession(
            jti=jti,
            user_id=user_id,
            is_sys_admin=is_sys_admin,
            org_admin=org_admin,
            org_user=org_user,
            created_at=now.isoformat(),
            expires_at=expires_at.isoformat(),
        )

        payload = json.dumps(
            {
                "jti": session.jti,
                "user_id": session.user_id,
                "is_sys_admin": session.is_sys_admin,
                "org_admin": session.org_admin,
                "org_user": session.org_user,
                "created_at": session.created_at,
                "expires_at": session.expires_at,
            }
        )

        await self.redis.setex(_session_key(jti), ttl, payload)
        await self.redis.sadd(_user_sessions_key(user_id), jti)

        logger.debug(f"Session created: jti={jti} user={user_id} ttl={ttl}s")
        return session

    async def get_session(self, jti: str) -> Optional[TokenSession]:
        """Retrieve a session by its jti.

        Args:
            jti: JWT ID (ULID string)

        Returns:
            TokenSession or None if not found / expired
        """
        raw = await self.redis.get(_session_key(jti))
        if raw is None:
            return None

        data = json.loads(raw)
        return TokenSession(
            jti=data["jti"],
            user_id=data["user_id"],
            is_sys_admin=data["is_sys_admin"],
            org_admin=data.get("org_admin", []),
            org_user=data.get("org_user", []),
            created_at=data.get("created_at", ""),
            expires_at=data.get("expires_at", ""),
        )

    async def delete_session(self, jti: str) -> None:
        """Revoke a single session by jti.

        Args:
            jti: JWT ID to revoke
        """
        raw = await self.redis.get(_session_key(jti))
        if raw:
            data = json.loads(raw)
            user_id = data.get("user_id")
            if user_id:
                await self.redis.srem(_user_sessions_key(user_id), jti)
        await self.redis.delete(_session_key(jti))
        logger.debug(f"Session revoked: jti={jti}")

    async def delete_all_user_sessions(self, user_id: str) -> None:
        """Revoke all active sessions for a user.

        Useful when removing a user from an org or disabling an account.

        Args:
            user_id: User identifier
        """
        user_key = _user_sessions_key(user_id)
        jtis = await self.redis.smembers(user_key)

        if jtis:
            session_keys = [_session_key(jti) for jti in jtis]
            await self.redis.delete(*session_keys)

        await self.redis.delete(user_key)
        logger.debug(f"All sessions revoked for user={user_id} count={len(jtis)}")
