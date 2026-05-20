"""initial schema

Revision ID: 20260506_0001
Revises:
Create Date: 2026-05-06 00:01:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260506_0001"
down_revision = None
branch_labels = None
depends_on = None


campaign_status_enum = postgresql.ENUM(
    "draft",
    "ready",
    "running",
    "paused",
    "completed",
    "failed",
    name="campaign_status",
    create_type=False,
)
lead_status_enum = postgresql.ENUM(
    "new",
    "enriched",
    "analyzed",
    "queued",
    "contacted",
    "replied",
    "qualified",
    "archived",
    name="lead_status",
    create_type=False,
)
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
outreach_channel_enum = postgresql.ENUM(
    "email",
    "sms",
    "linkedin",
    name="outreach_channel",
    create_type=False,
)
outreach_status_enum = postgresql.ENUM(
    "pending",
    "prepared",
    "sent",
    "failed",
    name="outreach_status",
    create_type=False,
)
conversation_status_enum = postgresql.ENUM(
    "open",
    "waiting",
    "qualified",
    "disqualified",
    "closed",
    name="conversation_status",
    create_type=False,
)
reply_classification_enum = postgresql.ENUM(
    "positive",
    "neutral",
    "objection",
    "unsubscribe",
    "spam",
    name="reply_classification",
    create_type=False,
)
message_direction_enum = postgresql.ENUM(
    "inbound",
    "outbound",
    name="message_direction",
    create_type=False,
)
workflow_status_enum = postgresql.ENUM(
    "queued",
    "running",
    "succeeded",
    "failed",
    name="workflow_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    campaign_status_enum.create(bind, checkfirst=True)
    lead_status_enum.create(bind, checkfirst=True)
    lead_state_enum.create(bind, checkfirst=True)
    lead_personalization_tier_enum.create(bind, checkfirst=True)
    outreach_channel_enum.create(bind, checkfirst=True)
    outreach_status_enum.create(bind, checkfirst=True)
    conversation_status_enum.create(bind, checkfirst=True)
    reply_classification_enum.create(bind, checkfirst=True)
    message_direction_enum.create(bind, checkfirst=True)
    workflow_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "campaigns",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", campaign_status_enum, nullable=False, server_default="draft"),
        sa.Column("lead_query", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("message_template", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_campaigns_status", "campaigns", ["status"])

    op.create_table(
        "leads",
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaigns.id"), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=False, server_default="google_maps"),
        sa.Column("external_source_id", sa.String(length=255), nullable=True),
        sa.Column("business_name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("website", sa.String(length=512), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("state", sa.String(length=120), nullable=True),
        sa.Column("country", sa.String(length=120), nullable=True),
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column("status", lead_status_enum, nullable=False, server_default="new"),
        sa.Column("lifecycle_state", lead_state_enum, nullable=False, server_default="DISCOVERED"),
        sa.Column("state_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state_timestamps", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("state_failure_reason", sa.Text(), nullable=True),
        sa.Column("heuristic_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("personalization_tier", lead_personalization_tier_enum, nullable=True),
        sa.Column("normalized_fingerprint", sa.String(length=255), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("normalized_fingerprint"),
    )
    op.create_index("ix_leads_campaign_id", "leads", ["campaign_id"])
    op.create_index("ix_leads_status", "leads", ["status"])
    op.create_index("ix_leads_lifecycle_state", "leads", ["lifecycle_state"])

    op.create_table(
        "lead_state_transitions",
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("from_state", lead_state_enum, nullable=True),
        sa.Column("to_state", lead_state_enum, nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_lead_state_transitions_lead_id", "lead_state_transitions", ["lead_id"])
    op.create_index("ix_lead_state_transitions_to_state", "lead_state_transitions", ["to_state"])

    op.create_table(
        "lead_enrichments",
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_lead_enrichments_lead_id", "lead_enrichments", ["lead_id"])

    op.create_table(
        "lead_scores",
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("score", sa.Numeric(5, 2), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_lead_scores_lead_id", "lead_scores", ["lead_id"])

    op.create_table(
        "outreach_logs",
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaigns.id"), nullable=True),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("channel", outreach_channel_enum, nullable=False),
        sa.Column("status", outreach_status_enum, nullable=False, server_default="pending"),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_outreach_logs_campaign_id", "outreach_logs", ["campaign_id"])
    op.create_index("ix_outreach_logs_lead_id", "outreach_logs", ["lead_id"])

    op.create_table(
        "conversations",
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaigns.id"), nullable=True),
        sa.Column("channel", sa.String(length=50), nullable=False),
        sa.Column("status", conversation_status_enum, nullable=False, server_default="open"),
        sa.Column("latest_classification", reply_classification_enum, nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_conversations_lead_id", "conversations", ["lead_id"])
    op.create_index("ix_conversations_campaign_id", "conversations", ["campaign_id"])

    op.create_table(
        "conversation_messages",
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("direction", message_direction_enum, nullable=False),
        sa.Column("sender", sa.String(length=255), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_conversation_messages_conversation_id", "conversation_messages", ["conversation_id"])

    op.create_table(
        "telegram_sessions",
        sa.Column("chat_id", sa.String(length=100), nullable=False),
        sa.Column("user_id", sa.String(length=100), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("state", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("chat_id"),
    )
    op.create_index("ix_telegram_sessions_user_id", "telegram_sessions", ["user_id"])

    op.create_table(
        "workflow_logs",
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaigns.id"), nullable=True),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id"), nullable=True),
        sa.Column("workflow_name", sa.String(length=150), nullable=False),
        sa.Column("status", workflow_status_enum, nullable=False, server_default="queued"),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workflow_logs_campaign_id", "workflow_logs", ["campaign_id"])
    op.create_index("ix_workflow_logs_lead_id", "workflow_logs", ["lead_id"])


def downgrade() -> None:
    op.drop_index("ix_workflow_logs_lead_id", table_name="workflow_logs")
    op.drop_index("ix_workflow_logs_campaign_id", table_name="workflow_logs")
    op.drop_table("workflow_logs")
    op.drop_index("ix_telegram_sessions_user_id", table_name="telegram_sessions")
    op.drop_table("telegram_sessions")
    op.drop_index("ix_conversation_messages_conversation_id", table_name="conversation_messages")
    op.drop_table("conversation_messages")
    op.drop_index("ix_conversations_campaign_id", table_name="conversations")
    op.drop_index("ix_conversations_lead_id", table_name="conversations")
    op.drop_table("conversations")
    op.drop_index("ix_outreach_logs_lead_id", table_name="outreach_logs")
    op.drop_index("ix_outreach_logs_campaign_id", table_name="outreach_logs")
    op.drop_table("outreach_logs")
    op.drop_index("ix_lead_scores_lead_id", table_name="lead_scores")
    op.drop_table("lead_scores")
    op.drop_index("ix_lead_enrichments_lead_id", table_name="lead_enrichments")
    op.drop_table("lead_enrichments")
    op.drop_index("ix_lead_state_transitions_to_state", table_name="lead_state_transitions")
    op.drop_index("ix_lead_state_transitions_lead_id", table_name="lead_state_transitions")
    op.drop_table("lead_state_transitions")
    op.drop_index("ix_leads_lifecycle_state", table_name="leads")
    op.drop_index("ix_leads_status", table_name="leads")
    op.drop_index("ix_leads_campaign_id", table_name="leads")
    op.drop_table("leads")
    op.drop_index("ix_campaigns_status", table_name="campaigns")
    op.drop_table("campaigns")

    bind = op.get_bind()
    workflow_status_enum.drop(bind, checkfirst=True)
    message_direction_enum.drop(bind, checkfirst=True)
    reply_classification_enum.drop(bind, checkfirst=True)
    conversation_status_enum.drop(bind, checkfirst=True)
    outreach_status_enum.drop(bind, checkfirst=True)
    outreach_channel_enum.drop(bind, checkfirst=True)
    lead_personalization_tier_enum.drop(bind, checkfirst=True)
    lead_state_enum.drop(bind, checkfirst=True)
    lead_status_enum.drop(bind, checkfirst=True)
    campaign_status_enum.drop(bind, checkfirst=True)
