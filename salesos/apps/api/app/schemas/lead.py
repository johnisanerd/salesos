import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import LeadPersonalizationTier, LeadState, LeadStatus


class LeadCreate(BaseModel):
    campaign_id: uuid.UUID | None = None
    source: str = "google_maps"
    external_source_id: str | None = None
    business_name: str
    phone: str | None = None
    email: EmailStr | None = None
    website: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    category: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LeadRead(BaseModel):
    id: uuid.UUID
    campaign_id: uuid.UUID | None
    business_name: str
    status: LeadStatus
    lifecycle_state: LeadState
    heuristic_score: float | None = None
    personalization_tier: LeadPersonalizationTier | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    city: str | None
    state: str | None
    category: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScrapeRequest(BaseModel):
    campaign_id: uuid.UUID | None = None
    query: str
    location: str
    max_results: int = 25
    fixture_name: str | None = None


class ScrapePipelineResponse(BaseModel):
    workflow_run_id: uuid.UUID
    correlation_id: str
    source_mode: str
    workflow_status: str
    total_received: int
    inserted: int
    deduplicated: int
    reused_existing: int
    analyzed: int
    personalized: int
    outreach_generated: int
    skipped_due_to_cooldown: int
    invalid: int
    campaign_id: uuid.UUID | None
    summary: str
    errors: list[dict[str, Any]] = Field(default_factory=list)


JobStatus = Literal["pending", "running", "partial", "failed", "completed"]


class ScrapeJobAccepted(BaseModel):
    job_id: uuid.UUID
    status: JobStatus


class ScrapeJobStatusResponse(BaseModel):
    job_id: uuid.UUID
    status: JobStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    result: ScrapePipelineResponse | None = None
    error: dict[str, Any] | None = None
