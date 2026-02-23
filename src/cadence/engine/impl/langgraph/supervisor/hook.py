"""Node lifecycle hooks for LangGraph orchestration.

Provides decorators to inject behavior at node boundaries with proper
context access for streaming and observability.
"""

import logging
from functools import wraps

from langgraph.config import get_stream_writer

from cadence.engine.impl.langgraph.state import MessageState
from cadence.engine.impl.langgraph.supervisor.graph_node import GraphNode, NodeDisplay
from cadence.infrastructure.streaming import StreamEventType

logger = logging.getLogger(__name__)


def _emit_node_start_event(node_name: str) -> None:
    """Emit node start event through available channels."""
    try:
        if node_name not in GraphNode.values():
            return
        stream_writer = get_stream_writer()
        stream_writer({StreamEventType.AGENT: NodeDisplay.get_by_name(node_name)})
    except RuntimeError:
        logger.debug(
            "_emit_node_start_event called outside LangGraph context for node: %s",
            node_name,
        )


def with_node_start_hook():
    """Decorator injecting node start event emission with LangGraph context."""

    def decorator(func):
        @wraps(func)
        def sync_wrapper(self, state: MessageState, *args, **kwargs):
            node_name = func(self, state, *args, **kwargs)
            _emit_node_start_event(node_name)
            return node_name

        return sync_wrapper

    return decorator
