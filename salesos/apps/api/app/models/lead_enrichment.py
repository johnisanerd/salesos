import uuid

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from salesos_shared.db import TimestampMixin, UUIDPrimaryKeyMixin


class LeadEnrichment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lead_enrichments"

    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    lead: Mapped["Lead"] = relationship(back_populates="enrichments")


Index("ix_lead_enrichments_lead_id", LeadEnrichment.lead_id)
