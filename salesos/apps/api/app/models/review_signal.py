import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from salesos_shared.db import TimestampMixin, UUIDPrimaryKeyMixin


class ReviewSignal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "review_signals"
    __table_args__ = (
        UniqueConstraint("lead_id", "category", "evidence_hash", name="uq_review_signals_dedup"),
    )

    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    operational_summary: Mapped[str] = mapped_column(Text, nullable=False)
    generated_hook: Mapped[str] = mapped_column(Text, nullable=False)
    review_rating: Mapped[float | None] = mapped_column(Numeric(3, 1), nullable=True)
    review_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    lead: Mapped["Lead"] = relationship(back_populates="review_signals")


Index("ix_review_signals_lead_id", ReviewSignal.lead_id)
Index("ix_review_signals_category", ReviewSignal.category)
