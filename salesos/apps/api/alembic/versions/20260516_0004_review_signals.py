"""add review signals

Revision ID: 20260516_0004
Revises: 20260510_0003
Create Date: 2026-05-16 00:04:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260516_0004"
down_revision: str | None = "20260510_0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "review_signals",
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.Integer(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("operational_summary", sa.Text(), nullable=False),
        sa.Column("generated_hook", sa.Text(), nullable=False),
        sa.Column("review_rating", sa.Numeric(3, 1), nullable=True),
        sa.Column("review_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lead_id", "category", "evidence_hash", name="uq_review_signals_dedup"),
    )
    op.create_index("ix_review_signals_lead_id", "review_signals", ["lead_id"])
    op.create_index("ix_review_signals_category", "review_signals", ["category"])


def downgrade() -> None:
    op.drop_index("ix_review_signals_category", table_name="review_signals")
    op.drop_index("ix_review_signals_lead_id", table_name="review_signals")
    op.drop_table("review_signals")
