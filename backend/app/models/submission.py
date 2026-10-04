import uuid
from datetime import datetime
from typing import Any, Optional, TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID
from app.models.question import JSONType

if TYPE_CHECKING:
    from app.models.session import ExamSession
    from app.models.question import Question


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("exam_sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("questions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    answer: Mapped[Any] = mapped_column(
        JSONType,
        nullable=False,
        doc="Submitted candidate answer: selected choice ID or code string with language",
    )
    is_correct: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
    )
    score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    details: Mapped[Optional[Any]] = mapped_column(
        JSONType,
        nullable=True,
        doc="Execution results per test case, stdout/stderr, compile output, runtime",
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    session: Mapped["ExamSession"] = relationship(
        "ExamSession",
        back_populates="submissions",
    )
    question: Mapped["Question"] = relationship(
        "Question",
        back_populates="submissions",
    )

    __table_args__ = (
        Index("ix_submissions_session_question", "session_id", "question_id"),
    )

    def __repr__(self) -> str:
        return f"<Submission id={self.id} session_id={self.session_id} question_id={self.question_id}>"
