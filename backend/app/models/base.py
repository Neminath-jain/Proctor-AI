import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator, CHAR


class GUID(TypeDecorator):
    """Platform-independent GUID/UUID type.
    Stores UUIDs as CHAR(36) in database, seamlessly exposes uuid.UUID objects in Python.
    """
    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(uuid.UUID(str(value)))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, uuid.UUID):
            return uuid.UUID(str(value).strip())
        return value


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy ORM models."""
    pass


class TimestampMixin:
    """Mixin that adds created_at and updated_at timestamp columns."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
