"""Performance indexes for concurrent proctoring queries

Revision ID: 0005_performance_indexes
Revises: 0004_video_audio_proctoring
Create Date: 2026-09-21 18:20:00.000000

"""
from typing import Sequence, Union
from alembic import op

revision: str = "0005_performance_indexes"
down_revision: Union[str, None] = "0004_video_audio_proctoring"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Composite index for chronological violation logs per session (admin audit query)
    op.create_index(
        "ix_violation_logs_session_timestamp",
        "violation_logs",
        ["session_id", "timestamp"],
        unique=False,
    )

    # 2. Composite index for recent candidate sessions per exam (admin monitoring grid)
    op.create_index(
        "ix_exam_sessions_exam_started",
        "exam_sessions",
        ["exam_id", "started_at"],
        unique=False,
    )

    # 3. Composite index for candidate session lookup (candidate exam entry)
    op.create_index(
        "ix_exam_sessions_candidate_exam",
        "exam_sessions",
        ["candidate_id", "exam_id"],
        unique=False,
    )

    # 4. Single/composite index for session submissions lookup (scoring & review)
    # Note: ix_submissions_session_question already exists, adding standalone session_id if missing
    try:
        op.create_index(
            "ix_submissions_session_id_perf",
            "submissions",
            ["session_id"],
            unique=False,
        )
    except Exception:
        pass


def downgrade() -> None:
    try:
        op.drop_index("ix_submissions_session_id_perf", table_name="submissions")
    except Exception:
        pass
    op.drop_index("ix_exam_sessions_candidate_exam", table_name="exam_sessions")
    op.drop_index("ix_exam_sessions_exam_started", table_name="exam_sessions")
    op.drop_index("ix_violation_logs_session_timestamp", table_name="violation_logs")
