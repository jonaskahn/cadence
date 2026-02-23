"""RabbitMQ-based orchestrator load/reload/unload event publisher and consumer."""

import json
import logging
import socket
from typing import Optional

from aio_pika import ExchangeType, Message
from aio_pika.abc import AbstractIncomingMessage

from cadence.engine import OrchestratorPool
from cadence.infrastructure.messaging.rabbitmq_client import RabbitMQClient
from cadence.repository.orchestrator_instance_repository import (
    OrchestratorInstanceRepository,
)
from cadence.repository.plugin_store_repository import PluginStoreRepository

logger = logging.getLogger(__name__)

_EXCHANGE_NAME = "cadence.orchestrators"
_RK_LOAD = "orchestrator.load"
_RK_UNLOAD = "orchestrator.unload"
_RK_RELOAD = "orchestrator.reload"
_RK_SETTINGS_GLOBAL_CHANGED = "settings.global_changed"


def _make_per_node_queue_name(node_name: str) -> str:
    """Unique queue name per node to prevent multiple nodes sharing same queue."""
    return f"cadence.orchestrators.{node_name}"


async def _should_skip_load_due_to_dedup(
    pool: OrchestratorPool,
    instance_id: str,
    instance_repo: OrchestratorInstanceRepository,
) -> bool:
    """Return True if already hot with matching config_hash (dedup)."""
    if not hasattr(pool, "get_hash"):
        return False
    current_hash = pool.get_hash(instance_id)
    if current_hash is None:
        return False
    instance = await instance_repo.get_by_id(instance_id)
    if instance and instance.get("config_hash") == current_hash:
        logger.info(f"Load event dedup: {instance_id} already hot with matching hash")
        return True
    return False


class OrchestratorEventPublisher:
    """Publishes orchestrator lifecycle events to RabbitMQ.

    Attributes:
        client: RabbitMQClient instance
        _channel: AMQP channel
        _exchange: Topic exchange
    """

    def __init__(self, client: RabbitMQClient):
        self.client = client
        self._channel = None
        self._exchange = None

    async def _ensure_exchange(self) -> None:
        if self._exchange is not None:
            return
        connection = self.client.get_connection()
        self._channel = await connection.channel()
        self._exchange = await self._channel.declare_exchange(
            _EXCHANGE_NAME,
            ExchangeType.TOPIC,
            durable=True,
        )

    async def publish_load(self, instance_id: str, org_id: str, tier: str) -> None:
        """Publish orchestrator.load event."""
        await self._ensure_exchange()
        payload = {"instance_id": instance_id, "org_id": org_id, "tier": tier}
        await self._publish(_RK_LOAD, payload)
        logger.info(f"Published load event for {instance_id} (tier={tier})")

    async def publish_unload(self, instance_id: str) -> None:
        """Publish orchestrator.unload event."""
        await self._ensure_exchange()
        payload = {"instance_id": instance_id}
        await self._publish(_RK_UNLOAD, payload)
        logger.info(f"Published unload event for {instance_id}")

    async def publish_reload(
        self, instance_id: str, org_id: str, config_hash: Optional[str]
    ) -> None:
        """Publish orchestrator.reload event."""
        await self._ensure_exchange()
        payload = {
            "instance_id": instance_id,
            "org_id": org_id,
            "config_hash": config_hash,
        }
        await self._publish(_RK_RELOAD, payload)
        logger.info(f"Published reload event for {instance_id}")

    async def publish_global_settings_changed(self) -> None:
        """Publish settings.global_changed event to all nodes."""
        await self._ensure_exchange()
        await self._publish(_RK_SETTINGS_GLOBAL_CHANGED, {})
        logger.info("Published global settings changed event")

    async def _publish(self, routing_key: str, payload: dict) -> None:
        body = json.dumps(payload).encode()
        await self._exchange.publish(
            Message(body=body, content_type="application/json"),
            routing_key=routing_key,
        )


