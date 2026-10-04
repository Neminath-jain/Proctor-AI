import enum
import uuid
from typing import List, TYPE_CHECKING
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, TimestampMixin

if TYPE_CHECKING:
    from app.models.exam import Exam
    from app.models.session import ExamSession


class UserRole(str, enum.Enum):
    CANDIDATE = "candidate"
    ADMIN = "admin"  # Invigilator / Administrator
    GRADER = "grader"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(50),
        default=UserRole.CANDIDATE.value,
        index=True,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationships
    created_exams: Mapped[List["Exam"]] = relationship(
        "Exam",
        back_populates="creator",
        cascade="all, delete-orphan",
    )
    exam_sessions: Mapped[List["ExamSession"]] = relationship(
        "ExamSession",
        foreign_keys="[ExamSession.candidate_id]",
        back_populates="candidate",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"
