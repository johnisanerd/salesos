"""outbound ops engine foundations

Revision ID: 20260520_0005
Revises: 20260516_0004
Create Date: 2026-05-20 00:05:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260520_0005"
down_revision = "20260516_0004"
branch_labels = None
depends_on = None


outreach_review_status_enum = postgresql.ENUM(
    "pending",
    "approved",
    "rejected",
    "edited",
    name="outreach_review_status",
    create_type=False,
)
follow_up_status_enum = postgresql.ENUM(
    "pending",
    "scheduled",
    "due",
    "processing",
    "sent",
    "failed",
    "replied",
    "skipped",
    "cancelled",
    name="follow_up_status",
    create_type=False,
)
escalation_status_enum = postgresql.ENUM(
    "none",
    "pending",
    "escalated",
    "resolved",
    name="escalation_status",
    create_type=False,
)
pipeline_stage_enum = postgresql.ENUM(
    "scrape",
    "normalize",
    "dedupe",
    "enrich",
    "intelligence",
    "score",
    "analyze",
    "outreach_generate",
    "outreach_review",
    "follow_up",
    "reply_classify",
    "escalate",
    "notify",
    name="pipeline_stage",
    create_type=False,
)
failure_category_enum = postgresql.ENUM(
    "validation",
    "dependency",
    "timeout",
    "persistence",
    "ai",
    "delivery",
    "operator",
    "unknown",
    name="failure_category",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("ALTER TYPE lead_state ADD VALUE IF NOT EXISTS 'INTELLIGENCE_READY'")
    op.execute("ALTER TYPE lead_state ADD VALUE IF NOT EXISTS 'IN_REVIEW'")
    op.execute("ALTER TYPE outreach_status ADD VALUE IF NOT EXISTS 'in_review'")
    op.execute("ALTER TYPE reply_classification ADD VALUE IF NOT EXISTS 'manual_review'")
    op.execute("ALTER TYPE workflow_status ADD VALUE IF NOT EXISTS 'dead_lettered'")

    outreach_review_status_enum.create(bind, checkfirst=True)
    follow_up_status_enum.create(bind, checkfirst=True)
    escalation_status_enum.create(bind, checkfirst=True)
    pipeline_stage_enum.create(bind, checkfirst=True)
    failure_category_enum.create(bind, checkfirst=True)

    op.add_column("workflow_logs", sa.Column("correlation_id", sa.String(length=100), nullable=True))
    op.add_column("workflow_logs", sa.Column("pipeline_stage", pipeline_stage_enum, nullable=True))
    op.add_column("workflow_logs", sa.Column("failure_category", failure_category_enum, nullable=True))
    op.add_column("workflow_logs", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("workflow_logs", sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("workflow_logs", sa.Column("dead_lettered", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index("ix_workflow_logs_pipeline_stage", "workflow_logs", ["pipeline_stage"])
    op.create_index("ix_workflow_logs_status", "workflow_logs", ["status"])

    op.add_column("outreach_logs", sa.Column("review_status", outreach_review_status_enum, nullable=False, server_default="pending"))
    op.add_column("outreach_logs", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("outreach_logs", sa.Column("reviewed_by", sa.String(length=255), nullable=True))
    op.add_column("outreach_logs", sa.Column("review_notes", sa.Text(), nullable=True))
    op.add_column("outreach_logs", sa.Column("follow_up_due_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("outreach_logs", sa.Column("follow_up_status", follow_up_status_enum, nullable=False, server_default="pending"))
    op.add_column("outreach_logs", sa.Column("follow_up_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("outreach_logs", sa.Column("latest_reply_classification", postgresql.ENUM(name="reply_classification", create_type=False), nullable=True))
    op.add_column("outreach_logs", sa.Column("escalation_status", escalation_status_enum, nullable=False, server_default="none"))
    op.create_index("ix_outreach_logs_review_status", "outreach_logs", ["review_status"])
    op.create_index("ix_outreach_logs_follow_up_status", "outreach_logs", ["follow_up_status"])

    op.add_column("conversations", sa.Column("escalation_status", escalation_status_enum, nullable=False, server_default="none"))

    op.create_table(
        "dead_letter_entries",
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaigns.id"), nullable=True),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id"), nullable=True),
        sa.Column("workflow_name", sa.String(length=150), nullable=False),
        sa.Column("pipeline_stage", pipeline_stage_enum, nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=True),
        sa.Column("failure_category", failure_category_enum, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_dead_letter_entries_campaign_id", "dead_letter_entries", ["campaign_id"])
    op.create_index("ix_dead_letter_entries_lead_id", "dead_letter_entries", ["lead_id"])
    op.create_index("ix_dead_letter_entries_pipeline_stage", "dead_letter_entries", ["pipeline_stage"])

    op.create_table(
        "operator_escalations",
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=True),
        sa.Column("outreach_log_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("outreach_logs.id"), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("status", escalation_status_enum, nullable=False, server_default="pending"),
        sa.Column("assigned_to", sa.String(length=255), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_operator_escalations_lead_id", "operator_escalations", ["lead_id"])
    op.create_index("ix_operator_escalations_conversation_id", "operator_escalations", ["conversation_id"])
    op.create_index("ix_operator_escalations_status", "operator_escalations", ["status"])


def downgrade() -> None:
    op.drop_index("ix_operator_escalations_status", table_name="operator_escalations")
    op.drop_index("ix_operator_escalations_conversation_id", table_name="operator_escalations")
    op.drop_index("ix_operator_escalations_lead_id", table_name="operator_escalations")
    op.drop_table("operator_escalations")

    op.drop_index("ix_dead_letter_entries_pipeline_stage", table_name="dead_letter_entries")
    op.drop_index("ix_dead_letter_entries_lead_id", table_name="dead_letter_entries")
    op.drop_index("ix_dead_letter_entries_campaign_id", table_name="dead_letter_entries")
    op.drop_table("dead_letter_entries")

    op.drop_column("conversations", "escalation_status")

    op.drop_index("ix_outreach_logs_follow_up_status", table_name="outreach_logs")
    op.drop_index("ix_outreach_logs_review_status", table_name="outreach_logs")
    op.drop_column("outreach_logs", "escalation_status")
    op.drop_column("outreach_logs", "latest_reply_classification")
    op.drop_column("outreach_logs", "follow_up_attempts")
    op.drop_column("outreach_logs", "follow_up_status")
    op.drop_column("outreach_logs", "follow_up_due_at")
    op.drop_column("outreach_logs", "review_notes")
    op.drop_column("outreach_logs", "reviewed_by")
    op.drop_column("outreach_logs", "reviewed_at")
    op.drop_column("outreach_logs", "review_status")

    op.drop_index("ix_workflow_logs_status", table_name="workflow_logs")
    op.drop_index("ix_workflow_logs_pipeline_stage", table_name="workflow_logs")
    op.drop_column("workflow_logs", "dead_lettered")
    op.drop_column("workflow_logs", "retryable")
    op.drop_column("workflow_logs", "retry_count")
    op.drop_column("workflow_logs", "failure_category")
    op.drop_column("workflow_logs", "pipeline_stage")
    op.drop_column("workflow_logs", "correlation_id")

    bind = op.get_bind()
    failure_category_enum.drop(bind, checkfirst=True)
    pipeline_stage_enum.drop(bind, checkfirst=True)
    escalation_status_enum.drop(bind, checkfirst=True)
    follow_up_status_enum.drop(bind, checkfirst=True)
    outreach_review_status_enum.drop(bind, checkfirst=True)
