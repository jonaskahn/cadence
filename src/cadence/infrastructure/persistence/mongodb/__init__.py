"""MongoDB database layer for conversation storage.

Uses database-per-organization strategy for tenant isolation.
Each organization gets its own MongoDB database: cadence_{org_id}
"""

from cadence.repository.message_repository import MessageRepository

from .client import MongoDBClient

__all__ = [
    "MongoDBClient",
    "MessageRepository",
]
