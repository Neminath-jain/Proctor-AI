import enum
import uuid
from datetime import datetime
from typing import Any, Optional, TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID
from app.models.question import JSONType

if TYPE_CHECKING:
    from app.models.session import ExamSession


class ViolationSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ViolationLog(Base):
    __tablename__ = "violation_logs"

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
    violation_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="e.g. multiple_faces, no_face, looking_away, tab_switch, voice_detected",
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
        nullable=False,
    )
    metadata_info: Mapped[Optional[Any]] = mapped_column(
        "metadata",  # column name in DB table
        JSONType,
        nullable=True,
        doc="Arbitrary payload: confidence score, snapshot URL, audio level, etc.",
    )
    severity: Mapped[str] = mapped_column(
        String(50),
        default=ViolationSeverity.MEDIUM.value,
        index=True,
        nullable=False,
    )
    evidence_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        doc="Secure authenticated reference URL to stored snapshot or audio clip",
    )
    review_status: Mapped[str] = mapped_column(
        String(50),
        default="unreviewed",
        nullable=False,
        index=True,
        doc="Human review verdict: unreviewed, reviewed_benign, confirmed_cheating",
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
        String(500),
        nullable=True,
    )

    # Relationships
    session: Mapped["ExamSession"] = relationship(
        "ExamSession",
        back_populates="violation_logs",
    )

    def __repr__(self) -> str:
        return f"<ViolationLog id={self.id} session_id={self.session_id} type={self.violation_type} severity={self.severity}>"
