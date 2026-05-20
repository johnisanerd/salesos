import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import FailureCategory, PipelineStage
from salesos_shared.db import TimestampMixin, UUIDPrimaryKeyMixin


class DeadLetterEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "dead_letter_entries"

    campaign_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=True)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=True)
    workflow_name: Mapped[str] = mapped_column(String(150), nullable=False)
    pipeline_stage: Mapped[PipelineStage] = mapped_column(Enum(PipelineStage, name="pipeline_stage"), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_category: Mapped[FailureCategory] = mapped_column(
        Enum(FailureCategory, name="failure_category"),
        nullable=False,
    )
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retryable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    lead: Mapped["Lead | None"] = relationship(back_populates="dead_letters")


Index("ix_dead_letter_entries_campaign_id", DeadLetterEntry.campaign_id)
Index("ix_dead_letter_entries_lead_id", DeadLetterEntry.lead_id)
Index("ix_dead_letter_entries_pipeline_stage", DeadLetterEntry.pipeline_stage)
