"""Initial database schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-09-21 11:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users table
    op.create_table(
        "users",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False, server_default="candidate"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])

    # 2. exams table
    op.create_table(
        "exams",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.CHAR(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_exams_created_by", "exams", ["created_by"])
    op.create_index("ix_exams_status", "exams", ["status"])

    # 3. questions table
    op.create_table(
        "questions",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("exam_id", sa.CHAR(36), sa.ForeignKey("exams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON().with_variant(postgresql.JSONB, "postgresql"), nullable=True),
        sa.Column("correct_answer", sa.Text(), nullable=True),
        sa.Column("test_cases", sa.JSON().with_variant(postgresql.JSONB, "postgresql"), nullable=True),
        sa.Column("time_limit", sa.Integer(), nullable=True),
        sa.Column("points", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_questions_exam_id", "questions", ["exam_id"])

    # 4. exam_sessions table
    op.create_table(
        "exam_sessions",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("exam_id", sa.CHAR(36), sa.ForeignKey("exams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidate_id", sa.CHAR(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="in_progress"),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_exam_sessions_exam_id", "exam_sessions", ["exam_id"])
    op.create_index("ix_exam_sessions_candidate_id", "exam_sessions", ["candidate_id"])
    op.create_index("ix_exam_sessions_status", "exam_sessions", ["status"])
    op.create_index("ix_exam_sessions_exam_candidate", "exam_sessions", ["exam_id", "candidate_id"])

    # 5. submissions table
    op.create_table(
        "submissions",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("session_id", sa.CHAR(36), sa.ForeignKey("exam_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.CHAR(36), sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("answer", sa.JSON().with_variant(postgresql.JSONB, "postgresql"), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_submissions_session_id", "submissions", ["session_id"])
    op.create_index("ix_submissions_question_id", "submissions", ["question_id"])
    op.create_index("ix_submissions_session_question", "submissions", ["session_id", "question_id"])

    # 6. violation_logs table
    op.create_table(
        "violation_logs",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("session_id", sa.CHAR(36), sa.ForeignKey("exam_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("violation_type", sa.String(length=100), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("metadata", sa.JSON().with_variant(postgresql.JSONB, "postgresql"), nullable=True),
        sa.Column("severity", sa.String(length=50), nullable=False, server_default="medium"),
    )
    op.create_index("ix_violation_logs_session_id", "violation_logs", ["session_id"])
    op.create_index("ix_violation_logs_timestamp", "violation_logs", ["timestamp"])
    op.create_index("ix_violation_logs_severity", "violation_logs", ["severity"])


def downgrade() -> None:
    op.drop_table("violation_logs")
    op.drop_table("submissions")
    op.drop_table("exam_sessions")
    op.drop_table("questions")
    op.drop_table("exams")
    op.drop_table("users")
