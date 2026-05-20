import uuid

from sqlalchemy import Enum, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import LeadState
from salesos_shared.db import TimestampMixin, UUIDPrimaryKeyMixin


class LeadStateTransition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lead_state_transitions"

    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False)
    from_state: Mapped[LeadState | None] = mapped_column(Enum(LeadState, name="lead_state"), nullable=True)
    to_state: Mapped[LeadState] = mapped_column(Enum(LeadState, name="lead_state"), nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    lead: Mapped["Lead"] = relationship(back_populates="state_transitions")


Index("ix_lead_state_transitions_lead_id", LeadStateTransition.lead_id)
Index("ix_lead_state_transitions_to_state", LeadStateTransition.to_state)
