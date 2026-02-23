"""MongoDB async client using Motor.

Provides connection management and database-per-organization access.
"""

from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


class MongoDBClient:
    """MongoDB client for async database operations.

    Manages MongoDB connection and provides database access per organization.

    Attributes:
        url: MongoDB connection URL
        client: Motor async client
    """

    def __init__(self, url: str):
        """Initialize MongoDB client.

        Args:
            url: MongoDB connection URL
        """
        self.url = url
        self.client: Optional[AsyncIOMotorClient] = None

    async def connect(self) -> None:
        """Create MongoDB client connection."""
        if self.client is None:
            self.client = AsyncIOMotorClient(self.url)

    async def disconnect(self) -> None:
        """Close MongoDB client connection."""
        if self.client is not None:
            self.client.close()
            self.client = None

    def get_database(self, org_id: str) -> AsyncIOMotorDatabase:
        """Get MongoDB database for organization.

        Uses database-per-organization strategy: cadence_{org_id}

        Args:
            org_id: Organization identifier

        Returns:
            AsyncIOMotorDatabase instance for the organization
        """
        if self.client is None:
            raise RuntimeError("Client not connected. Call connect() first.")

        database_name = f"cadence_{org_id}"
        return self.client[database_name]
