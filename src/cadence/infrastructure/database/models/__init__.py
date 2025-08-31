"""Cadence Framework Database Models - SQLAlchemy ORM with Optimized Storage.

This module provides SQLAlchemy ORM models that implement the optimized storage
strategy for the Cadence multi-agent AI framework. The models are designed to achieve
significant storage reduction while maintaining full conversation context capability.

Storage Optimization Strategy:
    The database models implement a revolutionary approach to conversation storage:
    - Store only user input + final AI response (not intermediate LangGraph steps)
    - Maintain conversation threading and context reconstruction capabilities
    - Comprehensive token tracking for precise cost optimization
    - Efficient indexing strategies for fast query performance

Model Architecture:
    Base Infrastructure:
        - Base: SQLAlchemy declarative base with common configurations
        - TimestampMixin: Automatic timestamp management for all entities

    Business Entities:
        - UserModel: User identity and organization affiliation
        - OrganizationModel: Multi-tenant organization management with resource limits
        - ThreadModel: Conversation containers with cost tracking and lifecycle
        - ConversationModel: Optimized user-assistant exchange storage

Key Features:
    - Automatic timestamp management for all entities
    - Comprehensive indexing for query performance optimization
    - Foreign key relationships with proper cascade behaviors
    - Token usage tracking at both thread and turn levels
    - Multi-tenant organization support with resource limits
    - Flexible metadata storage for extensibility

Database Schema Highlights:
    Optimized Conversation Storage:
        - Each ConversationTurn stores exactly one user-assistant exchange
        - No intermediate LangGraph steps stored (massive space savings)
        - Context reconstruction capability maintained through proper threading
        - Token counts tracked precisely for cost attribution

    Cost Tracking:
        - Thread-level aggregation of token usage and costs
        - Organization-level resource limit enforcement
        - Turn-level granular tracking for detailed analytics
        - Support for multiple token pricing models

Example Usage:
    Creating and using database models:

    ```python
    from cadence.infrastructure.database.models import (
        Base, UserModel, OrganizationModel, ThreadModel, ConversationModel
    )
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # Create database tables
    engine = create_engine("postgresql://user:pass@localhost/cadence")
    Base.metadata.create_all(engine)

    # Create session
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create organization and user
    org = OrganizationModel(
        org_id="acme-corp",
        name="ACME Corporation",
        monthly_token_limit=1000000
    )
    session.add(org)

    user = UserModel(
        user_id="alice",
        org_id="acme-corp",
        display_name="Alice Johnson"
    )
    session.add(user)

    # Create conversation thread
    thread = ThreadModel(
        thread_id="thread-123",
        user_id="alice",
        org_id="acme-corp"
    )
    session.add(thread)

    # Add conversation turn
    turn = ConversationModel(
        thread_id="thread-123",
        user_message="What is 2+2?",
        assistant_message="2+2 equals 4.",
        user_tokens=8,
        assistant_tokens=12
    )
    session.add(turn)

    session.commit()
    ```

    Query optimizations:

    ```python
    # Efficient conversation retrieval
    conversation_history = session.query(ConversationModel).filter(
        ConversationModel.thread_id == "thread-123"
    ).order_by(ConversationModel.created_at).all()

    # Cost tracking queries
    thread_cost = session.query(ThreadModel).filter(
        ThreadModel.thread_id == "thread-123"
    ).first().total_tokens
    ```

Performance Considerations:
    - Indexes on frequently queried fields (thread_id, user_id, org_id, created_at)
    - Partitioning strategies for high-volume deployments
    - Optimized foreign key relationships with proper cascade behaviors
    - Efficient JSON storage for flexible metadata

The database models provide the foundation for Cadence's optimized storage strategy,
enabling massive cost savings while maintaining full functionality.
"""

from .base import Base, TimestampMixin
from .conversation import ConversationModel
from .organization import OrganizationModel
from .thread import ThreadModel
from .user import UserModel

__all__ = [
    "Base",
    "TimestampMixin",
    "ThreadModel",
    "ConversationModel",
    "UserModel",
    "OrganizationModel",
]
