"""Repository for platform-level provider model catalog."""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from sqlalchemy import select

if TYPE_CHECKING:
    from cadence.infrastructure.persistence.postgresql.client import PostgreSQLClient

from cadence.infrastructure.persistence.postgresql.models import ProviderModelConfig


class ProviderModelConfigRepository:
    """Read-only access to the provider model catalog."""

    def __init__(self, client: PostgreSQLClient):
        self.client = client

    async def get_by_provider(self, provider: str) -> List[ProviderModelConfig]:
        """Return all active models for a given provider.

        Args:
            provider: Provider identifier (e.g. "openai")

        Returns:
            List of active ProviderModelConfig rows ordered by model_id
        """
        async with self.client.session() as session:
            result = await session.execute(
                select(ProviderModelConfig)
                .where(
                    ProviderModelConfig.provider == provider.lower(),
                    ProviderModelConfig.is_active.is_(True),
                )
                .order_by(ProviderModelConfig.model_id)
            )
            return list(result.scalars().all())

    async def get_all(self) -> List[ProviderModelConfig]:
        """Return all active model configs across all providers."""
        async with self.client.session() as session:
            result = await session.execute(
                select(ProviderModelConfig)
                .where(ProviderModelConfig.is_active.is_(True))
                .order_by(ProviderModelConfig.provider, ProviderModelConfig.model_id)
            )
            return list(result.scalars().all())
