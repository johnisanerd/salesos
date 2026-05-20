import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EscalationStatus, FollowUpStatus, OutreachReviewStatus, OutreachStatus, ReplyClassification


class OutreachReviewRead(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    campaign_id: uuid.UUID | None
    status: OutreachStatus
    review_status: OutreachReviewStatus
    subject: str | None
    body: str | None
    review_notes: str | None
    follow_up_due_at: datetime | None
    follow_up_status: FollowUpStatus
    latest_reply_classification: ReplyClassification | None
    escalation_status: EscalationStatus
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OutreachReviewAction(BaseModel):
    reviewer: str
    notes: str | None = None
    subject: str | None = None
    body: str | None = None


class FollowUpScheduleRequest(BaseModel):
    due_at: datetime
    actor: str = "operator"


class ReplyIngestRequest(BaseModel):
    conversation_id: uuid.UUID
    message_body: str
    sender: str | None = None


class EscalationRead(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    conversation_id: uuid.UUID | None
    outreach_log_id: uuid.UUID | None
    reason: str
    status: EscalationStatus
    assigned_to: str | None
    resolution_notes: str | None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EscalationResolveRequest(BaseModel):
    actor: str
    resolution_notes: str


class JobSnapshot(BaseModel):
    job_id: str
    status: str
    created_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None


class DashboardSnapshot(BaseModel):
    jobs: list[JobSnapshot]
    leads: list[dict[str, Any]]
    outreach: list[dict[str, Any]]
    failures: list[dict[str, Any]]
    metrics: dict[str, Any]
    escalations: list[dict[str, Any]]
