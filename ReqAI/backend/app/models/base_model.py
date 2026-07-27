"""
Shared abstract base mixin for all ORM models.
Provides id, created_at, updated_at, is_active on every table.
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer
from sqlalchemy.orm import declared_attr

from app.database.db import Base


class TimestampMixin:
    """Adds created_at / updated_at timestamp columns."""

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class BaseModel(TimestampMixin, Base):
    """
    Abstract base model inherited by all application models.
    Provides: id, is_active, created_at, updated_at.
    """

    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    is_active = Column(Boolean, default=True, nullable=False)

    @declared_attr
    def __tablename__(cls) -> str:  # noqa: N805
        """Automatically derive table name from class name (lowercase)."""
        return cls.__name__.lower()
