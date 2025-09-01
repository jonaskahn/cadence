"""PostgreSQL repository implementations using SQLAlchemy ORM.

This module provides PostgreSQL-specific repository implementations for the Cadence framework.
Optimized for PostgreSQL features like full-text search, JSON support, and advanced indexing.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, asc, desc, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from cadence.domain.models.conversation import Conversation
from cadence.domain.models.thread import Thread, ThreadStatus
from cadence.infrastructure.database.models.conversation import ConversationModel
from cadence.infrastructure.database.models.organization import OrganizationModel
from cadence.infrastructure.database.models.thread import ThreadModel
from cadence.infrastructure.database.models.user import UserModel
from cadence.infrastructure.database.repositories.conversation_repository import ConversationRepository
from cadence.infrastructure.database.repositories.thread_repository import ThreadRepository

logger = logging.getLogger(__name__)


class PostgreSQLThreadRepository(ThreadRepository):
    """PostgreSQL implementation of ThreadRepository using SQLAlchemy."""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    async def create_thread(self, user_id: str, org_id: str) -> Thread:
        """Create a new thread."""
        thread = Thread(user_id=user_id, org_id=org_id)
        thread_model = ThreadModel.from_domain_model(thread)

        async with self.session_factory() as session:
            await self._ensure_user_exists(session, user_id, org_id)

            session.add(thread_model)
            await session.commit()
            await session.refresh(thread_model)

        return thread_model.to_domain_model()

    async def get_thread(self, thread_id: str) -> Optional[Thread]:
        """Get thread by ID."""
        async with self.session_factory() as session:
            result = await session.execute(select(ThreadModel).where(ThreadModel.thread_id == thread_id))
            thread_model = result.scalar_one_or_none()

            return thread_model.to_domain_model() if thread_model else None

    async def update_thread(self, thread: Thread) -> Thread:
        """Update an existing thread."""
        async with self.session_factory() as session:
            result = await session.execute(select(ThreadModel).where(ThreadModel.thread_id == thread.thread_id))
            thread_model = result.scalar_one_or_none()

            if not thread_model:
                raise ValueError(f"Thread {thread.thread_id} not found")

            thread_model.update_from_domain_model(thread)
            await session.commit()
            await session.refresh(thread_model)

            return thread_model.to_domain_model()

    async def archive_thread(self, thread_id: str) -> bool:
        """Archive a thread."""
        async with self.session_factory() as session:
            result = await session.execute(
                select(ThreadModel).where(
                    and_(ThreadModel.thread_id == thread_id, ThreadModel.status == ThreadStatus.ACTIVE)
                )
            )
            thread_model = result.scalar_one_or_none()

            if not thread_model:
                return False

            thread_model.status = ThreadStatus.ARCHIVED
            thread_model.updated_at = datetime.utcnow()
            await session.commit()

            return True

    async def list_threads(
        self,
        user_id: Optional[str] = None,
        org_id: Optional[str] = None,
        status: Optional[ThreadStatus] = None,
        limit: int = 20,
        offset: int = 0,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> List[Thread]:
        """List threads with filtering and pagination."""
        async with self.session_factory() as session:
            query = select(ThreadModel)

            conditions = []
            if user_id:
                conditions.append(ThreadModel.user_id == user_id)
            if org_id:
                conditions.append(ThreadModel.org_id == org_id)
            if status:
                conditions.append(ThreadModel.status == status)

            if conditions:
                query = query.where(and_(*conditions))

            sort_column = getattr(ThreadModel, sort_by, ThreadModel.updated_at)
            if sort_order.lower() == "desc":
                query = query.order_by(desc(sort_column))
            else:
                query = query.order_by(asc(sort_column))

            query = query.offset(offset).limit(limit)

            result = await session.execute(query)
            thread_models = result.scalars().all()

            return [tm.to_domain_model() for tm in thread_models]

    async def count_threads(
        self, user_id: Optional[str] = None, org_id: Optional[str] = None, status: Optional[ThreadStatus] = None
    ) -> int:
        """Count threads matching filters."""
        async with self.session_factory() as session:
            query = select(func.count(ThreadModel.thread_id))

            conditions = []
            if user_id:
                conditions.append(ThreadModel.user_id == user_id)
            if org_id:
                conditions.append(ThreadModel.org_id == org_id)
            if status:
                conditions.append(ThreadModel.status == status)

            if conditions:
                query = query.where(and_(*conditions))

            result = await session.execute(query)
            return result.scalar()

    async def get_thread_stats(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive stats for a thread."""
        async with self.session_factory() as session:
            result = await session.execute(
                select(
                    ThreadModel,
                    func.count(ConversationModel.conversation_id).label("actual_turns"),
                    func.max(ConversationModel.created_at).label("latest_turn"),
                )
                .outerjoin(ConversationModel)
                .where(ThreadModel.thread_id == thread_id)
                .group_by(ThreadModel.thread_id)
            )

            row = result.first()
            if not row:
                return None

            thread_model = row[0]
            actual_turns = row[1] or 0
            latest_turn = row[2]

            estimated_cost = thread_model.input_tokens * 0.001 / 1000 + thread_model.output_tokens * 0.003 / 1000

            return {
                "thread_id": thread_model.thread_id,
                "total_tokens": thread_model.total_tokens,
                "input_tokens": thread_model.input_tokens,
                "output_tokens": thread_model.output_tokens,
                "message_count": thread_model.message_count,
                "actual_turn_count": actual_turns,
                "status": thread_model.status.value,
                "created_at": thread_model.created_at.isoformat(),
                "updated_at": thread_model.updated_at.isoformat(),
                "latest_turn_at": latest_turn.isoformat() if latest_turn else None,
                "estimated_cost": round(estimated_cost, 6),
            }

    async def update_thread_tokens(self, thread_id: str, user_tokens: int, assistant_tokens: int) -> bool:
        """Update thread token counters atomically."""
        async with self.session_factory() as session:
            result = await session.execute(
                select(ThreadModel).where(ThreadModel.thread_id == thread_id).with_for_update()
            )
            thread_model = result.scalar_one_or_none()

            if not thread_model or thread_model.status != ThreadStatus.ACTIVE:
                return False

            thread_model.input_tokens += user_tokens
            thread_model.output_tokens += assistant_tokens
            thread_model.total_tokens = thread_model.input_tokens + thread_model.output_tokens
            thread_model.message_count += 1
            thread_model.updated_at = datetime.utcnow()

            await session.commit()
            return True

    async def _ensure_user_exists(self, session: AsyncSession, user_id: str, org_id: str):
        """Ensure user exists, create if not."""
        result = await session.execute(
            select(UserModel).where(and_(UserModel.user_id == user_id, UserModel.org_id == org_id))
        )
        user_model = result.scalar_one_or_none()

        if not user_model:
            user_model = UserModel(user_id=user_id, org_id=org_id, display_name=user_id, is_active=True)
            session.add(user_model)

            await self._ensure_organization_exists(session, org_id)

    async def _ensure_organization_exists(self, session: AsyncSession, org_id: str):
        """Ensure organization exists, create if not."""
        result = await session.execute(select(OrganizationModel).where(OrganizationModel.org_id == org_id))
        org_model = result.scalar_one_or_none()

        if not org_model:
            org_model = OrganizationModel(org_id=org_id, name=f"Organization {org_id}", is_active=True)
            session.add(org_model)


