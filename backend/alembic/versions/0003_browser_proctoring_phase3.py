"""Browser proctoring Phase 3 schema additions

Revision ID: 0003_browser_proctoring_phase3
Revises: 0002_exam_engine_phase2
Create Date: 2026-09-21 12:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "0003_browser_proctoring_phase3"
down_revision: Union[str, None] = "0002_exam_engine_phase2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update exams table with Phase 3 proctoring settings & thresholds
    op.add_column(
        "exams",
        sa.Column("enable_browser_proctoring", sa.Boolean(), nullable=False, server_default=sa.true())
    )
    op.add_column(
        "exams",
        sa.Column("max_fullscreen_exits", sa.Integer(), nullable=False, server_default="2")
    )
    op.add_column(
        "exams",
        sa.Column("fullscreen_warning_timeout_seconds", sa.Integer(), nullable=False, server_default="10")
    )
    op.add_column(
        "exams",
        sa.Column("max_tab_away_seconds", sa.Integer(), nullable=False, server_default="60")
    )
    op.add_column(
        "exams",
        sa.Column("paste_char_threshold", sa.Integer(), nullable=False, server_default="50")
    )

    # 2. Update exam_sessions table with Phase 3 tracking columns
    op.add_column(
        "exam_sessions",
        sa.Column("media_permission_granted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "exam_sessions",
        sa.Column("fullscreen_exit_count", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "exam_sessions",
        sa.Column("total_tab_away_seconds", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "exam_sessions",
        sa.Column("terminated_reason", sa.String(255), nullable=True)
    )


def downgrade() -> None:
    # Remove from exam_sessions
    op.drop_column("exam_sessions", "terminated_reason")
    op.drop_column("exam_sessions", "total_tab_away_seconds")
    op.drop_column("exam_sessions", "fullscreen_exit_count")
    op.drop_column("exam_sessions", "media_permission_granted_at")

    # Remove from exams
    op.drop_column("exams", "paste_char_threshold")
    op.drop_column("exams", "max_tab_away_seconds")
    op.drop_column("exams", "fullscreen_warning_timeout_seconds")
    op.drop_column("exams", "max_fullscreen_exits")
    op.drop_column("exams", "enable_browser_proctoring")
