"""Conversation lifecycle management service.

Orchestrates complete conversation workflows including thread management,
multi-agent coordination, and conversation storage optimization.
"""

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from cadence_sdk.base.loggable import Loggable

from ...domain.dtos.chat_dtos import ChatRequest, ChatResponse, TokenUsage
from ...domain.models.conversation import Conversation
from ...domain.models.thread import Thread, ThreadStatus
from ...infrastructure.database.repositories import ConversationRepository, ThreadRepository
from ..orchestrator.coordinator import MultiAgentOrchestrator


class ConversationService(Loggable):
    """Manages conversation workflow and multi-agent coordination.

    Handles thread creation, message processing through orchestrator, and optimized
    conversation storage with token tracking.
    """

    def __init__(
        self,
        thread_repository: ThreadRepository,
        conversation_repository: ConversationRepository,
        orchestrator: MultiAgentOrchestrator,
    ):
        super().__init__()
        self.thread_repository = thread_repository
        self.conversation_repository = conversation_repository
        self.orchestrator = orchestrator

    async def process_message(self, request: ChatRequest) -> ChatResponse:
        """Process chat message within existing or new conversation thread."""
        self.logger.info(f"Processing message for thread {request.thread_id}")

        thread = await self._get_or_create_thread(request)

        if not thread.can_accept_message():
            raise ValueError(f"Thread {thread.thread_id} is {thread.status.value} and cannot accept messages")

        return await self._process_message_internal(
            thread, request.message, request.user_id, request.org_id, request.metadata, request.tone
        )

    async def _get_or_create_thread(self, request: ChatRequest) -> Thread:
        """Retrieve existing thread or create new one if needed."""
        if request.thread_id:
            thread = await self.thread_repository.get_thread(request.thread_id)
            if not thread:
                thread = await self.thread_repository.create_thread(request.user_id, request.org_id)
                self.logger.debug(f"Thread {request.thread_id} not found, created new thread {thread.thread_id}")
        else:
            thread = await self.thread_repository.create_thread(request.user_id, request.org_id)

        return thread

    async def _process_message_internal(
        self,
        thread: Thread,
        message: str,
        user_id: str,
        org_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        tone: Optional[str] = None,
    ) -> ChatResponse:
        """Process message through orchestrator and store optimized conversation data."""
        conversation_history = await self.conversation_repository.get_conversation_history(thread.thread_id, limit=50)
        langgraph_context = self._prepare_langgraph_context(conversation_history, message)

        from cadence_sdk.types.state import AgentState

        agent_state: AgentState = {
            "messages": langgraph_context,
            "current_agent": "coordinator",
            "agent_hops": 0,
            "thread_id": thread.thread_id,
            "plugin_context": {},
            "metadata": {
                "thread_id": thread.thread_id,
                "user_id": user_id,
                "organization_id": org_id,
                "checkpoint_ns": f"org_{org_id}/user_{user_id}",
                "tone": (tone or "natural").strip() or "natural",
                **(metadata or {}),
            },
        }

        start_time = time.time()
        self.logger.debug(f"Processing message with orchestrator for thread {thread.thread_id}")
        orchestrator_result = await self.orchestrator.ask(agent_state)
        processing_time = time.time() - start_time

        response_text = self._extract_response_text(orchestrator_result)
        processing_metadata = self._extract_processing_metadata(orchestrator_result)
        processing_metadata["processing_time"] = processing_time

        user_token_count = self._estimate_tokens(message)
        assistant_token_count = self._estimate_tokens(response_text)

        conversation = Conversation(
            thread_id=thread.thread_id,
            user_message=message,
            assistant_message=response_text,
            user_tokens=user_token_count,
            assistant_tokens=assistant_token_count,
            metadata={
                "agent_hops": processing_metadata.get("agent_hops", 0),
                "processing_time": processing_metadata.get("processing_time"),
                "tools_used": processing_metadata.get("tools_used", []),
                "routing_history": processing_metadata.get("routing_history", []),
                "model_used": processing_metadata.get("model_used"),
                **(metadata or {}),
            },
        )

        await self.conversation_repository.save(conversation)

        self.logger.info(f"Completed message processing for thread {thread.thread_id}, conversation {conversation.id}")

        return ChatResponse(
            response=response_text,
            thread_id=thread.thread_id,
            conversation_id=conversation.id,
            token_usage=TokenUsage(
                input_tokens=user_token_count,
                output_tokens=assistant_token_count,
                total_tokens=user_token_count + assistant_token_count,
            ),
            metadata={
                "agent_hops": processing_metadata.get("agent_hops", 0),
                "multi_agent": len(set(processing_metadata.get("routing_history", []))) > 1,
                "tools_used": processing_metadata.get("tools_used", []),
                "processing_time": processing_metadata.get("processing_time"),
                "thread_message_count": int(thread.message_count) + 1,
                "storage_optimized": True,
            },
        )

    def _prepare_langgraph_context(self, conversation_history: List[Conversation], current_message: str) -> List:
        """Prepare LangGraph message context from conversation history.

        Args:
            conversation_history: List of previous conversation turns
            current_message: New user message to append

        Returns:
            List of LangChain messages suitable for LangGraph execution
        """
        from langchain_core.messages import HumanMessage

        messages = []
        for turn in conversation_history:
            messages.extend(turn.to_langgraph_messages())
        messages.append(HumanMessage(content=current_message))

        self.logger.debug(
            f"Prepared LangGraph context with {len(messages)} messages from {len(conversation_history)} stored turns"
        )
        return messages

    @staticmethod
    def _extract_response_text(orchestrator_result: Dict[str, Any]) -> str:
        """Extract the final response text from orchestrator result.

        Args:
            orchestrator_result: Result from the orchestrator containing messages

        Returns:
            The final AI response text or default message if none found
        """
        from langchain_core.messages import AIMessage

        messages = orchestrator_result.get("messages", [])
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and getattr(msg, "content", None):
                return msg.content

        return "No response generated"

    @staticmethod
    def _extract_processing_metadata(orchestrator_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract processing metadata from orchestrator result.

        Args:
            orchestrator_result: Result from the orchestrator

        Returns:
            Dictionary containing tools used, routing history, and processing info
        """
        tools_used = []
        messages = orchestrator_result.get("messages", [])

        for message in messages:
            if hasattr(message, "tool_calls") and message.tool_calls:
                for tool_call in message.tool_calls:
                    if isinstance(tool_call, dict) and "name" in tool_call:
                        tools_used.append(tool_call["name"])
                    elif hasattr(tool_call, "name"):
                        tools_used.append(tool_call.name)

        agent_tools = [tool for tool in tools_used if not tool.startswith("goto_")]
        routing_tools = [tool for tool in tools_used if tool.startswith("goto_") and tool != "goto_finalize"]

        agent_hops = len(routing_tools)

        return {
            "tools_used": tools_used,
            "agent_hops": agent_hops,
            "routing_history": orchestrator_result.get("plugin_context", {}).get("routing_history", []),
            "model_used": "default",
        }

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Estimate token count using character-length heuristic.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count (minimum 1)
        """
        return max(1, len(text) // 4)

    async def get_conversation_history(self, thread_id: str, limit: int = 20) -> List[Conversation]:
        """Get conversation history for a thread.

        Args:
            thread_id: Thread identifier
            limit: Maximum number of conversations to return

        Returns:
            List of conversation objects
        """
        return await self.conversation_repository.get_conversation_history(thread_id, limit)

    async def get_thread_info(self, thread_id: str) -> Optional[Thread]:
        """Get thread information.

        Args:
            thread_id: Thread identifier

        Returns:
            Thread object if found, None otherwise
        """
        return await self.thread_repository.get_thread(thread_id)

    async def archive_thread(self, thread_id: str) -> bool:
        """Archive a conversation thread.

        Args:
            thread_id: Thread identifier to archive

        Returns:
            True if successfully archived
        """
        self.logger.info(f"Archiving thread {thread_id}")
        return await self.thread_repository.archive_thread(thread_id)

    async def get_user_threads(
        self, user_id: str, org_id: str, status: Optional[ThreadStatus] = None, limit: int = 20, offset: int = 0
    ) -> List[Thread]:
        """Get threads for a specific user.

        Args:
            user_id: User identifier
            org_id: Organization identifier
            status: Optional thread status filter
            limit: Maximum number of threads to return
            offset: Number of threads to skip

        Returns:
            List of thread objects
        """
        return await self.thread_repository.list_threads(
            user_id=user_id, org_id=org_id, status=status, limit=limit, offset=offset
        )

    async def search_conversations(
        self, query: str, user_id: Optional[str] = None, thread_id: Optional[str] = None, limit: int = 20
    ) -> List[Conversation]:
        """Search conversation content.

        Args:
            query: Search query string
            user_id: Optional user filter
            thread_id: Optional thread filter
            limit: Maximum number of results

        Returns:
            List of matching conversation objects
        """
        return await self.conversation_repository.search_conversations(
            query=query, thread_id=thread_id, user_id=user_id, limit=limit
        )

    async def get_conversation_statistics(
        self,
        user_id: Optional[str] = None,
        org_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get conversation statistics.

        Args:
            user_id: Optional user filter
            org_id: Optional organization filter
            start_date: Start date for statistics
            end_date: End date for statistics

        Returns:
            Dictionary containing conversation statistics
        """
        stats = await self.conversation_repository.get_conversation_statistics(
            user_id=user_id, org_id=org_id, start_date=start_date, end_date=end_date
        )

        if hasattr(self.conversation_repository, "get_storage_efficiency_estimate"):
            storage_efficiency = self.conversation_repository.get_storage_efficiency_estimate()
            stats.update(storage_efficiency)

        return stats

    async def cleanup_old_conversations(self, older_than_days: int) -> Dict[str, int]:
        """Clean up old conversation data.

        Args:
            older_than_days: Age threshold in days for cleanup

        Returns:
            Dictionary with cleanup statistics
        """
        self.logger.info(f"Cleaning up conversations older than {older_than_days} days")

        deleted_turns = await self.conversation_repository.delete_old_conversations(older_than_days)

        self.logger.info(f"Cleanup completed: {deleted_turns} turns deleted")
        return {"deleted_turns": deleted_turns, "archived_threads": 0}
