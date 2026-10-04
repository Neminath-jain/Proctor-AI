"""Phase 5 trust score and human-in-the-loop review schema

Revision ID: 0006_phase5_trust_score_and_reviews
Revises: 0005_performance_indexes
Create Date: 2026-09-22 20:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0006_phase5_trust_scores"
down_revision: Union[str, None] = "0005_performance_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # 1. exam_sessions Phase 5 columns and indexes
    exam_sessions_cols = {c["name"] for c in insp.get_columns("exam_sessions")}
    exam_sessions_indexes = {idx["name"] for idx in insp.get_indexes("exam_sessions")}

    if "trust_score" not in exam_sessions_cols:
        op.add_column("exam_sessions", sa.Column("trust_score", sa.Float(), nullable=False, server_default="100.0"))
    if "review_status" not in exam_sessions_cols:
        op.add_column("exam_sessions", sa.Column("review_status", sa.String(length=50), nullable=False, server_default="pending"))
    if "reviewed_by" not in exam_sessions_cols:
        op.add_column("exam_sessions", sa.Column("reviewed_by", sa.CHAR(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    if "reviewed_at" not in exam_sessions_cols:
        op.add_column("exam_sessions", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    if "review_notes" not in exam_sessions_cols:
        op.add_column("exam_sessions", sa.Column("review_notes", sa.Text(), nullable=True))
    if "latest_snapshot_path" not in exam_sessions_cols:
        op.add_column("exam_sessions", sa.Column("latest_snapshot_path", sa.String(length=500), nullable=True))

    if "ix_exam_sessions_trust_score" not in exam_sessions_indexes:
        op.create_index("ix_exam_sessions_trust_score", "exam_sessions", ["trust_score"], unique=False)
    if "ix_exam_sessions_review_status" not in exam_sessions_indexes:
        op.create_index("ix_exam_sessions_review_status", "exam_sessions", ["review_status"], unique=False)

    # 2. violation_logs Phase 5 columns and indexes
    violation_logs_cols = {c["name"] for c in insp.get_columns("violation_logs")}
    violation_logs_indexes = {idx["name"] for idx in insp.get_indexes("violation_logs")}

    if "review_status" not in violation_logs_cols:
        op.add_column("violation_logs", sa.Column("review_status", sa.String(length=50), nullable=False, server_default="unreviewed"))
    if "reviewed_by" not in violation_logs_cols:
        op.add_column("violation_logs", sa.Column("reviewed_by", sa.CHAR(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    if "reviewed_at" not in violation_logs_cols:
        op.add_column("violation_logs", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    if "review_notes" not in violation_logs_cols:
        op.add_column("violation_logs", sa.Column("review_notes", sa.String(length=500), nullable=True))

    if "ix_violation_logs_review_status" not in violation_logs_indexes:
        op.create_index("ix_violation_logs_review_status", "violation_logs", ["review_status"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    violation_logs_cols = {c["name"] for c in insp.get_columns("violation_logs")}
    violation_logs_indexes = {idx["name"] for idx in insp.get_indexes("violation_logs")}

    if "ix_violation_logs_review_status" in violation_logs_indexes:
        op.drop_index("ix_violation_logs_review_status", table_name="violation_logs")
    for col in ["review_notes", "reviewed_at", "reviewed_by", "review_status"]:
        if col in violation_logs_cols:
            op.drop_column("violation_logs", col)

    exam_sessions_cols = {c["name"] for c in insp.get_columns("exam_sessions")}
    exam_sessions_indexes = {idx["name"] for idx in insp.get_indexes("exam_sessions")}

    if "ix_exam_sessions_review_status" in exam_sessions_indexes:
        op.drop_index("ix_exam_sessions_review_status", table_name="exam_sessions")
    if "ix_exam_sessions_trust_score" in exam_sessions_indexes:
        op.drop_index("ix_exam_sessions_trust_score", table_name="exam_sessions")

    for col in ["latest_snapshot_path", "review_notes", "reviewed_at", "reviewed_by", "review_status", "trust_score"]:
        if col in exam_sessions_cols:
            op.drop_column("exam_sessions", col)
