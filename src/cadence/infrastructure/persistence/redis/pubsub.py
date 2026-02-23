"""Redis pub/sub for configuration change notifications.

Enables real-time configuration updates across multiple service instances
using Redis publish/subscribe pattern.
"""

import asyncio
import json
from typing import Any, Callable, Dict, Optional

from redis.asyncio import Redis
from redis.asyncio.client import PubSub


class RedisPubSub:
    """Redis pub/sub for configuration changes.

    Publishes and subscribes to configuration change events.
    Used for hot-reload of orchestrator instances.

    Attributes:
        client: Async Redis client
        channel: Pub/sub channel name
        pubsub: Redis PubSub instance
    """

    DEFAULT_CHANNEL = "cadence:config_changes"

    def __init__(self, client: Redis, channel: str = DEFAULT_CHANNEL):
        self.client = client
        self.channel = channel
        self.pubsub: Optional[PubSub] = None
        self._listen_task: Optional[asyncio.Task] = None

    async def publish(self, event: Dict[str, Any]) -> int:
        """Publish configuration change event.

        Args:
            event: Event data dictionary

        Returns:
            Number of subscribers that received the message
        """
        message = json.dumps(event)
        return await self.client.publish(self.channel, message)

    async def publish_orchestrator_reload(self, instance_id: str) -> int:
        """Publish orchestrator reload event.

        Args:
            instance_id: Orchestrator instance identifier

        Returns:
            Number of subscribers
        """
        event = {
            "event": "orchestrator_reload",
            "instance_id": instance_id,
        }
        return await self.publish(event)

    async def publish_settings_update(
        self, tier: str, org_id: Optional[str] = None
    ) -> int:
        """Publish settings update event.

        Args:
            tier: Settings tier (global, organization, instance)
            org_id: Optional organization identifier

        Returns:
            Number of subscribers
        """
        event = {
            "event": "settings_update",
            "tier": tier,
        }

        if org_id:
            event["org_id"] = org_id

        return await self.publish(event)

    async def subscribe(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Subscribe to configuration change events.

        Args:
            callback: Function to call when event is received
        """
        if self.pubsub is None:
            self.pubsub = self.client.pubsub()
            await self.pubsub.subscribe(self.channel)

        self._listen_task = asyncio.create_task(self._listen_for_messages(callback))

    async def _listen_for_messages(
        self, callback: Callable[[Dict[str, Any]], None]
    ) -> None:
        """Internal listener for pub/sub messages.

        Args:
            callback: Function to call with parsed event data
        """
        if self.pubsub is None:
            return

        async for message in self.pubsub.listen():
            if message["type"] == "message":
                try:
                    event = json.loads(message["data"])
                    callback(event)
                except json.JSONDecodeError:
                    pass

    async def unsubscribe(self) -> None:
        """Unsubscribe from pub/sub channel."""
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
            self._listen_task = None

        if self.pubsub:
            await self.pubsub.unsubscribe(self.channel)
            await self.pubsub.aclose()
            self.pubsub = None
