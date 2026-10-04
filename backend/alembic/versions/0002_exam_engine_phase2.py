"""Exam engine Phase 2 schema additions

Revision ID: 0002_exam_engine_phase2
Revises: 0001_initial_schema
Create Date: 2026-09-21 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_exam_engine_phase2"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update questions table with Phase 2 fields
    op.add_column(
        "questions",
        sa.Column("is_multiselect", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column(
        "questions",
        sa.Column("partial_credit", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column(
        "questions",
        sa.Column("starter_code", sa.JSON().with_variant(postgresql.JSONB, "postgresql"), nullable=True)
    )
    op.add_column(
        "questions",
        sa.Column("allowed_languages", sa.JSON().with_variant(postgresql.JSONB, "postgresql"), nullable=True)
    )
    op.add_column(
        "questions",
        sa.Column("memory_limit", sa.Integer(), nullable=True, server_default="128000")
    )
    op.add_column(
        "questions",
        sa.Column("order", sa.Integer(), nullable=False, server_default="0")
    )

    # 2. Update exam_sessions table with session_metadata
    op.add_column(
        "exam_sessions",
        sa.Column("session_metadata", sa.JSON().with_variant(postgresql.JSONB, "postgresql"), nullable=True)
    )

    # 3. Update submissions table with details
    op.add_column(
        "submissions",
        sa.Column("details", sa.JSON().with_variant(postgresql.JSONB, "postgresql"), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("submissions", "details")
    op.drop_column("exam_sessions", "session_metadata")
    op.drop_column("questions", "order")
    op.drop_column("questions", "memory_limit")
    op.drop_column("questions", "allowed_languages")
    op.drop_column("questions", "starter_code")
    op.drop_column("questions", "partial_credit")
    op.drop_column("questions", "is_multiselect")