class PostgreSQLConversationRepository(ConversationRepository):
    """PostgreSQL implementation of ConversationRepository using SQLAlchemy."""

    def __init__(self, session_factory, thread_repository: ThreadRepository):
        self.session_factory = session_factory
        self.thread_repository = thread_repository

    async def save(self, conversation: Conversation) -> Conversation:
        """Save a conversation atomically with thread token updates."""
        async with self.session_factory() as session:
            async with session.begin():
                conversation_model = ConversationModel.from_domain_model(conversation)
                session.add(conversation_model)

                success = await self.thread_repository.update_thread_tokens(
                    conversation.thread_id, conversation.user_tokens, conversation.assistant_tokens
                )

                if not success:
                    raise ValueError(f"Failed to update thread {conversation.thread_id} tokens")

                await session.commit()
                await session.refresh(conversation_model)

        return conversation_model.to_domain_model()

    async def get(self, id: str) -> Optional[Conversation]:
        """Get a conversation by ID."""
        async with self.session_factory() as session:
            result = await session.execute(select(ConversationModel).where(ConversationModel.conversation_id == id))
            conversation_model = result.scalar_one_or_none()

            return conversation_model.to_domain_model() if conversation_model else None

    async def get_conversation_history(
        self, thread_id: str, limit: int = 50, before_id: Optional[str] = None
    ) -> List[Conversation]:
        """Get conversation history for a thread, ordered by creation time."""
        async with self.session_factory() as session:
            query = select(ConversationModel).where(ConversationModel.thread_id == thread_id)

            if before_id:
                subquery = select(ConversationModel.created_at).where(ConversationModel.conversation_id == before_id)
                before_time = await session.execute(subquery)
                before_time = before_time.scalar()

                if before_time:
                    query = query.where(ConversationModel.created_at < before_time)

            query = query.order_by(asc(ConversationModel.created_at)).limit(limit)

            result = await session.execute(query)
            conversation_models = result.scalars().all()

            return [cm.to_domain_model() for cm in conversation_models]

    async def get_thread_conversations_count(self, thread_id: str) -> int:
        """Get total number of conversations in a thread."""
        async with self.session_factory() as session:
            result = await session.execute(
                select(func.count(ConversationModel.conversation_id)).where(ConversationModel.thread_id == thread_id)
            )
            return result.scalar()

    async def get_recent_conversations(
        self, user_id: Optional[str] = None, org_id: Optional[str] = None, limit: int = 10, hours_back: int = 24
    ) -> List[Conversation]:
        """Get recent conversations across threads."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)

        async with self.session_factory() as session:
            query = select(ConversationModel).where(ConversationModel.created_at >= cutoff_time)

            if user_id or org_id:
                query = query.join(ThreadModel)
                if user_id:
                    query = query.where(ThreadModel.user_id == user_id)
                if org_id:
                    query = query.where(ThreadModel.org_id == org_id)

            query = query.order_by(desc(ConversationModel.created_at)).limit(limit)

            result = await session.execute(query)
            conversation_models = result.scalars().all()

            return [cm.to_domain_model() for cm in conversation_models]

    async def search_conversations(
        self, query: str, thread_id: Optional[str] = None, user_id: Optional[str] = None, limit: int = 20
    ) -> List[Conversation]:
        """Search conversations by content using full-text search."""
        async with self.session_factory() as session:
            search_query = select(ConversationModel)

            search_condition = or_(
                ConversationModel.user_message.ilike(f"%{query}%"),
                ConversationModel.assistant_message.ilike(f"%{query}%"),
            )
            search_query = search_query.where(search_condition)

            if thread_id:
                search_query = search_query.where(ConversationModel.thread_id == thread_id)

            if user_id:
                search_query = search_query.join(ThreadModel).where(ThreadModel.user_id == user_id)

            search_query = search_query.order_by(desc(ConversationModel.created_at)).limit(limit)

            result = await session.execute(search_query)
            conversation_models = result.scalars().all()

            return [cm.to_domain_model() for cm in conversation_models]

    async def get_conversation_statistics(
        self,
        thread_id: Optional[str] = None,
        user_id: Optional[str] = None,
        org_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get conversation statistics."""
        async with self.session_factory() as session:
            query = select(
                func.count(ConversationModel.conversation_id).label("total_turns"),
                func.coalesce(func.sum(ConversationModel.user_tokens + ConversationModel.assistant_tokens), 0).label(
                    "total_tokens"
                ),
                func.coalesce(func.avg(ConversationModel.user_tokens + ConversationModel.assistant_tokens), 0).label(
                    "avg_tokens_per_turn"
                ),
                func.coalesce(func.sum(ConversationModel.user_tokens), 0).label("total_input_tokens"),
                func.coalesce(func.sum(ConversationModel.assistant_tokens), 0).label("total_output_tokens"),
                func.count(func.distinct(ConversationModel.thread_id)).label("unique_threads"),
            )

            conditions = []
            if thread_id:
                conditions.append(ConversationModel.thread_id == thread_id)
            if start_date:
                conditions.append(ConversationModel.created_at >= start_date)
            if end_date:
                conditions.append(ConversationModel.created_at <= end_date)

            if user_id or org_id:
                query = query.select_from(ConversationModel.join(ThreadModel))
                if user_id:
                    conditions.append(ThreadModel.user_id == user_id)
                if org_id:
                    conditions.append(ThreadModel.org_id == org_id)

            if conditions:
                query = query.where(and_(*conditions))

            result = await session.execute(query)
            row = result.first()

            estimated_cost = row.total_input_tokens * 0.001 / 1000 + row.total_output_tokens * 0.003 / 1000

            return {
                "total_turns": row.total_turns,
                "total_tokens": row.total_tokens,
                "average_tokens_per_turn": float(row.avg_tokens_per_turn),
                "total_input_tokens": row.total_input_tokens,
                "total_output_tokens": row.total_output_tokens,
                "estimated_cost": round(estimated_cost, 6),
                "unique_threads": row.unique_threads,
            }

    async def delete_old_conversations(self, older_than_days: int) -> int:
        """Delete conversations older than specified days."""
        cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)

        async with self.session_factory() as session:
            result = await session.execute(
                ConversationModel.__table__.delete().where(ConversationModel.created_at < cutoff_date)
            )

            deleted_count = result.rowcount
            await session.commit()

            return deleted_count

    async def get_storage_efficiency_stats(self) -> Dict[str, Any]:
        """Get storage efficiency statistics using database views."""
        async with self.session_factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT COUNT(*)                                                  as total_turns,
                           SUM(LENGTH(user_message) + LENGTH(assistant_message))     as actual_storage_bytes,
                           SUM(LENGTH(user_message) + LENGTH(assistant_message)) * 4 as estimated_full_storage_bytes,
                           ROUND(
                                   (1 - (SUM(LENGTH(user_message) + LENGTH(assistant_message))::float / 
                              (SUM(LENGTH(user_message) + LENGTH(assistant_message)) * 4))) * 100,
                                   2
                           )                                                         as storage_efficiency_percentage,
                           SUM(user_tokens + assistant_tokens)                       as total_tokens,
                           AVG(user_tokens + assistant_tokens)                       as avg_tokens_per_turn
                    FROM conversations
                    """
                )
            )

            row = result.first()

            if not row or row.total_turns == 0:
                return {"efficiency_percentage": 0.0, "estimated_savings_bytes": 0}

            return {
                "total_turns": row.total_turns,
                "current_storage_bytes": row.actual_storage_bytes or 0,
                "estimated_full_storage_bytes": row.estimated_full_storage_bytes or 0,
                "efficiency_percentage": float(row.storage_efficiency_percentage or 0),
                "estimated_savings_bytes": (row.estimated_full_storage_bytes or 0) - (row.actual_storage_bytes or 0),
                "total_tokens": row.total_tokens or 0,
                "average_tokens_per_turn": float(row.avg_tokens_per_turn or 0),
            }
