"""Orchestrator service for processing chat requests.

This module provides high-level chat processing using orchestrators,
managing conversation history and state.
"""

from typing import Any, AsyncIterator, Optional

from cadence_sdk import Loggable, UvAIMessage, UvState
from cadence_sdk.types.sdk_messages import UvHumanMessage
from cadence.engine.utils.message_utils import count_tokens_estimate

from cadence.constants import DEFAULT_CONVERSATION_HISTORY_LIMIT
from cadence.engine.pool import OrchestratorPool
from cadence.infrastructure.streaming import StreamEvent
from cadence.service.conversation_service import ConversationService


class OrchestratorService(Loggable):
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
        self.pool = pool
        self.conversation_service = conversation_service
        self.settings_resolver = settings_resolver

    async def _prepare_context(
        self,
        org_id: str,
        instance_id: str,
        user_id: str,
        message: str,
        conversation_id: Optional[str],
    ) -> tuple[str, "UvState", Any, "UvHumanMessage"]:
        if not conversation_id:
            conversation_id = await self.conversation_service.create_conversation(
                org_id=org_id,
                user_id=user_id,
                instance_id=instance_id,
            )

        orchestrator = await self.pool.get(instance_id)

        history = await self.conversation_service.get_history(
            org_id=org_id,
            conversation_id=conversation_id,
            limit=DEFAULT_CONVERSATION_HISTORY_LIMIT,
        )
        user_message = UvHumanMessage(content=message)
        all_messages = history + [user_message]

        # Autocompact check: summarize history if either context limit exceeded
        settings = getattr(getattr(orchestrator, "mode_config", None), "settings", None)
        max_ctx = getattr(settings, "max_context_window", 0)
        msg_ctx = getattr(settings, "message_context_window", 0)
        token_exceeded = (
            isinstance(max_ctx, int)
            and max_ctx
            and count_tokens_estimate(all_messages) > max_ctx
        )
        msg_count_exceeded = (
            isinstance(msg_ctx, int) and msg_ctx and len(history) > msg_ctx
        )
        if token_exceeded or msg_count_exceeded:
            if getattr(settings, "enabled_auto_compact", False):
                try:
                    summary = await orchestrator.compact_history(history)
                    await self.conversation_service.compact_conversation(
                        org_id=org_id,
                        conversation_id=conversation_id,
                        human_summary="[Previous conversation summary]",
                        ai_summary=summary,
                    )
                    all_messages = [
                        UvHumanMessage(content="[Previous conversation summary]"),
                        UvAIMessage(content=summary),
                        user_message,
                    ]
                    self.logger.info(
                        "Autocompacted conversation %s for instance %s",
                        conversation_id,
                        instance_id,
                    )
                except Exception as e:
                    self.logger.warning(
                        "Autocompact failed for conversation %s: %s",
                        conversation_id,
                        e,
                        exc_info=True,
                    )
            else:
                reason = (
                    f"token count exceeded ({count_tokens_estimate(all_messages)} > {max_ctx})"
                    if token_exceeded
                    else f"message count exceeded ({len(history)} > {msg_ctx})"
                )
                raise RuntimeError(
                    f"Context limit reached: {reason}. Enable autocompact to handle long conversations."
                )

        state = UvState(messages=all_messages, thread_id=conversation_id)
        return conversation_id, state, orchestrator, user_message

    async def process_chat(
        self,
        org_id: str,
        instance_id: str,
        user_id: str,
        message: str,
        conversation_id: Optional[str] = None,
    ) -> dict:
        """Process chat request and return a structured response."""
        conv_id, state, orchestrator, user_message = await self._prepare_context(
            org_id, instance_id, user_id, message, conversation_id
        )
        result = await orchestrator.ask(state)
        messages = result.get("messages", [])
        response = next(
            (msg.content for msg in reversed(messages) if isinstance(msg, UvAIMessage)),
            "",
        )
        await self.conversation_service.save_message(
            org_id=org_id, conversation_id=conv_id, message=user_message
        )
        await self.conversation_service.save_message(
            org_id=org_id,
            conversation_id=conv_id,
            message=UvAIMessage(content=response),
        )
        return {
            "conversation_id": conv_id,
            "response": response,
            "messages": messages,
            "metadata": {
                "agent_hops": result.get("agent_hops", 0),
                "current_agent": result.get("current_agent", ""),
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
        """Process chat request with streaming."""
        self.logger.info("Processing streaming chat for instance %s", instance_id)
        conv_id, state, orchestrator, user_message = await self._prepare_context(
            org_id, instance_id, user_id, message, conversation_id
        )
        yield StreamEvent.metadata({"session_id": conv_id})
        async for event in orchestrator.astream(state):
            yield event
        await self.conversation_service.save_message(
            org_id=org_id, conversation_id=conv_id, message=user_message
        )
        yield StreamEvent.metadata({"session_id": conv_id, "saved": True})

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
            self.logger.warning("Failed to get instance %s", instance_id, exc_info=True)
            return None

    @staticmethod
    def convert_to_ai_message(
        accumulated_messages: list[dict[str, str]],
    ) -> UvAIMessage:
        results = []
        for message in accumulated_messages:
            if message["role"] == "assistant":
                results.append(message["content"])

        return UvAIMessage(content="".join(results))
