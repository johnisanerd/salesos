"""add lead lifecycle state machine

Revision ID: 20260510_0003
Revises: 20260510_0002
Create Date: 2026-05-10 00:03:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260510_0003"
down_revision = "20260510_0002"
branch_labels = None
depends_on = None


lead_state_enum = postgresql.ENUM(
    "DISCOVERED",
    "ENRICHED",
    "QUALIFIED",
    "PERSONALIZED",
    "OUTREACH_READY",
    "CONTACTED",
    "REPLIED",
    "INTERESTED",
    "CLOSED",
    "REJECTED",
    "COOLDOWN",
    "FAILED",
    name="lead_state",
    create_type=False,
)
lead_personalization_tier_enum = postgresql.ENUM(
    "high",
    "medium",
    "low",
    name="lead_personalization_tier",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    lead_state_enum.create(bind, checkfirst=True)
    lead_personalization_tier_enum.create(bind, checkfirst=True)

    op.add_column(
        "leads",
        sa.Column("lifecycle_state", lead_state_enum, nullable=False, server_default="DISCOVERED"),
    )
    op.add_column("leads", sa.Column("state_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "leads",
        sa.Column(
            "state_timestamps",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column("leads", sa.Column("state_failure_reason", sa.Text(), nullable=True))
    op.add_column("leads", sa.Column("heuristic_score", sa.Numeric(5, 2), nullable=True))
    op.add_column("leads", sa.Column("personalization_tier", lead_personalization_tier_enum, nullable=True))
    op.create_index("ix_leads_lifecycle_state", "leads", ["lifecycle_state"])

    op.create_table(
        "lead_state_transitions",
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("from_state", lead_state_enum, nullable=True),
        sa.Column("to_state", lead_state_enum, nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_lead_state_transitions_lead_id", "lead_state_transitions", ["lead_id"])
    op.create_index("ix_lead_state_transitions_to_state", "lead_state_transitions", ["to_state"])


def downgrade() -> None:
    op.drop_index("ix_lead_state_transitions_to_state", table_name="lead_state_transitions")
    op.drop_index("ix_lead_state_transitions_lead_id", table_name="lead_state_transitions")
    op.drop_table("lead_state_transitions")

    op.drop_index("ix_leads_lifecycle_state", table_name="leads")
    op.drop_column("leads", "personalization_tier")
    op.drop_column("leads", "heuristic_score")
    op.drop_column("leads", "state_failure_reason")
    op.drop_column("leads", "state_timestamps")
    op.drop_column("leads", "state_updated_at")
    op.drop_column("leads", "lifecycle_state")

    bind = op.get_bind()
    lead_personalization_tier_enum.drop(bind, checkfirst=True)
    lead_state_enum.drop(bind, checkfirst=True)
