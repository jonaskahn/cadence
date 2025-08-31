"""Cadence Framework Database Base Configuration - SQLAlchemy Foundation.

This module provides the foundational SQLAlchemy configuration and common mixins
for the Cadence database models. It establishes consistent patterns for timestamp
management, table naming, and common database behaviors across all models.

Components:
    Base: SQLAlchemy declarative base with Cadence-specific configurations
    TimestampMixin: Automatic timestamp management for entity lifecycle tracking

Design Patterns:
    - Mixin Pattern: Reusable functionality across multiple models
    - Declarative Configuration: Consistent table and column conventions
    - Automatic Timestamp Management: Audit trail for all entity changes

Features:
    - Consistent timestamp tracking across all database entities
    - Optimized column configurations for performance
    - Database-specific optimizations (PostgreSQL functions, indexing hints)
    - Standardized comment documentation for database introspection

Example Usage:
    Using TimestampMixin in model definitions:

    ```python
    from cadence.infrastructure.database.models.base import Base, TimestampMixin
    from sqlalchemy import Column, String, Integer

    class MyModel(Base, TimestampMixin):
        __tablename__ = "my_models"

        id = Column(Integer, primary_key=True)
        name = Column(String(255), nullable=False)

                instance = MyModel(name="example")

        instance.name = "updated example"
    ```
"""

from sqlalchemy import Column, DateTime, func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class TimestampMixin:
    """Mixin providing automatic timestamp management for entity lifecycle tracking.

    This mixin adds created_at and updated_at columns to any model that includes it,
    providing automatic timestamp management for audit trails and change tracking.
    The timestamps use database-level functions for consistency and performance.

    Features:
        - created_at: Automatically set on record creation
        - updated_at: Automatically updated on any record modification
        - Database-level timestamp functions for consistency across connections
        - Proper indexing hints for query performance optimization

    Example:
        ```python
        class UserModel(Base, TimestampMixin):
            __tablename__ = "users"

            user_id = Column(String(255), primary_key=True)
            name = Column(String(255), nullable=False)
            user = UserModel(user_id="user-123", name="Alice")

        user.name = "Alice Smith"
        ```
    """

    created_at = Column(
        DateTime,
        default=func.now(),
        nullable=False,
        comment="Record creation timestamp - automatically set on insert",
        index=True,
    )

    updated_at = Column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Record last modification timestamp - automatically updated on any change",
        index=True,
    )
