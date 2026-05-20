import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from salesos_shared.db import TimestampMixin, UUIDPrimaryKeyMixin


class LeadScore(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lead_scores"

    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    lead: Mapped["Lead"] = relationship(back_populates="scores")


Index("ix_lead_scores_lead_id", LeadScore.lead_id)
