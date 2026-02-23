"""Orchestrator service for processing chat requests.

This module provides high-level chat processing using orchestrators,
managing conversation history and state.
"""

import logging
from typing import Any, AsyncIterator, Dict, Optional

from cadence_sdk.types.sdk_messages import UvHumanMessage
from cadence_sdk.types.sdk_state import create_initial_state

from cadence.constants import DEFAULT_CONVERSATION_HISTORY_LIMIT
from cadence.engine.pool import OrchestratorPool
from cadence.infrastructure.streaming import StreamEvent
from cadence.service.conversation_service import ConversationService

logger = logging.getLogger(__name__)


class OrchestratorService:
    """Service for processing chat requests through orchestrators.

    Attributes:
        pool: Orchestrator pool
        conversation_service: Conversation service
        settings_resolver: Settings resolver (optional)
    """

    def __init__(
        self,
        pool: OrchestratorPool,
        conversation_service: ConversationService,
        settings_resolver: Optional[Any] = None,
    ):
        """Initialize orchestrator service.

        Args:
            pool: Orchestrator pool
            conversation_service: Conversation service
            settings_resolver: Optional settings resolver
        """
        self.pool = pool
        self.conversation_service = conversation_service
        self.settings_resolver = settings_resolver

    async def process_chat(
        self,
        org_id: str,
        instance_id: str,
        user_id: str,
        message: str,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process chat request (single-shot, non-streaming).

        Args:
            org_id: Organization ID
            instance_id: Orchestrator instance ID
            user_id: User ID
            message: User message text
            conversation_id: Optional existing conversation ID

        Returns:
            Result dictionary with response and metadata
        """
        logger.info(f"Processing chat for instance {instance_id}, user {user_id}")

        if not conversation_id:
            conversation_id = await self.conversation_service.create_conversation(
                org_id=org_id,
                user_id=user_id,
                instance_id=instance_id,
            )

        history = await self.conversation_service.get_history(
            org_id=org_id,
            conversation_id=conversation_id,
            limit=DEFAULT_CONVERSATION_HISTORY_LIMIT,
        )

        user_message = UvHumanMessage(content=message)

        state = create_initial_state(thread_id=conversation_id)
        state["messages"] = history + [user_message]

        orchestrator = await self.pool.get(instance_id)

        result_state = await orchestrator.ask(state)

        result_messages = result_state.get("messages", [])
        new_messages = result_messages[len(history) :]

        for msg in new_messages:
            await self.conversation_service.save_message(
                org_id=org_id,
                conversation_id=conversation_id,
                message=msg,
            )

        assistant_messages = [msg for msg in new_messages if msg.role == "ai"]

        final_response = assistant_messages[-1].content if assistant_messages else ""

        return {
            "conversation_id": conversation_id,
            "response": final_response,
            "messages": [msg.to_dict() for msg in new_messages],
            "metadata": {
                "agent_hops": result_state.get("agent_hops", 0),
                "current_agent": result_state.get("current_agent", ""),
            },
        }

    async def process_chat_stream(
        self,
        org_id: str,
        instance_id: str,
        user_id: str,
        message: str,
        conversation_id: Optional[str] = None,
    ) -> AsyncIterator[StreamEvent]:
        """Process chat request with streaming.

        Args:
            org_id: Organization ID
            instance_id: Orchestrator instance ID
            user_id: User ID
            message: User message text
            conversation_id: Optional existing conversation ID

        Yields:
            StreamEvent instances
        """
        logger.info(f"Processing streaming chat for instance {instance_id}")

        if not conversation_id:
            conversation_id = await self.conversation_service.create_conversation(
                org_id=org_id,
                user_id=user_id,
                instance_id=instance_id,
            )

        history = await self.conversation_service.get_history(
            org_id=org_id,
            conversation_id=conversation_id,
            limit=DEFAULT_CONVERSATION_HISTORY_LIMIT,
        )

        user_message = UvHumanMessage(content=message)

        state = create_initial_state(thread_id=conversation_id)
        state["messages"] = history + [user_message]

        orchestrator = await self.pool.get(instance_id)

        accumulated_messages = []

        async for event in orchestrator.astream(state):
            yield event

            if event.event_type == "message":
                accumulated_messages.append(event.data)

        await self.conversation_service.save_message(
            org_id=org_id,
            conversation_id=conversation_id,
            message=user_message,
        )

        yield StreamEvent.metadata(
            {
                "conversation_id": conversation_id,
                "saved": True,
            }
        )

    async def get_instance_org_id(self, instance_id: str) -> Optional[str]:
        """Get organization ID for an orchestrator instance.

        Args:
            instance_id: Instance ID

        Returns:
            Organization ID or None if instance not found
        """
        try:
            instance = await self.pool.get(instance_id)
            if hasattr(instance, "org_id"):
                return instance.org_id
            return None
        except Exception:
            return None
