"""Video and audio proctoring Phase 4 schema additions

Revision ID: 0004_video_audio_proctoring
Revises: 0003_browser_proctoring_phase3
Create Date: 2026-09-21 15:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0004_video_audio_proctoring"
down_revision: Union[str, None] = "0003_browser_proctoring_phase3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update exams table with video & audio proctoring configurations
    op.add_column(
        "exams",
        sa.Column("proctor_frame_interval_seconds", sa.Integer(), nullable=False, server_default="10"),
    )
    op.add_column(
        "exams",
        sa.Column("face_similarity_threshold", sa.Float(), nullable=False, server_default="0.60"),
    )
    op.add_column(
        "exams",
        sa.Column("consecutive_no_face_limit", sa.Integer(), nullable=False, server_default="3"),
    )
    op.add_column(
        "exams",
        sa.Column("sustained_audio_threshold_seconds", sa.Float(), nullable=False, server_default="5.0"),
    )
    op.add_column(
        "exams",
        sa.Column("audio_window_seconds", sa.Integer(), nullable=False, server_default="30"),
    )

    # 2. Update exam_sessions table with reference photo and live tracking state
    op.add_column(
        "exam_sessions",
        sa.Column("reference_photo_path", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "exam_sessions",
        sa.Column("reference_embedding", sa.JSON().with_variant(postgresql.JSONB, "postgresql"), nullable=True),
    )
    op.add_column(
        "exam_sessions",
        sa.Column("consecutive_no_face_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "exam_sessions",
        sa.Column("audio_speech_seconds_in_window", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "exam_sessions",
        sa.Column("last_audio_window_reset", sa.DateTime(timezone=True), nullable=True),
    )

    # 3. Update violation_logs table with direct evidence reference column
    op.add_column(
        "violation_logs",
        sa.Column("evidence_url", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("violation_logs", "evidence_url")

    op.drop_column("exam_sessions", "last_audio_window_reset")
    op.drop_column("exam_sessions", "audio_speech_seconds_in_window")
    op.drop_column("exam_sessions", "consecutive_no_face_count")
    op.drop_column("exam_sessions", "reference_embedding")
    op.drop_column("exam_sessions", "reference_photo_path")

    op.drop_column("exams", "audio_window_seconds")
    op.drop_column("exams", "sustained_audio_threshold_seconds")
    op.drop_column("exams", "consecutive_no_face_limit")
    op.drop_column("exams", "face_similarity_threshold")
    op.drop_column("exams", "proctor_frame_interval_seconds")
