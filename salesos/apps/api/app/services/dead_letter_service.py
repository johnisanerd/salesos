from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dead_letter_entry import DeadLetterEntry
from app.models.enums import FailureCategory, PipelineStage
from app.repositories.dead_letter_repository import DeadLetterRepository


class DeadLetterService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = DeadLetterRepository(session)

    async def create_entry(
        self,
        *,
        workflow_name: str,
        pipeline_stage: PipelineStage,
        failure_category: FailureCategory,
        error_message: str,
        correlation_id: str,
        campaign_id: uuid.UUID | None = None,
        lead_id: uuid.UUID | None = None,
        retry_count: int = 0,
        retryable: bool = False,
        payload: dict[str, Any] | None = None,
    ) -> DeadLetterEntry:
        entry = DeadLetterEntry(
            workflow_name=workflow_name,
            pipeline_stage=pipeline_stage,
            failure_category=failure_category,
            error_message=error_message,
            correlation_id=correlation_id,
            campaign_id=campaign_id,
            lead_id=lead_id,
            retry_count=retry_count,
            retryable=retryable,
            payload=payload or {},
        )
        await self.repository.add(entry)
        await self.session.commit()
        await self.session.refresh(entry)
        return entry