class OrchestratorEventConsumer:
    """Consumes orchestrator lifecycle events from RabbitMQ.

    Uses a per-node unique queue bound to orchestrator.* routing keys.

    Attributes:
        client: RabbitMQClient instance
    """

    def __init__(
        self,
        client: RabbitMQClient,
        pool: OrchestratorPool,
        instance_repo: OrchestratorInstanceRepository,
        plugin_store: PluginStoreRepository,
    ):
        self.client = client
        self._channel = None
        self._consumer_tag = None
        self.pool = pool
        self.instance_repo = instance_repo
        self.plugin_store = plugin_store

    async def start(
        self,
    ) -> None:
        """Declare exchange + queue, bind, and begin consuming."""
        connection = self.client.get_connection()
        self._channel = await connection.channel()
        await self._channel.set_qos(prefetch_count=10)

        exchange = await self._channel.declare_exchange(
            _EXCHANGE_NAME,
            ExchangeType.TOPIC,
            durable=True,
        )

        node_name = socket.gethostname()
        queue_name = _make_per_node_queue_name(node_name)
        queue = await self._channel.declare_queue(queue_name, durable=True)

        await queue.bind(exchange, routing_key="orchestrator.*")
        await queue.bind(exchange, routing_key="settings.*")

        self._consumer_tag = await queue.consume(lambda msg: self._dispatch(msg))
        logger.info(f"Orchestrator event consumer started (queue={queue_name})")

    async def stop(self) -> None:
        """Cancel the consumer and close the channel."""
        if self._channel and not self._channel.is_closed:
            if self._consumer_tag:
                try:
                    await self._channel.cancel(self._consumer_tag)
                except Exception:
                    pass
            await self._channel.close()
        logger.info("Orchestrator event consumer stopped")

    async def _dispatch(self, message: AbstractIncomingMessage) -> None:
        async with message.process(requeue=False):
            try:
                event = json.loads(message.body)
                routing_key = message.routing_key

                if routing_key == _RK_LOAD:
                    await _handle_load(
                        event,
                        self.pool,
                        self.instance_repo,
                        self.plugin_store,
                    )
                elif routing_key == _RK_RELOAD:
                    await _handle_reload(
                        event,
                        self.pool,
                        self.instance_repo,
                    )
                elif routing_key == _RK_UNLOAD:
                    await _handle_unload(event, self.pool)
                elif routing_key == _RK_SETTINGS_GLOBAL_CHANGED:
                    await _handle_global_settings_changed(
                        event,
                        self.pool,
                        self.instance_repo,
                    )
                else:
                    logger.warning(f"Unknown routing key: {routing_key}")
            except Exception as e:
                logger.error(f"Error handling orchestrator event: {e}", exc_info=True)


async def _download_plugins(
    active_plugins: list,
    plugin_store: PluginStoreRepository,
    org_id: str,
) -> None:
    """Ensure all active plugins are present locally.

    Args:
        active_plugins: List of 'pid@version' plugin references
        plugin_store: Plugin store for fetching remote plugins
        org_id: Organization identifier
    """
    if plugin_store is None:
        return
    for plugin_ref in active_plugins:
        try:
            pid, version = _parse_plugin_ref(plugin_ref)
            await plugin_store.ensure_local(pid=pid, version=version, org_id=org_id)
        except Exception as exc:
            logger.warning(f"Could not ensure local plugin {plugin_ref}: {exc}")


async def _handle_load(
    event: dict,
    pool: OrchestratorPool,
    instance_repo: OrchestratorInstanceRepository,
    plugin_store: PluginStoreRepository,
) -> None:
    """Handle orchestrator.load event."""
    instance_id = event.get("instance_id")
    org_id = event.get("org_id")

    if not instance_id or not org_id:
        logger.warning(f"Load event missing instance_id or org_id: {event}")
        return

    if await _should_skip_load_due_to_dedup(pool, instance_id, instance_repo):
        return

    instance = await instance_repo.get_by_id(instance_id)
    if not instance:
        logger.warning(f"Load event: instance {instance_id} not found in DB")
        return

    active_plugins = instance.get("config", {}).get("active_plugins", [])
    await _download_plugins(active_plugins, plugin_store, org_id)

    resolved_config = {**instance["config"], "org_id": instance["org_id"]}

    if instance_id in pool.hot_tier:
        await pool.reload_instance(
            instance_id=instance_id,
            org_id=instance["org_id"],
            framework_type=instance["framework_type"],
            mode=instance["mode"],
            instance_config=instance["config"],
            resolved_config=resolved_config,
        )
    else:
        try:
            await pool.create_instance(
                instance_id=instance_id,
                org_id=instance["org_id"],
                framework_type=instance["framework_type"],
                mode=instance["mode"],
                instance_config=instance["config"],
                resolved_config=resolved_config,
            )
        except ValueError:
            await pool.reload_instance(
                instance_id=instance_id,
                org_id=instance["org_id"],
                framework_type=instance["framework_type"],
                mode=instance["mode"],
                instance_config=instance["config"],
                resolved_config=resolved_config,
            )

    if hasattr(pool, "set_hash") and instance.get("config_hash"):
        pool.set_hash(instance_id, instance["config_hash"])

    logger.info(f"Instance {instance_id} loaded into hot tier")


