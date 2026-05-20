import uuid

from sqlalchemy import Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import EscalationStatus
from salesos_shared.db import TimestampMixin, UUIDPrimaryKeyMixin


class OperatorEscalation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "operator_escalations"

    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id"),
        nullable=True,
    )
    outreach_log_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("outreach_logs.id"),
        nullable=True,
    )
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[EscalationStatus] = mapped_column(
        Enum(EscalationStatus, name="escalation_status"),
        default=EscalationStatus.pending,
        nullable=False,
    )
    assigned_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    lead: Mapped["Lead"] = relationship(back_populates="escalations")
    conversation: Mapped["Conversation | None"] = relationship(back_populates="escalations")
    outreach_log: Mapped["OutreachLog | None"] = relationship(back_populates="escalations")


Index("ix_operator_escalations_lead_id", OperatorEscalation.lead_id)
Index("ix_operator_escalations_conversation_id", OperatorEscalation.conversation_id)
Index("ix_operator_escalations_status", OperatorEscalation.status)
