"""RabbitMQ client for Cadence messaging infrastructure."""

import logging
from typing import Optional

import aio_pika
from aio_pika.abc import AbstractRobustConnection

logger = logging.getLogger(__name__)


class RabbitMQClient:
    """Manages a robust RabbitMQ connection.

    Attributes:
        url: AMQP connection URL
        _connection: Underlying aio_pika robust connection
    """

    def __init__(self, url: str):
        self.url = url
        self._connection: Optional[AbstractRobustConnection] = None

    async def connect(self) -> None:
        """Establish a robust AMQP connection."""
        self._connection = await aio_pika.connect_robust(self.url)
        logger.info("RabbitMQ connection established")

    async def disconnect(self) -> None:
        """Close the AMQP connection."""
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
            logger.info("RabbitMQ connection closed")

    def get_connection(self) -> AbstractRobustConnection:
        """Return the active connection.

        Raises:
            RuntimeError: If not connected
        """
        if not self._connection or self._connection.is_closed:
            raise RuntimeError("RabbitMQ client is not connected")
        return self._connection
