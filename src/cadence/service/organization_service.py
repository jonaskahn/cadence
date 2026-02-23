"""Organization CRUD, settings, and LLM configuration mixin."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from cadence_sdk import Loggable

from cadence.constants import SettingValue
from cadence.infrastructure.persistence.postgresql.models import (
    Organization,
    OrganizationSettings,
)


class OrganizationServiceMixin(Loggable, ABC):
    """Mixin that provides organization CRUD, settings, and LLM config management.

    Requires self.get_org_repo(), self.get_org_settings_repo(), self.get_org_llm_config_repo(),
    self.get_membership_repo(), and optionally self.get_instance_repo().
    """

    @abstractmethod
    def get_org_repo(self):
        pass

    @abstractmethod
    def get_org_settings_repo(self):
        pass

    @abstractmethod
    def get_org_llm_config_repo(self):
        pass

    @abstractmethod
    def get_instance_repo(self):
        pass

    @abstractmethod
    def get_membership_repo(self):
        pass

    async def create_org(
        self,
        name: str,
        org_id: Optional[str] = None,
        caller_id: Optional[str] = None,
        display_name: Optional[str] = None,
        domain: Optional[str] = None,
        tier: Optional[str] = None,
        description: Optional[str] = None,
        contact_email: Optional[str] = None,
        website: Optional[str] = None,
        logo_url: Optional[str] = None,
        country: Optional[str] = None,
        timezone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new organization.

        Args:
            name: Organization slug name
            org_id: Organization identifier (auto-generated if not provided)
            caller_id: User ID performing the operation
            display_name: Human-friendly display name
            domain: Organization domain
            tier: Subscription tier
            description: Optional description
            contact_email: Contact email
            website: Website URL
            logo_url: Logo URL
            country: Country
            timezone: Timezone

        Returns:
            Created organization data
        """
        if org_id is None:
            from uuid import uuid4

            org_id = str(uuid4())
        self.logger.info(f"Creating organization: {org_id}")
        org = await self.get_org_repo().create(
            org_id=org_id,
            name=name,
            caller_id=caller_id,
            display_name=display_name,
            domain=domain,
            tier=tier,
            description=description,
            contact_email=contact_email,
            website=website,
            logo_url=logo_url,
            country=country,
            timezone=timezone,
        )
        return self._org_to_response(org)

    @staticmethod
    def _org_to_response(org: Organization) -> Dict[str, Any]:
        """Convert Organization ORM instance to API response dict."""
        return {
            "org_id": str(org.id),
            "name": org.name,
            "status": org.status,
            "created_at": org.created_at.isoformat() if org.created_at else "",
            "display_name": getattr(org, "display_name", None),
            "domain": getattr(org, "domain", None),
            "tier": getattr(org, "subscription_tier", "free") or "free",
            "description": getattr(org, "description", None),
            "contact_email": getattr(org, "contact_email", None),
            "website": getattr(org, "website", None),
            "logo_url": getattr(org, "logo_url", None),
            "country": getattr(org, "country", None),
            "timezone": getattr(org, "timezone", None),
        }

    def _setting_to_response(self, setting: OrganizationSettings) -> Dict[str, Any]:
        """Convert OrganizationSettings ORM to API response format."""
        value_type = self._infer_value_type(setting.value)
        return {
            "key": setting.key,
            "value": setting.value,
            "value_type": value_type,
            "overridable": setting.overridable,
        }

    @staticmethod
    def _infer_value_type(value: Any) -> str:
        """Infer API value_type from Python type."""
        type_map = {
            str: "string",
            int: "number",
            float: "number",
            bool: "boolean",
            dict: "object",
            list: "array",
        }
        return type_map.get(type(value), "string")

    async def get_org(self, org_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve organization by ID.

        Args:
            org_id: Organization identifier

        Returns:
            Organization data or None if not found
        """
        org = await self.get_org_repo().get_by_id(org_id)
        return self._org_to_response(org) if org else None

    async def list_orgs(self) -> List[Dict[str, Any]]:
        """List all organizations.

        Returns:
            List of organization data
        """
        orgs = await self.get_org_repo().get_all()
        return [self._org_to_response(org) for org in orgs]

    async def list_orgs_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        """List active orgs the given user belongs to, including their role.

        Args:
            user_id: User identifier

        Returns:
            List of org dicts with role key ('org_admin' or 'member'), sorted by org_id
        """
        memberships = await self.get_membership_repo().list_for_user(user_id)
        result = []
        for membership in memberships:
            org = await self.get_org_repo().get_by_id(membership.org_id)
            if org and org.status == "active":
                entry = self._org_to_response(org)
                entry["role"] = "org_admin" if membership.is_admin else "member"
                result.append(entry)
        return sorted(result, key=lambda x: x["org_id"])

    async def update_org(
        self,
        org_id: str,
        updates: Dict[str, Any],
        caller_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update organization with partial updates.

        Args:
            org_id: Organization identifier
            updates: Dictionary of fields to update
            caller_id: User ID performing the operation

        Returns:
            Updated organization data or None
        """
        self.logger.info(f"Updating organization: {org_id}")
        org = await self.get_org_repo().update(org_id, updates, caller_id=caller_id)
        return self._org_to_response(org) if org else None

    async def delete_org(self, org_id: str) -> None:
        """Delete organization permanently.

        Args:
            org_id: Organization identifier
        """
        self.logger.info(f"Deleting organization: {org_id}")
        await self.get_org_repo().delete(org_id)

    async def get_setting(self, org_id: str, key: str) -> SettingValue:
        """Get a single organization setting value.

        Args:
            org_id: Organization identifier
            key: Setting key

        Returns:
            Setting value or None if not found
        """
        setting = await self.get_org_settings_repo().get_by_key(org_id, key)
        if not setting:
            return None
        return setting.value if hasattr(setting, "value") else setting.get("value")

    async def set_setting(
        self,
        org_id: str,
        key: str,
        value: SettingValue,
        caller_id: Optional[str] = None,
        overridable: bool = False,
    ) -> Dict[str, Any]:
        """Create or update an organization setting.

        Args:
            org_id: Organization identifier
            key: Setting key
            value: Setting value
            caller_id: User ID performing the operation
            overridable: Whether instances may override this key

        Returns:
            Created or updated setting data (key, value, value_type, overridable)
        """
        self.logger.info(f"Setting organization setting: {org_id}/{key}")
        setting = await self.get_org_settings_repo().upsert(
            org_id=org_id,
            key=key,
            value=value,
            caller_id=caller_id,
            overridable=overridable,
        )
        return self._setting_to_response(setting)

    async def list_settings(self, org_id: str) -> List[Dict[str, Any]]:
        """List all organization settings.

        Args:
            org_id: Organization identifier

        Returns:
            List of setting dicts with key, value, value_type
        """
        settings = await self.get_org_settings_repo().get_all_for_org(org_id)
        return [self._setting_to_response(setting) for setting in settings]

    async def delete_setting(self, org_id: str, key: str) -> None:
        """Delete an organization setting.

        Args:
            org_id: Organization identifier
            key: Setting key
        """
        self.logger.info(f"Deleting organization setting: {org_id}/{key}")
        await self.get_org_settings_repo().delete(org_id, key)

    async def add_llm_config(
        self,
        org_id: str,
        name: str,
        provider: str,
        api_key: str,
        base_url: Optional[str] = None,
        additional_config: Optional[Dict[str, Any]] = None,
        caller_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add LLM configuration for organization.

        Args:
            org_id: Organization ID
            name: Config name
            provider: Provider name (openai, anthropic, google, etc.)
            api_key: API key
            base_url: Optional base URL for provider
            additional_config: Optional provider-specific extra settings
            caller_id: User ID performing the operation

        Returns:
            Created LLM config ORM object
        """
        self.logger.info(f"Adding LLM config for org {org_id}: {provider}/{name}")
        return await self.get_org_llm_config_repo().create(
            org_id=org_id,
            name=name,
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            additional_config=additional_config or {},
            caller_id=caller_id,
        )

    async def get_llm_config_by_id(self, config_id: int):
        """Retrieve an LLM config by its primary key."""
        return await self.get_org_llm_config_repo().get_by_id(config_id)

    async def list_llm_configs(self, org_id: str) -> List[Dict[str, Any]]:
        """List organization's LLM configurations.

        Args:
            org_id: Organization ID

        Returns:
            List of LLM config ORM objects (non-deleted only)
        """
        return await self.get_org_llm_config_repo().get_all_for_org(
            org_id, include_deleted=False
        )

    async def update_llm_config(
        self,
        org_id: str,
        name: str,
        updates: Dict[str, Any],
        caller_id: Optional[str] = None,
    ):
        """Update an LLM configuration (provider is immutable).

        Args:
            org_id: Organization ID
            name: Current config name
            updates: Fields to update (only provided fields are changed)
            caller_id: User ID performing the operation

        Returns:
            Updated LLM config ORM object, or None if not found
        """
        self.logger.info(f"Updating LLM config: {org_id}/{name}")
        return await self.get_org_llm_config_repo().update(
            org_id=org_id,
            name=name,
            caller_id=caller_id,
            **updates,
        )

    async def delete_llm_config(
        self,
        org_id: str,
        name: str,
        caller_id: Optional[str] = None,
    ) -> bool:
        """Soft-delete an LLM configuration.

        Raises ValueError if any active orchestrator instance in the org
        still references this config by name.

        Args:
            org_id: Organization ID
            name: Config name
            caller_id: User ID performing the operation

        Returns:
            True if deleted

        Raises:
            ValueError: If the config is still referenced by active orchestrators
        """
        self.logger.info(f"Deleting LLM config: {org_id}/{name}")

        if self.get_instance_repo() is not None:
            config = await self.get_org_llm_config_repo().get_by_name(org_id, name)
            if config is None:
                return False
            count = await self.get_instance_repo().count_using_llm_config(
                org_id, config.id
            )
            if count > 0:
                raise ValueError(
                    f"LLM config '{name}' is still referenced by {count} active "
                    "orchestrator instance(s). Remove or update those instances first."
                )

        return await self.get_org_llm_config_repo().soft_delete(
            org_id=org_id, name=name, caller_id=caller_id
        )
