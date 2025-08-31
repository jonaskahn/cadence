"""Cassandra repository implementations for the Cadence framework.

This module provides Cassandra-specific repository implementations.
Currently a placeholder for future Cassandra support.
"""

from .cassandra_repositories import CassandraConversationRepository, CassandraThreadRepository

__all__ = [
    "CassandraThreadRepository",
    "CassandraConversationRepository",
]
