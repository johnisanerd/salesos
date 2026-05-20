import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import FailureCategory, PipelineStage, WorkflowStatus
from salesos_shared.db import TimestampMixin, UUIDPrimaryKeyMixin


class WorkflowLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workflow_logs"

    campaign_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=True)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=True)
    workflow_name: Mapped[str] = mapped_column(String(150), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pipeline_stage: Mapped[PipelineStage | None] = mapped_column(
        Enum(PipelineStage, name="pipeline_stage"),
        nullable=True,
    )
    status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus, name="workflow_status"),
        default=WorkflowStatus.queued,
        nullable=False,
    )
    failure_category: Mapped[FailureCategory | None] = mapped_column(
        Enum(FailureCategory, name="failure_category"),
        nullable=True,
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retryable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dead_lettered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


Index("ix_workflow_logs_campaign_id", WorkflowLog.campaign_id)
Index("ix_workflow_logs_lead_id", WorkflowLog.lead_id)
Index("ix_workflow_logs_pipeline_stage", WorkflowLog.pipeline_stage)
Index("ix_workflow_logs_status", WorkflowLog.status)
