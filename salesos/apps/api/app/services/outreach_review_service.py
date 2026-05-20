from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import FollowUpStatus, LeadState, OutreachReviewStatus, OutreachStatus
from app.models.outreach_log import OutreachLog
from app.repositories.base import Repository
from app.repositories.outreach_repository import OutreachLogRepository
from app.services.lead_lifecycle_service import LeadLifecycleService


class OutreachReviewService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = Repository(session)
        self.outreach = OutreachLogRepository(session)
        self.lifecycle = LeadLifecycleService(session)

    async def list_queue(self, *, limit: int = 50) -> list[OutreachLog]:
        return await self.outreach.list_review_queue(limit=limit)

    async def approve(self, outreach_id, *, reviewer: str, notes: str | None = None) -> OutreachLog:
        outreach = await self._get(outreach_id)
        outreach.review_status = OutreachReviewStatus.approved
        outreach.status = OutreachStatus.pending
        outreach.reviewed_at = datetime.now(UTC)
        outreach.reviewed_by = reviewer
        outreach.review_notes = notes
        outreach.follow_up_status = FollowUpStatus.scheduled
        await self.session.commit()
        return outreach

    async def reject(self, outreach_id, *, reviewer: str, notes: str | None = None) -> OutreachLog:
        outreach = await self._get(outreach_id)
        outreach.review_status = OutreachReviewStatus.rejected
        outreach.status = OutreachStatus.failed
        outreach.reviewed_at = datetime.now(UTC)
        outreach.reviewed_by = reviewer
        outreach.review_notes = notes
        await self.session.commit()
        return outreach

    async def edit(self, outreach_id, *, reviewer: str, subject: str | None, body: str | None, notes: str | None) -> OutreachLog:
        outreach = await self._get(outreach_id)
        outreach.subject = subject or outreach.subject
        outreach.body = body or outreach.body
        outreach.review_status = OutreachReviewStatus.edited
        outreach.status = OutreachStatus.pending
        outreach.reviewed_at = datetime.now(UTC)
        outreach.reviewed_by = reviewer
        outreach.review_notes = notes
        outreach.follow_up_status = FollowUpStatus.scheduled
        await self.session.commit()
        return outreach

    async def mark_sent(self, outreach: OutreachLog) -> None:
        outreach.status = OutreachStatus.sent
        await self.session.commit()

    async def _get(self, outreach_id) -> OutreachLog:
        outreach = await self.repository.get_by_id(OutreachLog, outreach_id)
        if outreach is None:
            raise ValueError("Outreach not found")
        return outreach
