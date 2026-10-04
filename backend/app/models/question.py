import enum
import uuid
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, TimestampMixin

if TYPE_CHECKING:
    from app.models.exam import Exam
    from app.models.submission import Submission

# Native JSONB in Postgres, standard JSON in fallback/SQLite
JSONType = JSON().with_variant(JSONB, "postgresql")


class QuestionType(str, enum.Enum):
    MCQ = "mcq"
    CODING = "coding"


class Question(Base, TimestampMixin):
    __tablename__ = "questions"

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
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    question_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    options: Mapped[Optional[Any]] = mapped_column(
        JSONType,
        nullable=True,
        doc="Array of option objects for MCQ questions: [{'id': 'A', 'text': '...'}]",
    )
    correct_answer: Mapped[Optional[Any]] = mapped_column(
        JSONType,
        nullable=True,
        doc="Correct answer identifier or array of IDs for MCQ",
    )
    is_multiselect: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="True if candidate can select multiple answers",
    )
    partial_credit: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="True if partial score is awarded for multi-select options",
    )
    starter_code: Mapped[Optional[Any]] = mapped_column(
        JSONType,
        nullable=True,
        doc="Starter code snippet per language: {'python': '...', 'javascript': '...'}",
    )
    allowed_languages: Mapped[Optional[Any]] = mapped_column(
        JSONType,
        nullable=True,
        doc="Allowed programming languages for coding: ['python', 'javascript', 'cpp']",
    )
    test_cases: Mapped[Optional[Any]] = mapped_column(
        JSONType,
        nullable=True,
        doc="Array of test case objects for coding: [{'input': '...', 'expected_output': '...', 'is_hidden': bool}]",
    )
    time_limit: Mapped[Optional[int]] = mapped_column(
        Integer,
        default=3,
        nullable=True,
        doc="Time limit in seconds for answering this question or coding execution timeout",
    )
    memory_limit: Mapped[Optional[int]] = mapped_column(
        Integer,
        default=128000,
        nullable=True,
        doc="Memory limit in KB for code execution",
    )
    points: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
    )
    order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Display order index within the exam",
    )

    # Relationships
    exam: Mapped["Exam"] = relationship(
        "Exam",
        back_populates="questions",
    )
    submissions: Mapped[List["Submission"]] = relationship(
        "Submission",
        back_populates="question",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Question id={self.id} exam_id={self.exam_id} type={self.type}>"
