from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import select

if TYPE_CHECKING:
    from cadence.infrastructure.persistence.postgresql.client import PostgreSQLClient

from cadence.infrastructure.persistence.postgresql.models import User, utc_now


class UserRepository:
    """Repository for user operations.

    Users are platform-level entities. Org membership is tracked separately
    in UserOrgMembershipRepository.

    Attributes:
        client: PostgreSQL client for database access
    """

    def __init__(self, client: PostgreSQLClient):
        self.client = client

    async def create(
        self,
        user_id: str | UUID,
        username: str,
        email: Optional[str] = None,
        is_sys_admin: bool = False,
        password_hash: Optional[str] = None,
        caller_id: Optional[str] = None,
    ) -> User:
        """Create new user.

        Args:
            user_id: User identifier (UUID or string)
            username: Globally unique username (among non-deleted users)
            email: Optional email address
            is_sys_admin: Platform-wide admin flag
            password_hash: Pre-hashed password string
            caller_id: User ID performing the operation

        Returns:
            Created User instance
        """
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        async with self.client.session() as session:
            user = User(
                id=user_id,
                username=username,
                email=email,
                is_sys_admin=is_sys_admin,
                password_hash=password_hash,
                created_by=caller_id,
            )
            session.add(user)
            await session.flush()
            return user

    async def get_by_id(self, user_id: str | UUID) -> Optional[User]:
        """Retrieve user by ID.

        Args:
            user_id: User identifier (UUID or string)

        Returns:
            User instance or None
        """
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        async with self.client.session() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        """Retrieve active user by username (globally unique).

        Args:
            username: Username

        Returns:
            User instance or None
        """
        async with self.client.session() as session:
            result = await session.execute(
                select(User).where(
                    User.username == username,
                    ~User.is_deleted,
                )
            )
            return result.scalar_one_or_none()

    async def list_all(self) -> List[User]:
        """Retrieve all non-deleted users ordered by creation date.

        Returns:
            List of User instances
        """
        async with self.client.session() as session:
            result = await session.execute(
                select(User).where(~User.is_deleted).order_by(User.created_at.desc())
            )
            return list(result.scalars().all())

    async def update(
        self,
        user_id: str | UUID,
        username: Optional[str] = None,
        email: Optional[str] = None,
        is_sys_admin: Optional[bool] = None,
        caller_id: Optional[str] = None,
    ) -> Optional[User]:
        """Update user fields (username, email, is_sys_admin).

        Args:
            user_id: User identifier (UUID or string)
            username: New username or None to leave unchanged
            email: New email or None to leave unchanged
            is_sys_admin: New sys_admin flag or None to leave unchanged
            caller_id: User ID performing the operation

        Returns:
            Updated User instance or None if not found
        """
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(User).where(User.id == user_id, ~User.is_deleted)
            )
            user = result.scalar_one_or_none()
            if user:
                if username is not None:
                    user.username = username
                if email is not None:
                    user.email = email
                if is_sys_admin is not None:
                    user.is_sys_admin = is_sys_admin
                user.updated_by = caller_id
                user.updated_at = utc_now()
                await session.flush()
            return user

    async def get_by_email(self, email: str) -> Optional[User]:
        """Retrieve active user by email address.

        Args:
            email: Email address

        Returns:
            User instance or None
        """
        async with self.client.session() as session:
            result = await session.execute(
                select(User).where(
                    User.email == email,
                    ~User.is_deleted,
                )
            )
            return result.scalar_one_or_none()

    async def update_password(
        self, user_id: str | UUID, password_hash: str, caller_id: Optional[str] = None
    ) -> Optional[User]:
        """Update user password hash.

        Args:
            user_id: User identifier (UUID or string)
            password_hash: New pre-hashed password string
            caller_id: User ID performing the operation

        Returns:
            Updated User instance or None if not found
        """
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(User).where(User.id == user_id, ~User.is_deleted)
            )
            user = result.scalar_one_or_none()
            if user:
                user.password_hash = password_hash
                user.updated_by = caller_id
                user.updated_at = utc_now()
                await session.flush()
            return user

    async def delete(
        self, user_id: str | UUID, caller_id: Optional[str] = None
    ) -> bool:
        """Soft-delete a user.

        Sets is_deleted=True. The user record is
        retained for audit purposes.

        Args:
            user_id: User identifier (UUID or string)
            caller_id: User ID performing the operation

        Returns:
            True if found and soft-deleted, False if not found or already deleted
        """
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(User).where(User.id == user_id, ~User.is_deleted)
            )
            user = result.scalar_one_or_none()

            if not user:
                return False

            user.is_deleted = True
            user.updated_at = utc_now()
            user.updated_by = caller_id
            await session.flush()
            return True
