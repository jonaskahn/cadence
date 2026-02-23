from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select

if TYPE_CHECKING:
    from cadence.infrastructure.persistence.postgresql.client import PostgreSQLClient

from cadence.infrastructure.persistence.postgresql.models import (
    OrganizationLLMConfig,
    utc_now,
)


class OrganizationLLMConfigRepository:
    """Repository for organization LLM configuration operations.

    All mutations are soft-delete only. Queries exclude soft-deleted rows by
    default (include_deleted=False). The api_key column stores the raw (or
    service-encrypted) key; masking happens at the controller layer.
    """

    def __init__(self, client: PostgreSQLClient):
        self.client = client

    async def get_all_for_org(
        self, org_id: str | UUID, include_deleted: bool = False
    ) -> List[OrganizationLLMConfig]:
        """Retrieve LLM configs for an organization.

        Args:
            org_id: Organization identifier
            include_deleted: If True, include soft-deleted rows

        Returns:
            List of OrganizationLLMConfig instances
        """
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        async with self.client.session() as session:
            query = select(OrganizationLLMConfig).where(
                OrganizationLLMConfig.org_id == org_id
            )
            if not include_deleted:
                query = query.where(~OrganizationLLMConfig.is_deleted)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_by_id(self, config_id: int) -> Optional[OrganizationLLMConfig]:
        """Retrieve LLM config by primary key (includes soft-deleted rows).

        Args:
            config_id: Primary key

        Returns:
            OrganizationLLMConfig instance or None
        """
        async with self.client.session() as session:
            result = await session.execute(
                select(OrganizationLLMConfig).where(
                    OrganizationLLMConfig.id == config_id,
                )
            )
            return result.scalar_one_or_none()

    async def get_by_name(
        self, org_id: str | UUID, name: str
    ) -> Optional[OrganizationLLMConfig]:
        """Retrieve active (non-deleted) LLM config by name.

        Args:
            org_id: Organization identifier
            name: Configuration name

        Returns:
            OrganizationLLMConfig instance or None
        """
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(OrganizationLLMConfig).where(
                    OrganizationLLMConfig.org_id == org_id,
                    OrganizationLLMConfig.name == name,
                    ~OrganizationLLMConfig.is_deleted,
                )
            )
            return result.scalar_one_or_none()

    async def create(
        self,
        org_id: str | UUID,
        name: str,
        provider: str,
        api_key: str,
        base_url: Optional[str] = None,
        additional_config: Optional[Dict[str, Any]] = None,
        caller_id: Optional[str] = None,
    ) -> OrganizationLLMConfig:
        """Create new LLM configuration.

        Args:
            org_id: Organization identifier
            name: Configuration name (unique within org among non-deleted rows)
            provider: LLM provider
            api_key: API key
            base_url: Optional custom base URL
            additional_config: Optional provider-specific extra settings (JSONB)
            caller_id: User ID performing the operation

        Returns:
            Created OrganizationLLMConfig instance
        """
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        async with self.client.session() as session:
            config = OrganizationLLMConfig(
                org_id=org_id,
                name=name,
                provider=provider,
                api_key=api_key,
                base_url=base_url,
                additional_config=additional_config or {},
                created_by=caller_id,
            )
            session.add(config)
            await session.flush()
            return config

    async def update(
        self,
        org_id: str | UUID,
        name: str,
        caller_id: Optional[str] = None,
        **updates,
    ) -> Optional[OrganizationLLMConfig]:
        """Update an active LLM configuration.

        Args:
            org_id: Organization identifier
            name: Configuration name
            caller_id: User ID performing the operation
            **updates: Fields to update

        Returns:
            Updated OrganizationLLMConfig instance or None
        """
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(OrganizationLLMConfig).where(
                    OrganizationLLMConfig.org_id == org_id,
                    OrganizationLLMConfig.name == name,
                    ~OrganizationLLMConfig.is_deleted,
                )
            )
            config = result.scalar_one_or_none()

            if config:
                for key, value in updates.items():
                    setattr(config, key, value)
                config.updated_by = caller_id
                await session.flush()
            return config

    async def soft_delete(
        self, org_id: str | UUID, name: str, caller_id: Optional[str] = None
    ) -> bool:
        """Soft-delete an LLM configuration.

        Sets is_deleted=True. The row is retained for
        audit purposes but invisible to the LLM factory and normal queries.

        Args:
            org_id: Organization identifier
            name: Configuration name
            caller_id: User ID performing the operation

        Returns:
            True if the row was found and soft-deleted, False otherwise
        """
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(OrganizationLLMConfig).where(
                    OrganizationLLMConfig.org_id == org_id,
                    OrganizationLLMConfig.name == name,
                    ~OrganizationLLMConfig.is_deleted,
                )
            )
            config = result.scalar_one_or_none()

            if not config:
                return False

            config.is_deleted = True
            config.updated_at = utc_now()
            config.updated_by = caller_id
            await session.flush()
            return True
