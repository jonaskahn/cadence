"""User CRUD and org membership management mixin."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from cadence.infrastructure.persistence.postgresql.models import User, UserOrgMembership
from cadence.repository.user_org_membership_repository import (
    UserOrgMembershipRepository,
)
from cadence.repository.user_repository import UserRepository

logger = logging.getLogger(__name__)


class UserServiceMixin(ABC):
    """Mixin that provides user CRUD and org membership management.

    Requires self.get_user_repo() and self.get_membership_repo() to be set by the inheriting class.
    """

    @abstractmethod
    def get_user_repo(self) -> UserRepository:
        pass

    @abstractmethod
    def get_membership_repo(self) -> UserOrgMembershipRepository:
        pass

    @staticmethod
    def serialize_user(user: User) -> Dict[str, Any]:
        """Serialize a User ORM instance to a plain dict."""
        return {
            "user_id": str(user.id),
            "username": user.username,
            "email": user.email,
            "is_sys_admin": bool(user.is_sys_admin),
            "is_deleted": bool(user.is_deleted),
        }

    @staticmethod
    def _serialize_membership(membership: UserOrgMembership) -> Dict[str, Any]:
        """Serialize a UserOrgMembership ORM instance to a plain dict."""
        return {
            "user_id": str(membership.user_id),
            "org_id": str(membership.org_id),
            "is_admin": bool(membership.is_admin),
            "created_at": (
                membership.created_at.isoformat() if membership.created_at else None
            ),
        }

    @staticmethod
    def _create_password_hash(password: str | None) -> str | None:
        if not password:
            return None
        from passlib.context import CryptContext

        ctx = CryptContext(schemes=["argon2"], deprecated="auto")
        return ctx.hash(password)

    async def create_user(
        self,
        username: str,
        user_id: Optional[str] = None,
        email: Optional[str] = None,
        password: Optional[str] = None,
        is_sys_admin: bool = False,
        caller_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new platform user (not bound to any org).

        Args:
            username: Globally unique username
            user_id: User identifier (auto-generated if not provided)
            email: Optional email address
            password: Raw password string
            is_sys_admin: Platform-wide admin flag
            caller_id: User ID performing the operation

        Returns:
            Created user data (serialized)
        """
        if user_id is None:
            from uuid import uuid4

            user_id = str(uuid4())
        logger.info(f"Creating user {username}")
        password_hash = self._create_password_hash(password)
        user = await self.get_user_repo().create(
            user_id=user_id,
            username=username,
            email=email,
            is_sys_admin=is_sys_admin,
            password_hash=password_hash,
            caller_id=caller_id,
        )
        return self.serialize_user(user)

    async def add_user_to_org(
        self,
        user_id: str,
        org_id: str,
        is_admin: bool = False,
        caller_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add an existing user to an organization.

        Args:
            user_id: User identifier
            org_id: Organization identifier
            is_admin: Whether the user should be an org admin
            caller_id: User ID performing the operation

        Returns:
            Membership data (serialized)
        """
        logger.info(f"Adding user {user_id} to org {org_id} is_admin={is_admin}")
        membership = await self.get_membership_repo().create(
            user_id=user_id,
            org_id=org_id,
            is_admin=is_admin,
            caller_id=caller_id,
        )
        return self._serialize_membership(membership)

    async def update_org_membership(
        self,
        user_id: str,
        org_id: str,
        is_admin: bool,
        caller_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update the admin flag for an existing org membership.

        Args:
            user_id: User identifier
            org_id: Organization identifier
            is_admin: New admin value
            caller_id: User ID performing the operation

        Returns:
            Updated membership data or None if not found
        """
        logger.info(f"Updating membership {user_id}/{org_id} is_admin={is_admin}")
        membership = await self.get_membership_repo().update_admin_flag(
            user_id=user_id,
            org_id=org_id,
            is_admin=is_admin,
            caller_id=caller_id,
        )
        return self._serialize_membership(membership) if membership else None

    async def remove_user_from_org(self, user_id: str, org_id: str) -> bool:
        """Hard-delete the user's membership in this org.

        Args:
            user_id: User identifier
            org_id: Organization identifier

        Returns:
            True if removed, False if not found
        """
        logger.info(f"Removing user {user_id} from org {org_id}")
        return await self.get_membership_repo().delete(user_id=user_id, org_id=org_id)

    async def list_org_members(self, org_id: str) -> List[Dict[str, Any]]:
        """List all members of an organization with their user details.

        Only returns entries where the user account is not soft-deleted.

        Args:
            org_id: Organization identifier

        Returns:
            List of dicts with user + membership data
        """
        memberships = await self.get_membership_repo().list_for_org(org_id)
        result = []
        for m in memberships:
            user = await self.get_user_repo().get_by_id(m.user_id)
            if user and not user.is_deleted:
                entry = self.serialize_user(user)
                entry["is_admin"] = m.is_admin
                result.append(entry)
        return result

    async def delete_user(self, user_id: str, caller_id: Optional[str] = None) -> bool:
        """Soft-delete a user and hard-delete all their org memberships.

        Args:
            user_id: User identifier
            caller_id: User ID performing the operation

        Returns:
            True if deleted, False if not found
        """
        logger.info(f"Soft-deleting user {user_id}")
        deleted = await self.get_user_repo().delete(user_id, caller_id=caller_id)
        if deleted and self.get_membership_repo():
            await self.get_membership_repo().delete_all_for_user(user_id)
        return deleted

    async def search_user(
        self,
        user_id: Optional[str] = None,
        email: Optional[str] = None,
        username: Optional[str] = None,
        requester_is_sys_admin: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Look up a single user by id, email, or username (first non-None wins).

        Args:
            user_id: Exact user ID to look up
            email: Exact email address to look up
            username: Exact username to look up
            requester_is_sys_admin: Whether the requester has sys_admin rights

        Returns:
            Serialized user dict with is_admin=False, or None if not found/hidden
        """
        if user_id:
            user = await self.get_user_repo().get_by_id(user_id)
        elif email:
            user = await self.get_user_repo().get_by_email(email)
        else:
            user = await self.get_user_repo().get_by_username(username)

        if not user or user.is_deleted:
            return None
        if user.is_sys_admin and not requester_is_sys_admin:
            return None

        user_dict = self.serialize_user(user)
        user_dict["is_admin"] = False
        return user_dict

    async def list_all_users(self) -> List[Dict[str, Any]]:
        """List all non-deleted platform users.

        Returns:
            List of serialized user dicts with is_admin=False
        """
        users = await self.get_user_repo().list_all()
        result = []
        for u in users:
            user_dict = self.serialize_user(u)
            user_dict["is_admin"] = False
            result.append(user_dict)
        return result

    async def update_user(
        self,
        user_id: str,
        username: Optional[str] = None,
        email: Optional[str] = None,
        is_sys_admin: Optional[bool] = None,
        caller_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update a platform user's username, email, or sys_admin flag.

        Args:
            user_id: User identifier
            username: New username or None to leave unchanged
            email: New email or None to leave unchanged
            is_sys_admin: New sys_admin flag or None to leave unchanged
            caller_id: User ID performing the operation

        Returns:
            Updated user dict with is_admin=False, or None if not found
        """
        user = await self.get_user_repo().update(
            user_id=user_id,
            username=username,
            email=email,
            is_sys_admin=is_sys_admin,
            caller_id=caller_id,
        )
        if not user:
            return None
        user_dict = self.serialize_user(user)
        user_dict["is_admin"] = False
        return user_dict

    async def add_existing_user_to_org(
        self,
        org_id: str,
        user_id: str,
        is_admin: bool = False,
        caller_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Validate that a user exists and add them to an organization.

        Args:
            org_id: Organization identifier
            user_id: Existing user identifier
            is_admin: Whether the user should be an org admin
            caller_id: User ID performing the operation

        Returns:
            Serialized user dict with is_admin set

        Raises:
            ValueError: If user not found or soft-deleted
        """
        user = await self.get_user_repo().get_by_id(user_id)
        if not user or user.is_deleted:
            raise ValueError(f"User {user_id} not found")

        await self.add_user_to_org(
            user_id=user_id,
            org_id=org_id,
            is_admin=is_admin,
            caller_id=caller_id,
        )
        user_dict = self.serialize_user(user)
        user_dict["is_admin"] = is_admin
        return user_dict

    async def get_org_member(
        self, org_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get a user's details and their admin flag within an org.

        Args:
            org_id: Organization identifier
            user_id: User identifier

        Returns:
            Serialized user dict with is_admin set, or None if not found
        """
        user = await self.get_user_repo().get_by_id(user_id)
        if not user:
            return None
        memberships = await self.get_membership_repo().list_for_user(user_id)
        membership = next(
            (m for m in memberships if str(m.org_id) == str(org_id)), None
        )
        if not membership:
            return None
        user_dict = self.serialize_user(user)
        user_dict["is_admin"] = membership.is_admin
        return user_dict
