import enum
import uuid
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.question import Question
    from app.models.session import ExamSession


class ExamStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class Exam(Base, TimestampMixin):
    __tablename__ = "exams"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    duration_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default=ExamStatus.DRAFT.value,
        index=True,
        nullable=False,
    )

    # Browser-level proctoring configurations (Phase 3)
    enable_browser_proctoring: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    max_fullscreen_exits: Mapped[int] = mapped_column(
        Integer,
        default=2,
        nullable=False,
    )
    fullscreen_warning_timeout_seconds: Mapped[int] = mapped_column(
        Integer,
        default=10,
        nullable=False,
    )
    max_tab_away_seconds: Mapped[int] = mapped_column(
        Integer,
        default=60,
        nullable=False,
    )
    paste_char_threshold: Mapped[int] = mapped_column(
        Integer,
        default=50,
        nullable=False,
    )

    # Video & Audio ML proctoring configurations (Phase 4)
    proctor_frame_interval_seconds: Mapped[int] = mapped_column(
        Integer,
        default=10,
        nullable=False,
    )
    face_similarity_threshold: Mapped[float] = mapped_column(
        Float,
        default=0.60,
        nullable=False,
    )
    consecutive_no_face_limit: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False,
    )
    sustained_audio_threshold_seconds: Mapped[float] = mapped_column(
        Float,
        default=5.0,
        nullable=False,
    )
    audio_window_seconds: Mapped[int] = mapped_column(
        Integer,
        default=30,
        nullable=False,
    )

    # Relationships
    creator: Mapped["User"] = relationship(
        "User",
        back_populates="created_exams",
    )
    questions: Mapped[List["Question"]] = relationship(
        "Question",
        back_populates="exam",
        cascade="all, delete-orphan",
    )
    sessions: Mapped[List["ExamSession"]] = relationship(
        "ExamSession",
        back_populates="exam",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Exam id={self.id} title={self.title} status={self.status}>"
