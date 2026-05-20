import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import EscalationStatus, FollowUpStatus, OutreachChannel, OutreachReviewStatus, OutreachStatus, ReplyClassification
from salesos_shared.db import TimestampMixin, UUIDPrimaryKeyMixin


class OutreachLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "outreach_logs"

    campaign_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False)
    channel: Mapped[OutreachChannel] = mapped_column(Enum(OutreachChannel, name="outreach_channel"), nullable=False)
    status: Mapped[OutreachStatus] = mapped_column(
        Enum(OutreachStatus, name="outreach_status"),
        default=OutreachStatus.pending,
        nullable=False,
    )
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    review_status: Mapped[OutreachReviewStatus] = mapped_column(
        Enum(OutreachReviewStatus, name="outreach_review_status"),
        default=OutreachReviewStatus.pending,
        nullable=False,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    follow_up_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    follow_up_status: Mapped[FollowUpStatus] = mapped_column(
        Enum(FollowUpStatus, name="follow_up_status"),
        default=FollowUpStatus.pending,
        nullable=False,
    )
    follow_up_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latest_reply_classification: Mapped[ReplyClassification | None] = mapped_column(
        Enum(ReplyClassification, name="reply_classification"),
        nullable=True,
    )
    escalation_status: Mapped[EscalationStatus] = mapped_column(
        Enum(EscalationStatus, name="escalation_status"),
        default=EscalationStatus.none,
        nullable=False,
    )
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    campaign: Mapped["Campaign | None"] = relationship(back_populates="outreach_logs")
    lead: Mapped["Lead"] = relationship(back_populates="outreach_logs")
    escalations: Mapped[list["OperatorEscalation"]] = relationship(back_populates="outreach_log", lazy="selectin")


Index("ix_outreach_logs_campaign_id", OutreachLog.campaign_id)
Index("ix_outreach_logs_lead_id", OutreachLog.lead_id)
Index("ix_outreach_logs_review_status", OutreachLog.review_status)
Index("ix_outreach_logs_follow_up_status", OutreachLog.follow_up_status)
