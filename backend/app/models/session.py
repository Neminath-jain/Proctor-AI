import enum
import uuid
from datetime import datetime
from typing import Any, List, Optional, TYPE_CHECKING
from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, TimestampMixin
from app.models.question import JSONType

if TYPE_CHECKING:
    from app.models.exam import Exam
    from app.models.user import User
    from app.models.submission import Submission
    from app.models.violation import ViolationLog


class SessionStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    TERMINATED = "terminated"
    TIMED_OUT = "timed_out"


class ExamSession(Base, TimestampMixin):
    __tablename__ = "exam_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
    )
    exam_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("exams.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default=SessionStatus.IN_PROGRESS.value,
        index=True,
        nullable=False,
    )
    score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    session_metadata: Mapped[Optional[Any]] = mapped_column(
        JSONType,
        nullable=True,
        doc="Stores randomized question order, shuffled options, and timer state",
    )

    # Phase 3 Proctoring Tracking
    media_permission_granted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when candidate granted webcam and microphone permissions",
    )
    fullscreen_exit_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Total times candidate exited fullscreen during this session",
    )
    total_tab_away_seconds: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Cumulative seconds spent blurred/away from the exam window",
    )
    terminated_reason: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Specific rule breach if session was terminated early by proctoring engine",
    )

    # Phase 4 Video & Audio Proctoring Tracking
    reference_photo_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        doc="Filesystem or storage path of candidate reference photo captured at pre-exam check",
    )
    reference_embedding: Mapped[Optional[Any]] = mapped_column(
        JSONType,
        nullable=True,
        doc="128-dimensional facial embedding vector of candidate reference photo",
    )
    consecutive_no_face_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Count of consecutive frames where no face was detected",
    )
    audio_speech_seconds_in_window: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        doc="Cumulative speech duration in seconds within the rolling window",
    )
    last_audio_window_reset: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when rolling audio analysis window was last reset",
    )

    # Phase 5 Trust Score & Human Review Tracking
    trust_score: Mapped[float] = mapped_column(
        Float,
        default=100.0,
        nullable=False,
        index=True,
        doc="Server-computed trust score from 0.0 to 100.0 reflecting integrity signals",
    )
    review_status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        nullable=False,
        index=True,
        doc="Human-in-the-loop review verdict: pending, reviewed_benign, confirmed_cheating",
    )
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    review_notes: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True,
    )
    latest_snapshot_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        doc="Most recent snapshot evidence path for quick thumbnail previews",
    )

    # Relationships
    exam: Mapped["Exam"] = relationship(
        "Exam",
        back_populates="sessions",
    )
    candidate: Mapped["User"] = relationship(
        "User",
        foreign_keys=[candidate_id],
        back_populates="exam_sessions",
    )
    reviewer: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[reviewed_by],
    )
    submissions: Mapped[List["Submission"]] = relationship(
        "Submission",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    violation_logs: Mapped[List["ViolationLog"]] = relationship(
        "ViolationLog",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_exam_sessions_exam_candidate", "exam_id", "candidate_id"),
    )

    def __repr__(self) -> str:
        return f"<ExamSession id={self.id} exam_id={self.exam_id} candidate_id={self.candidate_id} status={self.status}>"
