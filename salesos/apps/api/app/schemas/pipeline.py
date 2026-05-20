import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import FailureCategory, PipelineStage


class EnrichmentPayload(BaseModel):
    lead_id: uuid.UUID
    provider: str
    payload: dict[str, Any] = Field(default_factory=dict)


class LeadAnalysisRequest(BaseModel):
    lead_id: uuid.UUID
    business_name: str
    context: str


class ReplyClassificationRequest(BaseModel):
    conversation_id: uuid.UUID
    message_body: str


class OutreachPreparationRequest(BaseModel):
    campaign_id: uuid.UUID
    lead_id: uuid.UUID
    business_name: str
    context: str


class PipelineEvent(BaseModel):
    workflow_event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    workflow_run_id: uuid.UUID
    campaign_id: uuid.UUID | None = None
    lead_id: uuid.UUID | None = None
    workflow_stage: str
    pipeline_stage: PipelineStage | None = None
    correlation_id: str | None = None
    duration_ms: float = 0.0
    status: str
    error_message: str | None = None
    failure_category: FailureCategory | None = None
    retry_count: int = 0
    retryable: bool = False
    dead_lettered: bool = False
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)
