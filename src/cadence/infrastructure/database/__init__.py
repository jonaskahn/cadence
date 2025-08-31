"""Database infrastructure for Cadence framework.

Provides multi-backend data persistence with repository pattern implementations,
supporting PostgreSQL, Redis, and in-memory storage with optimized conversation handling.
"""

from .connection import DatabaseConnectionManager, initialize_databases
from .factory import DatabaseFactory
from .models import Base, ConversationModel, OrganizationModel, ThreadModel, UserModel
from .repositories import (
    ConversationRepository,
    InMemoryConversationRepository,
    InMemoryThreadRepository,
    PostgreSQLConversationRepository,
    PostgreSQLThreadRepository,
    ThreadRepository,
)

__all__ = [
    "DatabaseConnectionManager",
    "initialize_databases",
    "DatabaseFactory",
    "Base",
    "ThreadModel",
    "ConversationModel",
    "UserModel",
    "OrganizationModel",
    "ThreadRepository",
    "ConversationRepository",
    "InMemoryThreadRepository",
    "InMemoryConversationRepository",
    "PostgreSQLThreadRepository",
    "PostgreSQLConversationRepository",
]
