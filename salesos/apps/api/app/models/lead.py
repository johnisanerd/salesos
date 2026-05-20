import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import LeadPersonalizationTier, LeadState, LeadStatus
from salesos_shared.db import TimestampMixin, UUIDPrimaryKeyMixin


class Lead(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "leads"

    campaign_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(100), default="google_maps", nullable=False)
    external_source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website: Mapped[str | None] = mapped_column(String(512), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[LeadStatus] = mapped_column(
        Enum(LeadStatus, name="lead_status"),
        default=LeadStatus.new,
        nullable=False,
    )
    lifecycle_state: Mapped[LeadState] = mapped_column(
        Enum(LeadState, name="lead_state"),
        default=LeadState.DISCOVERED,
        nullable=False,
    )
    state_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    state_timestamps: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    state_failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    heuristic_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    personalization_tier: Mapped[LeadPersonalizationTier | None] = mapped_column(
        Enum(LeadPersonalizationTier, name="lead_personalization_tier"),
        nullable=True,
    )
    normalized_fingerprint: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    campaign: Mapped["Campaign | None"] = relationship(back_populates="leads")
    enrichments: Mapped[list["LeadEnrichment"]] = relationship(back_populates="lead", lazy="selectin")
    scores: Mapped[list["LeadScore"]] = relationship(back_populates="lead", lazy="selectin")
    review_signals: Mapped[list["ReviewSignal"]] = relationship(back_populates="lead", lazy="selectin")
    outreach_logs: Mapped[list["OutreachLog"]] = relationship(back_populates="lead", lazy="selectin")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="lead", lazy="selectin")
    state_transitions: Mapped[list["LeadStateTransition"]] = relationship(back_populates="lead", lazy="selectin")
    dead_letters: Mapped[list["DeadLetterEntry"]] = relationship(back_populates="lead", lazy="selectin")
    escalations: Mapped[list["OperatorEscalation"]] = relationship(back_populates="lead", lazy="selectin")


Index("ix_leads_campaign_id", Lead.campaign_id)
Index("ix_leads_status", Lead.status)
Index("ix_leads_lifecycle_state", Lead.lifecycle_state)
