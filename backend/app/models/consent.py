import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, GUID
from app.models.question import JSONType


class ConsentRecord(Base):
    __tablename__ = "dpdp_consent_records"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    exam_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("exams.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID,
        ForeignKey("exam_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="granted, withdrawn, declined",
    )
    notice_version: Mapped[str] = mapped_column(
        String(50),
        default="2023.1-dpdp",
        nullable=False,
    )
    clauses_consented: Mapped[Optional[Any]] = mapped_column(
        JSONType,
        nullable=True,
        doc="Array of consented clauses: video_snapshots, audio_detection, biometric_face, browser_activity",
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    retention_days: Mapped[int] = mapped_column(
        Integer,
        default=90,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class DataErasureRequest(Base):
    __tablename__ = "data_erasure_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        nullable=False,
        doc="pending, processed, rejected",
    )
    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    details: Mapped[Optional[Any]] = mapped_column(
        JSONType,
        nullable=True,
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