async def _handle_reload(
    event: dict,
    pool: OrchestratorPool,
    instance_repo: OrchestratorInstanceRepository,
) -> None:
    """Handle orchestrator.reload event."""
    instance_id = event.get("instance_id")
    config_hash = event.get("config_hash")

    if not instance_id:
        return

    if hasattr(pool, "get_hash"):
        current_hash = pool.get_hash(instance_id)
        if current_hash is not None and current_hash == config_hash:
            logger.info(f"Reload event dedup: {instance_id} hash unchanged")
            return

    if instance_id not in pool.hot_tier:
        logger.debug(f"Reload event: {instance_id} not in hot tier, skipping")
        return

    instance = await instance_repo.get_by_id(instance_id)
    if not instance:
        return

    resolved_config = {**instance["config"], "org_id": instance["org_id"]}

    await pool.reload_instance(
        instance_id=instance_id,
        org_id=instance["org_id"],
        framework_type=instance["framework_type"],
        mode=instance["mode"],
        instance_config=instance["config"],
        resolved_config=resolved_config,
    )

    if hasattr(pool, "set_hash") and config_hash:
        pool.set_hash(instance_id, config_hash)

    logger.info(f"Instance {instance_id} reloaded")


async def _handle_unload(event: dict, pool: OrchestratorPool) -> None:
    """Handle orchestrator.unload event."""
    instance_id = event.get("instance_id")
    if not instance_id:
        return

    if instance_id in pool.hot_tier:
        try:
            await pool.remove_instance(instance_id)
            logger.info(f"Instance {instance_id} unloaded from hot tier")
        except Exception as exc:
            logger.error(f"Failed to unload {instance_id}: {exc}")
    else:
        logger.debug(f"Unload event: {instance_id} not in hot tier")


async def _handle_global_settings_changed(
    event: dict,
    pool: OrchestratorPool,
    instance_repo: OrchestratorInstanceRepository,
) -> None:
    """Handle settings.global_changed event.

    Reloads all hot-tier instances with fresh resolved config so that
    updated global settings take effect without a restart.
    """
    hot_instance_ids = list(pool.hot_tier.keys())
    reloaded = 0

    for instance_id in hot_instance_ids:
        try:
            instance = await instance_repo.get_by_id(instance_id)
            if not instance:
                continue

            resolved_config = {**instance["config"], "org_id": instance["org_id"]}

            await pool.reload_instance(
                instance_id=instance_id,
                org_id=instance["org_id"],
                framework_type=instance["framework_type"],
                mode=instance["mode"],
                instance_config=instance["config"],
                resolved_config=resolved_config,
            )
            reloaded += 1
        except Exception as exc:
            logger.error(
                f"Failed to reload instance {instance_id} after global settings change: {exc}",
                exc_info=True,
            )

    logger.info(
        f"Global settings changed: reloaded {reloaded}/{len(hot_instance_ids)} hot-tier instances"
    )


def _parse_plugin_ref(plugin_ref: str) -> tuple[str, str]:
    """Parse 'pid@version' or 'pid' (returns 'latest' for bare pid)."""
    if "@" in plugin_ref:
        pid, version = plugin_ref.split("@", 1)
        return pid, version
    return plugin_ref, "latest"
